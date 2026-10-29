# Confirmation randomisée du coût de collecte — protocole préalable

Ce protocole prépare une nouvelle acquisition en pause avec **la même DLL 0.8.20**. Il ne rapporte aucun résultat. Il complète le [pilote précédent](direct-aggregate-statistics-measurements.md) sur deux limites : l'ordre déterministe des triades et l'absence de mesure du CPU du serveur MCP. Les contrôles de protection et de restitution du [protocole initial](observer-overhead-protocol.md) restent applicables.

## Plan et enregistrement avant capture

Le plan comporte **36 blocs de 5 s**, regroupés en **12 triades**. Chacune contient les trois conditions suivantes à une seule fréquence :

| Condition | Travail pendant le bloc |
|---|---|
| `baseline` | Aucun getter ; mêmes réveils programmés du timer |
| `full` | `get_frame_stats(n=60, detail='full')` à 1 ou 10 Hz |
| `aggregates` | `get_frame_stats(n=60, detail='aggregates')` à 1 ou 10 Hz |

Pour chacune des fréquences 1 et 10 Hz, les six permutations des trois conditions figurent exactement une fois. Les conditions d'une triade restent contiguës ; **l'ordre des 12 triades est randomisé**, sans modifier leurs permutations internes. La référence exécutable est `analyze_observer_randomized.make_plan(seed)`. Le plan effectivement obtenu, les indices de triade, fréquence, condition et position sont conservés intégralement.

Avant le premier bloc, figer une graine entière non signée de **64 bits**, sans conversion flottante, puis enregistrer la graine, le plan, ce protocole et les SHA-256 des sources, du manifeste et de la DLL. La DLL attendue est `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e`. Conserver le SHA du document de préenregistrement et vérifier que la capture reprend exactement sa graine et son plan. Il ne suffit pas de stocker une graine ajoutée après acquisition. Aucun réordonnancement ou choix de graine en fonction des premiers résultats n'est admis.

Chaque bloc est précédé de **1 s d'attente neutre sans commande**, identique dans les trois conditions, puis des mêmes contrôles auxiliaires. Ce n'est pas un préchauffage dans la condition mesurée. Les échéances absolues utilisent `perf_counter`/QPC avec revérification après réveil. Il n'y a qu'une requête en vol, aucun rattrapage en rafale ; retards, sauts et dépassements sont enregistrés. Une exécution complète prévoit 660 requêtes et 330 réveils de témoin. Un essai incomplet ou hors calendrier est conservé et signalé ; il ne remplace pas discrètement un essai défavorable.

## État maintenu et protection

Le protocole ne change ni le code natif 0.8.20, ni ses hooks, ni les réglages, ni les acteurs du jeu. Il n'ajoute ni combat, ni déplacement, ni entrée d'acteur ou de caméra. La copie `KenshiProbe_test` est utilisée ; `KenshiProbe_validation`, la copie et le snapshot protégé sont contrôlés par leurs manifestes.

Exiger une partie prête en pause, multiplicateur nul, heure simulée constante, absence de bataille suivie, même identité du processus de jeu et même contrat Root/CPU/service. Relever populations, ville active et positions : une variation doit rester visible, sans prétendre que la pause détermine toute la charge interne. Prendre la référence de caméra après verrouillage et stabilisation, puis la vérifier aux bornes de tous les blocs et juste avant libération. Ne pas ajouter d'entrée pour obtenir artificiellement de meilleurs timings.

À la fin, vérifier pause, heure, fichiers protégés, settings, DLL, sources et gardes de restauration. Libérer le contrôle de caméra et restituer le réglage Edge initial. Les coordonnées après libération sont enregistrées séparément ; le protocole ne garantit pas le retour aux coordonnées initiales. En cas d'échec, conserver le brut et l'état de restitution effectivement obtenu.

Si le serveur MCP devient indisponible, le nettoyage peut passer directement au TCP du plugin, après une nouvelle vérification du PID, de la création, de l'exécutable et des arguments du jeu. Ce secours est limité aux deux appels idempotents `pause(paused=True)` et `set_camera_free(enabled=False, release_edge=True)`. L'identité est vérifiée avant la tentative MCP et de nouveau avant son éventuel secours TCP. Chaque échec MCP et l'issue du secours sont enregistrés. **Une capture ayant utilisé ce secours reste invalide pour l'analyse, même si la restitution réussit.**

Les scènes immédiatement avant libération et après nettoyage sont lues directement en TCP après vérification fraîche de l'identité du jeu, afin de ne pas dépendre de la survie du serveur MCP. Les contrôles des fichiers et gardes s'exécutent dans un bloc indépendant des erreurs de caméra ou de transport. Une impossibilité de restauration est signalée ; elle n'est pas masquée par la réussite des autres contrôles.

## CPU du serveur MCP et bornes distinctes

Le serveur MCP persiste pendant toute la série. Son identité est déterminée à partir de son lancement, puis enregistrée avec exactement **six champs** : `pid`, `created_at`, `executable`, `cmdline`, `parent_pid` et `token`. Le jeton aléatoire de lancement, distinct de la graine du plan, relie le fichier d'identité créé exclusivement à cette session stdio. Le script propre `observer_mcp_server.py` publie l'identité, puis importe et sert le MCP existant dans ce même processus ; son code n'ajoute pas de getter implicite du jeu.

La provenance conserve la commande attendue, les exécutables Python autorisés, le chemin du script de démarrage, l'identité du contrôleur et la chaîne des parents. Le serveur doit être un enfant direct du contrôleur, ou son descendant à travers **un seul launcher Python venv**. Les dates de création des parents précèdent celles de leurs enfants ; la chaîne, les arguments et les identités sont revérifiés à chaque relevé CPU. Le launcher éventuel n'est pas le processus serveur mesuré. Les identités du serveur, du contrôleur et du jeu doivent être distinctes. Une identité ambiguë, un redémarrage ou une absence à un endpoint invalide la mesure CPU correspondante ; aucune consommation n'est estimée pour la remplacer.

Le compteur retenu est celui du **processus serveur seul**, hors launcher et hors somme récursive de ses enfants. Chaque relevé `mcp_server_cpu_before` ou `mcp_server_cpu_after` contient l'identité à six champs, `user_seconds`, `system_seconds` et `monotonic_seconds` issu de QPC. Les identités doivent correspondre à l'identité de référence ; temps et compteurs sont finis, les deltas CPU non négatifs, et les deux endpoints doivent encadrer la fenêtre des requêtes. L'intervalle propre au serveur sert à normaliser son delta CPU ; il n'est remplacé ni par les 5 s demandées ni par l'intervalle du jeu.

L'ordre enregistré par le contrôleur est : **serveur avant, contrôleur avant, jeu avant, bloc de requêtes, jeu après, serveur après, contrôleur après**, puis getters finaux. Les endpoints processus/thread du jeu, processus serveur et contrôleur restent distincts. Les getters auxiliaires, l'analyse et le réencodage des réponses sont exécutés hors de la fenêtre CPU du jeu ; leurs effets persistants restent possibles. Le CPU du contrôleur inclut son travail de collecte selon ses propres bornes. Aucun total contrôleur + serveur n'est présenté comme un coût synchrone exact, et le service natif n'est pas additionné au CPU du serveur.

Les statistiques de callbacks sont récupérées après le bloc, en mode agrégé, avec n calculé depuis les bornes de scène, une seule requête retenue et un budget maximal de **3600 frames**. Conserver première/dernière frame, n demandé/reçu et toutes les tentatives. Une réduction de n ou un dépassement du budget empêche de qualifier la fenêtre de complète. Les buckets glissants ne sont pas assimilés aux fenêtres des compteurs OS.

## Comparaisons annoncées et interprétation

La comparaison principale est **`aggregates − full` dans chacune des six triades de chaque fréquence**, pour trois mesures conservées séparément :

- service natif : différence entre médianes des requêtes de chaque bloc ;
- latence client MCP : même calcul sur la durée aller-retour observée par le contrôleur ;
- CPU du processus serveur : différence des équivalents de processeur logique, chacun calculé avec ses propres endpoints.

L'attente est une diminution de ces mesures avec la réponse agrégée. Publier toutes les six différences, leur médiane, leur étendue et les nombres de signes positifs, négatifs et nuls. Des signes mixtes ou des deltas proches de la quantification empêchent d'annoncer un effet uniformément reproduit. Aucune marge d'équivalence, aucun seuil de significativité et aucune règle de sélection favorable ne sont implicites. Les répétitions dans une même session ne sont pas des acquisitions indépendantes.

Les comparaisons `full − baseline` et `aggregates − baseline`, ainsi que les callbacks, CPU du jeu, thread Root, contrôleur, octets et attente en file restent publiées comme diagnostics secondaires. Le témoin conserve plugin, hooks, watchdog, timer et endpoints ; il n'est pas un jeu sans instrumentation. Le résultat de service doit rester une durée murale incluant seulement son périmètre documenté, pas du CPU exclusif.

Conserver les deltas quantifiés, les identités de threads manquantes et les résidus signés processus moins threads calculables, sans clamp ni attribution inventée. Les portées CPU, service, client et callbacks ne sont pas interchangeables. La randomisation réduit une limite d'ordre mais ne supprime ni le bruit de la machine, ni les effets persistants, ni la différence entre scènes successives. **Aucune causalité sur les FPS, aucun gain de rendu et aucune réduction générale du CPU moteur ne sont déduits de cette seule confirmation.**

## Preuves attendues

Le dossier de capture doit permettre de retrouver le préenregistrement antérieur au premier bloc, sa graine 64 bits et son plan, les sources et binaires identifiés, le brut de chaque tentative, l'analyse et l'audit de restitution. Le rejeu vérifie les SHA et le plan reconstruit, refuse les identités ou bornes incohérentes et crée une nouvelle sortie sans écrasement. Deux graines de hachage Python peuvent contrôler la stabilité du rejeu ; elles ne remplacent pas la graine de randomisation et ne constituent pas de nouvelles acquisitions.

Ce document définit les critères avant mesure. La graine réelle, les hashes de préenregistrement et les résultats appartiendront aux preuves de cette future capture ; ils ne sont pas inventés ici.
