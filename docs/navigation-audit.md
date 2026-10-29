# Audit hors jeu des appels retenus

analyze_navigation.py lit les mesures JSON sans joindre le jeu. Il indexe les réponses, manifests et notes de qualité par SHA-256, et identifie un appel par processus/date de création/thread/horodatage QPC de départ. Des observations contradictoires d'une même identité provoquent une erreur ; elles ne sont pas fusionnées silencieusement.

Exécution depuis la racine, avec le PYTHONPATH habituel :

```powershell
.venv/Scripts/python.exe mcp-server/analyze_navigation.py --root runtime/measurements --output runtime/navigation-analysis.json
```

L'audit initial des campagnes jusqu'à 0.6.2 a regroupé 35 observations en **22 appels distincts** : 13 doublons provenaient des fenêtres et lectures de contexte qui se chevauchent. Dix-huit appels retenus ont renvoyé false et quatre true. **Ce n'est pas un taux d'échec de la navigation** : seuls des appels dépassant le seuil et encore présents dans le tampon sont représentés.

Quatre appels distincts sont dans des fenêtres avec garde de caméra à chaque fenêtre, quatorze dans les anciennes conditions vérifiées seulement aux bornes, quatre uniquement dans des contextes de transition. Sept disposent de CPU individuel, dont les quatre retours false déjà décrits dans navigation-diagnosis.md. La condition x1 à caméra dérivante est conservée pour la traçabilité mais exclue du groupe contrôlé. L'échec de restauration survenu après la paire suivante n'efface pas ses mesures terminées ; son rétablissement reste une preuve séparée.

L'outil recherche aussi les couples de clés/paramètres réapparaissant avec des XYZ différents. Dans ce premier petit ensemble de vecteurs, il n'en trouve pas ; cette absence n'établit ni la stabilité du maillage ni la sûreté d'un cache. Les arguments complets ne sont disponibles que pour quelques appels lents, et leur repère monde n'est pas établi.

La signature SDK NavMesh::findPath renvoie un booléen et un hkArray<EdgePathNode,...>& ; elle n'expose pas de code de terminaison détaillé. Les autres lectures comme pathExists, validateFaceKey, isInterior ou getWorldShift ne constituent pas un code de raison, et leurs invariants de verrouillage ne sont pas prouvés dans ce contexte. La version suivante compte donc les retours de **tous** les appels et observe la taille du tableau de sortie, sans inventer un motif de retour false ni réappeler un calcul du moteur.

Après la campagne 0.6.3, l'audit contient 44 observations, **27 appels distincts et 17 doublons retirés**. Dix-neuf retours false et huit true restent des appels retenus au-dessus du seuil, pas un taux global. Les neuf appels visibles uniquement dans des contextes restent séparés des fenêtres stabilisées. Chaque provenance indique aussi si l'appel précède, traverse ou suit la frame de préparation : l'appel de 180 ms de la dernière lecture x5 précède cette préparation et n'est donc pas attribué au travail de la nouvelle scène. Voir simulation-clock-measurements.md pour les nouveaux compteurs complets et le débit de l'horloge.

## Intégration explicite des captures de bataille

L'auditeur accepte maintenant le format de `live_battle.py`, sans le transformer en fenêtre de ville stabilisée :

```powershell
.venv/Scripts/python.exe mcp-server/analyze_navigation.py --root runtime/measurements --battle-root runtime/scenarios --output runtime/navigation-analysis-with-battles.json
```

L'exécution sur les données existantes produit **62 observations, 45 appels distincts et 17 doublons retirés**. Les huit fichiers de bataille gardent leur empreinte et leur provenance ; deux sans fenêtre finale sont exclus du calcul, avec motif explicite. Les six captures terminées apportent 18 appels retenus, dans une phase distincte `battle_tail`. Les anciens groupes de ville restent séparés. Le total de 27 false et 18 true concerne toujours l'échantillon retenu au-dessus du seuil, pas tous les appels du moteur.

Deux retours false ont un tableau de sortie non vide : **0→19** éléments, 140,917 ms murales/140,625 ms CPU dans le combat à deux acteurs ; **0→6**, 130,579 ms/125 ms CPU dans celui à dix. La validité ou l'utilisation ultérieure de ces éléments n'est pas attestée. Un booléen false ne suffit pas à conclure « aucun élément de chemin fourni » ni à concevoir un cache d'échecs sans conserver les autres sémantiques.

Les contrôles de caméra de bataille sont nommés `per_observation`, distincts de `per_window`. L'audit indique notamment `ends_after_last_observation` lorsque le relevé de statistiques final va au-delà de la dernière lecture de caméra ; il ne certifie pas ces frames sans observation. La frame de préparation vient de la première scène après création et reste étiquetée comme telle. Un appel ne dispose toujours pas d'identité de personnage, même si sa fin suit la préparation.

L'identité d'un appel retenu exige désormais PID **et** date de création ; un PID seul est refusé. Des désaccords de PID entre capture de bataille et ressources sont également rejetés. Sept tests supplémentaires couvrent sorties non vides, phases, borne d'observation, identité, déduplication entre formats, capture absente et caméra invalide.

Quatre groupes partagent les mêmes clés/paramètres mais présentent des XYZ différents. Cela confirme que les clés seules ne décrivent pas les arguments géométriques complets. Même des arguments capturés identiques ne prouvent pas la stabilité du maillage, des portes ou du streaming ; aucune sûreté de cache n'est établie.

## Contexte supplémentaire du relevé CPU par thread

La campagne `battle-20261028T025346Z.json` ajoute une lecture de diagnostic de 3600 frames, séparée de la fin de bataille de 600 frames. L'auditeur garde la phase `battle_diagnostic_context`, ses bornes d'observation propres et l'indicateur de troncature : **66 appels lents comptés, seulement 32 retenus** dans ce contexte. Les appels visibles dans les deux phases sont fusionnés par identité, sans emprunter les bornes caméra de l'autre phase.

L'audit actualisé contient **97 observations, 77 appels distincts et 20 doublons retirés** : 30 false/47 true parmi les appels retenus, toujours sans taux global d'échec inféré. Neuf fichiers de bataille sont indexés, dont deux sans fenêtre exclus ; 21 appels apparaissent dans leurs fins de mesure, 32 dans le nouveau contexte, et 50 appels distincts dans l'union des phases de bataille. Cinq retours false ont une sortie non vide ; sept groupes partagent les clés/paramètres avec des XYZ différents. Le contexte étendu ne devient pas une fenêtre contrôlée de combat et ne donne pas l'identité de personnage.

Trois tests vérifient la déduplication contexte/fin, les bornes distinctes et la provenance de la troncature. Voir thread-cpu-measurements.md pour le périmètre des rôles de threads et leurs limites.
