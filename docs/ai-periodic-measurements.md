> État actif : **0.8.1**, cible sélectionnée AI::update4Frame ; [nouveau relevé et sélection au lancement](ai-target-selection-measurements.md). Les mesures périodiques 0.8.0 ci-dessous restent historiques.

# Profilage ciblé AI::periodicUpdate — 0.8.0

**5 984 appels complétés de AI::periodicUpdate sont reliés exactement au rôle SDK world_ai_non_render dans la fenêtre finale x1 à Heng.** Leur temps inclusif cumulé, divisé par les 600 frames de service de la fenêtre, vaut **0,701594 ms/frame**. Aucun appel n'est enregistré dans les deux fenêtres finales de pause. Le deuxième worker sensible à la simulation reste sans fonction attribuée : ce point d'entrée ne le capture pas dans ces fenêtres.

La version **0.8.0**, compilée/liée v100 x64 et validée par MCP réel, conserve **17 outils et trois sondes de systèmes**. La sonde AI remplace PhysicsActual::_NV_backThreadUpdate ; les autres sont charsUpdate et NavMesh::findPath. Les callbacks de service GameWorld/Renderer sont inchangés. Aucun algorithme du moteur n'est modifié.

## Signature et collecte

AI/AI.h déclare publiquement void AI::_NV_periodicUpdate(float frametime), wrapper non virtuel. Le hook est résolu par KenshiLib::GetRealAddress sur ce wrapper, lié à la bibliothèque SDK puis observé réellement ; la méthode virtuelle periodicUpdate elle-même n'est pas passée à GetRealAddress, conformément à core/Functions.h. Aucun RVA ni layout n'est recodé.

La compilation a révélé une erreur d'en-tête : AI.h déclarait class CharacterMessage, alors que Character.h définit cet enum. prepare_deps.py remplace cette déclaration erronée par l'inclusion du Character.h du SDK ; correction idempotente dans la dépendance ignorée par Git. La première compilation échouée n'a pas été installée ; compilation et liaison suivantes réussies.

CallTelemetry.h partage les compteurs bornés avec l'ancienne interface PhysicsTelemetry.h, conservée pour les tests natifs. Le hook mesure seulement les appels **extérieurs complétés**. Un garde RAII de profondeur TLS laisse les appels imbriqués atteindre l'original mais évite de compter deux fois leur durée ; nested_entries_skipped_total les compte séparément. L'unwind C++ rétablit la profondeur en cas d'exception, sans absorber l'exception du jeu. Les appels extérieurs qui ne terminent pas normalement ne sont pas comptés comme complétés.

QPC encadre l'appel original ; son temps mural est inclusif et peut comprendre du travail délégué attendu. KENSHI_PROBE_AI_THREAD_CPU=1 active deux GetThreadTimes par appel extérieur, avec TID et création FILETIME. Le garde protège le dépôt des compteurs, jamais l'exécution de la fonction originale. Huit identités par bucket sont retenues ; un bucket unlisted conserve les compteurs excédentaires. Appels, maxima, disponibilité CPU et partitions sont réconciliés sans clamp. Chaque appel terminé est déposé dans le bucket de sa frame de fin ; il peut avoir commencé avant celle-ci. Aucun pointeur AI n'est conservé.

La lecture CPU de démarrage mesure environ 0,232 µs par requête dans ce lancement (200 requêtes). Ce n'est pas une calibration du coût complet de l'instrumentation. Les compteurs CPU sont quantifiés et leurs lectures contribuent à l'observation ; aucun gain ou coût exclusif n'est déduit de ce seul nombre.

## Preuves et protocole

- Archive de déploiement : crashes/20261028T061944920384Z-deployment-080, motif deployment_0.8.0, ancienne DLL 0.7.9/config/préférences/journal. Identités de l'ancien jeu 7716 et des watchdogs 12552/37596 vérifiées avant arrêt, seuls processus de ce projet touchés.
- Nouveau jeu **19296**, smoke runtime/ai-080-smoke.json : AI active, physique désactivée, trois sondes, sept rôles SDK, paramètre natif facultatif correct.
- Brut : **runtime/scenarios/pause-cpu-20261028T062209Z.json**, SHA-256 **05f3d92f9b9e129e560d5096248c197d42bf38820fa401bdfa3508cf826161bf**.
- Analyse : **runtime/ai-080-analysis.json**, recalculée par analyze_ai_periodic.py, avec identité SDK aux bornes et conservation des inconnus.
- État final : **runtime/ai-080-final.json**.

Le contrôleur recharge KenshiProbe_test, prépare Heng, laisse le streaming se stabiliser, puis exécute pause/x1/pause avec trois secondes de stabilisation et vingt secondes OS demandées par phase. Il observe scène/caméra/vitesse/horloge toutes les 0,5 seconde, collecte l'inventaire borné et les statistiques finales de 600 frames ainsi qu'un contexte plus large. Les rôles SDK sont lus en pause avant et après l'ensemble, sans chargement entre les phases. Les identités encadrent chaque scène CPU et restent stables. La copie est rechargée en pause à la fin. Aucun pytest pendant les mesures.

| Phase | CPU processus / temps réel | Processeurs logiques moyens | Population observée | Appels AI dans les 600 frames finales | Moyenne inclusive AI par frame |
| --- | --- | ---: | --- | ---: | ---: |
| Pause avant | 34,859375 s / 20,359 s | 1,712234 | 399 stable | 0 | 0 ms |
| x1 | 48,312500 s / 20,344 s | 2,374779 | 420..440 | 5 984 | 0,701594 ms |
| Pause après | 36,406250 s / 20,391 s | 1,785408 | 440 stable | 0 | 0 ms |

Horloge de simulation immobile en pause, +0,186449 heure à x1. Résidus signés processus moins threads : +0,062500 / +0,015625 / −0,062500 s ; deux threads absents à la seconde borne x1, exclusions explicites. Les populations/temps/caches évoluent : contraste descriptif, pas expérience causale entre phases ni comparaison de versions.

## Fonction et thread entier

La fenêtre finale x1 couvre les frames **15597..16196**, 600 frames, toutes dans la phase. Moyenne frame de service 7,396405 ms ; l'interception de la requête de statistiques termine après le heartbeat CPU, et la fenêtre n'est pas alignée exactement sur l'intervalle OS de 20,344 s.

Les appels AI sont tous sur **TID 18336, création FILETIME 134376419978624433**, identité du rôle world_ai_non_render aux deux bornes SDK et du thread OS. Durée murale inclusive cumulée **420,956201 ms**, maximum d'un appel **0,844700 ms**. CPU des appels : **250 ms user + 203,125 ms noyau**, 5 984 lectures disponibles, aucune indisponible. Aucun débordement ni entrée imbriquée observés dans cette fenêtre.

**453,125 ms CPU d'appels dépasse ici le cumul mural 420,956 ms.** Les mesures CPU de courts appels sont quantifiées et incluent des effets de lecture ; ces valeurs restent brutes, sans clamp ni transformation en couverture exclusive. Elles ne prouvent pas une accélération, une saturation de cœur ou une durée CPU exacte à l'échelle de chaque petit appel.

Le **thread entier** consomme 6,671875 s CPU sur l'intervalle OS x1, soit 0,327953 processeur logique moyen ; environ 0,047583 puis 0,045210 dans les pauses. Les fenêtres fonction/OS diffèrent : ne pas diviser leurs totaux pour annoncer une part de thread exclusive.

L'autre worker, **19228 / création 134376419978623026**, passe de **0,002302 à 0,326417 puis 0,001533 processeur logique**. Il n'apparaît pas dans les lignes de cette fonction retenues ; son rôle reste inconnu, et « autre worker » ne signifie pas « toute l'IA restante ». Le service principal GameWorld/Renderer, TID 38532, reste autour de 0,744450 / 0,744999 / 0,737917 logique. Aucun de ces nombres n'est transféré à un ancien PID/TID réutilisé.

## Validation et restauration

**241 pytest passent en 4,00 s.** Tests natifs v100 x64 : partitions, fusion, débordement, CPU partiel, TID réutilisé, et restauration de profondeur imbriquée après exception. Tests Python : historique physique inchangé, nouveaux compteurs AI, incompatibilité des sondes retraitées, identités CPU exactes, création SDK changée refusée pour l'attribution et scènes encadrées. Les buckets AI restent absents/None pour les anciens relevés.

Jeu 19296, watchdog wrapper **20820**/enfant **14244** au contrôle final, à revérifier avant arrêt. **702 fichiers KenshiProbe_validation, 702 KenshiProbe_test et 738 ancien snapshot conformes** ; settings.cfg byte-identique au préalable, gardes false. Copie en pause, vue normale de référence, Edge scrolling=true, combat suivi inactif, contrôle temporaire relâché. Watchdog frais/zéro erreur, autoload réussi, échéance/activation **1793225700** inchangées. Contrôleur terminé ; ancien snapshot sur disque, sa propriété en mémoire n'est plus supposée. Panneau RE_Kenshi non vérifié visuellement, autres applications non contrôlées.

## Prochaine hypothèse

AI::_NV_periodicUpdate couvre un point d'entrée du thread déjà identifié ; aucune optimisation ne suit automatiquement de ces mesures. Le worker 19228 nécessite un autre point d'entrée ou des piles CPU. AI/AI.h expose aussi **void AI::_NV_update4Frame(float)** : vérifier liaison puis le tester **en remplacement** de periodicUpdate, jamais comme quatrième sonde. Une sélection de fonction au lancement, explicitement rendue dans les métadonnées, éviterait de reconstruire une DLL par cible ; ne pas présenter des statistiques d'update4Frame sous le nom periodicUpdate. Conserver les anciens champs à null lorsque leur sonde n'est pas installée. Le pilote ETW administrateur reste en attente ; ne pas répéter la question ni la tentative bloquée sans changement utilisateur.
