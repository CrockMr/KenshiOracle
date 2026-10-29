# Coût de collecte : pilote en pause avec KenshiProbe 0.8.19

Le pilote accepté contient **36 blocs, 660 lectures MCP et aucune échéance sautée**. À 10 Hz, le mode complet est associé à un intervalle moyen entre callbacks plus long que le témoin dans les six triades : différence médiane **+0,10936 ms**, étendue **+0,06101 à +0,41160 ms**. Le CPU du jeu fluctue dans les deux sens. Le mode agrégé réduit les réponses d'environ 36 ko à 3,95 ko ; son avantage sur le CPU ou les callbacks n'est pas établi par ce pilote. Ces observations portent sur une seule session en pause, sans conclusion de gain FPS, de causalité ou de significativité statistique.

## Acquisition et état contrôlé

Le [protocole](observer-overhead-protocol.md) utilise les 17 outils existants, la même DLL 0.8.19 et les mêmes réglages. Chaque triade contient un témoin sans getter pendant le bloc (`baseline`), cinq ou cinquante lectures `get_frame_stats(n=60, detail='full')`, et autant de lectures `detail='aggregates'`. Les fréquences sont 1 et 10 Hz ; chacune possède six triades, couvrant les six permutations des trois conditions. L'ordre est déterministe et équilibré, **pas randomisé**. Les six paires par comparaison sont les unités d'analyse ; les requêtes ne sont pas traitées comme 660 réplications indépendantes.

Chaque bloc vise 5 s. Le contrôleur enregistré prévoit **1 s d'attente neutre sans commande** avant les lectures communes de scène et de heartbeat. Ce n'est pas un préchauffage de 2 s dans la condition étudiée. Le texte du protocole a été aligné sur ce plan du contrôleur ; les métadonnées du brut décrivent l'attente effectivement exécutée. Les contrôles et les statistiques finaux restent hors de la collecte CPU du jeu, mais un effet persistant sur le bloc suivant n'est pas exclu.

Les 108 lectures de scène des blocs montrent toutes **78 personnages chargés, 1 ville active**, pause effective, multiplicateur zéro et heure simulée `404.3333339691162`. La bataille suivie est inactive. Le centre et la position de caméra sont identiques à la référence prise après verrouillage, jusqu'au contrôle avant libération. Ces inventaires et positions stables ne prouvent pas que toute l'activité interne ou la charge de la machine soit identique entre blocs.

Le processus reste le PID `32156`, création `1793219931.5380297`, exécutable `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe --norestart`. Le thread Root est joint par TID `18784` et création `134376935315380313`. La DLL conserve le SHA-256 `796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3`, avec trois hooks de systèmes et deux hooks de service déjà présents. Aucun hook ou outil supplémentaire n'a été ajouté pour cette mesure.

## Volumes et latences

Pour chaque bloc de lecture, on calcule d'abord la médiane de ses 5 requêtes à 1 Hz ou de ses 50 requêtes à 10 Hz. Le tableau présente ensuite **la médiane [minimum ; maximum] des six médianes de blocs**. Il ne regroupe pas les requêtes de plusieurs blocs dans une seule distribution. Le témoin ne produit aucune requête de statistiques pendant sa fenêtre et n'a donc pas de latence correspondante.

| Fréquence et réponse | Octets JSON par résultat | Latence client MCP, ms | Service natif, ms | Attente en file, ms |
|---|---:|---:|---:|---:|
| 1 Hz, full | 35 985 [35 974 ; 35 990] | 11,769 [9,383 ; 15,285] | 2,230 [2,119 ; 2,412] | 3,078 [1,424 ; 6,054] |
| 1 Hz, aggregates | 3 946 [3 943 ; 3 948] | 9,703 [7,997 ; 12,326] | 2,346 [2,186 ; 2,447] | 2,969 [1,286 ; 4,568] |
| 10 Hz, full | 35 989 [35 985,5 ; 35 991] | 11,791 [10,901 ; 12,850] | 2,204 [2,178 ; 2,218] | 3,590 [2,940 ; 4,741] |
| 10 Hz, aggregates | 3 944,75 [3 942 ; 3 946] | 11,110 [9,558 ; 11,846] | 2,251 [2,222 ; 2,381] | 4,252 [2,990 ; 5,058] |

Les octets sont ceux du réencodage JSON compact du résultat reçu, sans enveloppe de transport. La réduction observée est d'environ **89 %**. Dans les six différences appariées `aggregates − full`, la médiane du changement de volume est −32 039,5 octets à 1 Hz et −32 045 octets à 10 Hz ; les douze différences sont négatives.

À 10 Hz, les six différences appariées de latence client sont négatives : médiane **−0,890 ms**, étendue −1,838 à −0,624 ms. Le service natif est pourtant plus long dans les six paires : médiane **+0,04975 ms**, étendue +0,01710 à +0,18360 ms. À 1 Hz, la latence client diminue dans cinq paires sur six, médiane −1,190 ms et étendue −6,213 à +0,256 ms ; le service augmente dans cinq sur six, médiane +0,05800 ms et étendue −0,21170 à +0,24890 ms.

Ces portées différentes empêchent de présenter la baisse de latence client comme une accélération du calcul des statistiques. Le [mode agrégé](aggregate-statistics-measurements.md) construit toujours la réponse complète avant de remplacer deux listes par `null` et leurs comptes d'omissions. Le [service natif](command-service-measurements.md) mesure une durée murale d'exécution, d'affectation de réponse et de journalisation ; il exclut notamment l'attachement de télémétrie, la sérialisation réseau et le transport client. Ce n'est pas du CPU exclusif.

## Différences appariées de CPU et de callbacks

Chaque cellule indique **médiane [minimum ; maximum] ; nombre de différences positives sur 6**. Une valeur positive signifie que le traitement dépasse sa référence. Le CPU est exprimé en équivalents de processeur logique : secondes CPU divisées par la durée propre à chaque compteur, sans normalisation au nombre de cœurs de la machine. La métrique de callback est la moyenne de la fenêtre de statistiques, pas la durée exclusive de `Root::renderOneFrame`.

| Hz | Traitement − référence | CPU processus jeu | CPU thread Root | CPU contrôleur | Intervalle moyen entre callbacks, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | −0,02756 [−0,12738 ; +0,21217] ; 2/6 | +0,02337 [−0,00265 ; +0,03897] ; 5/6 | +0,00003 [−0,00300 ; +0,00601] ; 4/6 | +0,00143 [−0,62351 ; +0,32596] ; 3/6 |
| 1 | aggregates − baseline | +0,06267 [−0,20039 ; +0,15313] ; 4/6 | +0,00017 [−0,02516 ; +0,04654] ; 3/6 | +0,00154 [−0,00298 ; +0,00606] ; 5/6 | −0,02837 [−0,86700 ; +0,19846] ; 2/6 |
| 1 | aggregates − full | −0,06221 [−0,12490 ; +0,16640] ; 2/6 | −0,01589 [−0,05673 ; +0,00757] ; 2/6 | +0,00004 [−0,00600 ; +0,00886] ; 5/6 | −0,03417 [−0,30468 ; +0,51289] ; 3/6 |
| 10 | full − baseline | −0,04393 [−0,13168 ; +0,32913] ; 2/6 | +0,01448 [−0,06026 ; +0,03720] ; 5/6 | +0,01048 [+0,00001 ; +0,02089] ; 6/6 | +0,10936 [+0,06101 ; +0,41160] ; 6/6 |
| 10 | aggregates − baseline | −0,03129 [−0,22045 ; +0,13930] ; 3/6 | +0,01903 [−0,03693 ; +0,02574] ; 5/6 | +0,01062 [+0,00296 ; +0,02122] ; 6/6 | +0,09692 [−0,00677 ; +0,48892] ; 5/6 |
| 10 | aggregates − full | −0,04950 [−0,22895 ; +0,15060] ; 2/6 | +0,00476 [−0,02463 ; +0,02334] ; 3/6 | −0,00290 [−0,00895 ; +0,01229] ; 2/6 | −0,06507 [−0,31314 ; +0,42791] ; 2/6 |

Dans l'ordre des triades à 10 Hz, les six différences de callback `full − baseline` sont **+0,081783 ; +0,411605 ; +0,079408 ; +0,061012 ; +0,136937 ; +0,227934 ms**. Pour `aggregates − baseline`, elles sont **−0,006773 ; +0,098469 ; +0,241582 ; +0,488924 ; +0,095362 ; +0,074112 ms**. Ce signal justifie de traiter la fréquence de collecte comme une variable de mesure. L'avantage d'`aggregates` sur `full` reste mixte : à 10 Hz, quatre différences de callback sont négatives et deux positives, avec une étendue qui traverse largement zéro.

Le témoin lui-même varie : ses moyennes de callback vont de 7,346 à 8,585 ms à 1 Hz, et de 7,384 à 7,975 ms à 10 Hz. Son CPU processus va respectivement de 1,327 à 1,768 et de 1,553 à 1,725 équivalent logique. Le plan équilibré et l'appariement ne suppriment ni cette variabilité, ni l'effet possible de l'ordre déterministe. Les différences de CPU du jeu ne constituent pas une preuve de réduction de son coût global.

## Bornes, calendrier et limites

| Portée mesurée | Minimum | Médiane | Maximum |
|---|---:|---:|---:|
| Bloc de requêtes, s | 5,00088 | 5,00774 | 5,01571 |
| Compteurs CPU processus, s | 5,06265 | 5,07171 | 5,09359 |
| Compteurs CPU du thread Root, s | 5,06310 | 5,07651 | 5,11488 |
| Compteurs CPU contrôleur, s | 5,12392 | 5,14111 | 5,18001 |
| Nombre de callbacks retenus | 600 | 657 | 706 |

Les 36 fenêtres de callbacks ont été obtenues en une requête agrégée chacune, avec leur n demandé conservé et sans dépasser le budget de 3600. Leurs intervalles cumulés vont d'environ 5,126 à 5,184 s. Ce sont des fenêtres glissantes de buckets, distinctes des intervalles CPU et de la fenêtre des requêtes ; les données agrégées ne permettent pas de retrancher individuellement tous les callbacks proches des contrôles auxiliaires.

Le calendrier accepté repose sur `perf_counter`, implémentation déclarée `QueryPerformanceCounter()`, monotone, non ajustable, résolution déclarée `1e-7 s`. La boucle d'attente revérifie l'échéance après chaque réveil. Les 660 départs de requête respectent le plan sans rattrapage, sans chevauchement et sans saut ; leur retard maximal observé est **16,485 ms**. Le témoin conserve 330 réveils enregistrés. Une résolution déclarée fine ne garantit pas une précision équivalente de l'ordonnanceur ou des compteurs CPU.

Le CPU du **serveur MCP séparé est indisponible** : l'adaptateur ne fournit pas son identité de processus. Le CPU contrôleur n'est donc pas le coût complet de toute la collecte. Il inclut son travail dans un intervalle légèrement plus large que le bloc, tandis que l'encodage et les endpoints finaux restent hors de la fenêtre CPU du jeu. Le témoin conserve le plugin, le watchdog, les hooks, les endpoints communs et les réveils du timer ; il n'est pas une référence sans instrumentation.

Deux omissions OS sont conservées : thread `33092` non observé après le bloc 2, et thread `42992` non observé avant le bloc 3, indices à partir de zéro. Le thread Root reste identifié. Le résidu signé processus moins somme des threads observés va de **−0,53125 à +0,125 s** ; il n'est ni ramené à zéro ni présenté comme du CPU attribuable à une fonction. Les lectures séquentielles, la quantification des compteurs et le bruit de la machine restent des limites, conformément au [rapport CPU Root](root-cpu-measurements.md).

La série ne fournit ni test de significativité, ni marge d'équivalence, ni preuve de stationnarité, ni extrapolation à une scène active ou au combat. Toute confirmation demande une nouvelle série indépendante, un ordre randomisé documenté, l'identité et le CPU du serveur MCP, et un contrôle explicite des effets persistants. Une campagne après le 28 octobre 2026 à 22 h 15 UTC nécessite une nouvelle autorisation.

## Essais rejetés et restitution

Deux bruts restent archivés séparément et sont exclus des comparaisons :

- [`observer-overhead-20261028T210549980627Z.json`](../runtime/scenarios/observer-overhead-20261028T210549980627Z.json), SHA-256 `3f6978934f9690f31552f53b12d274345b387b243862a9cbed29c4e9393b0eb8` : arrêt avant toute mesure, **0 bloc mesuré**, parce que la caméra avait bougé entre la lecture initiale et le verrouillage. La référence est désormais prise après stabilisation sous verrou ; le contrôle final de position précède sa libération.
- [`observer-overhead-20261028T211140302156Z.json`](../runtime/scenarios/observer-overhead-20261028T211140302156Z.json), SHA-256 `cb91beb08dd13b863d9aa2d57788e4bf52acb2a102269d75ebd0ba38d86281c0` : contrôleur déclaré terminé, mais rejeu strict refusé pour **72 réveils ou départs anticipés**, jusqu'à **13 ms**. La [preuve des réveils anticipés](../runtime/observer-early-wake-proof.json) est conservée. L'ancien `time.monotonic` basé sur `GetTickCount64`, à résolution déclarée de 15,625 ms, a été remplacé par QPC et une attente avec revérification. Les horodatages anciens ne sont ni convertis ni mélangés au pilote accepté.

À la sortie du pilote accepté, la copie reste en pause à la même heure ; `free_camera=false`, contrôle de caméra libéré et réglage Edge initial rétabli à `true`. Les sauvegardes protégées, dont `KenshiProbe_validation`, la copie et le snapshot sont vérifiés contre leurs manifestes ; les réglages, la DLL et les sources propres au pilote sont inchangés. Les deux gardes de restauration restent à `false` avant et après.

**Les coordonnées initiales de caméra ne sont pas restaurées.** Le déplacement entre lecture initiale et référence verrouillée vaut environ 12,732 unités ; après libération, le déplacement observé vaut environ 18,501 unités. La stabilité est attestée aux lectures sous verrou jusqu'à `pre_release_scene`, pas après restitution d'Edge. Cette distinction figure aussi dans les limites de l'analyseur.

Après cette campagne, Computer Use a replacé le pointeur sur une zone vide du panneau RE_Kenshi déjà ouvert. Trois lectures espacées d'une seconde retrouvent la caméra stable, sans verrou détenu, Edge=true et pointeur `(639,354)` dans la fenêtre. La [preuve complémentaire](../runtime/observer-post-ui-audit.json) recontrôle les702/702/738 fichiers, settings et pause. C'est un contrôle après acquisition, pas une modification ou une validation rétroactive des conditions visuelles de la campagne.

Cette même preuve vérifie directement les108 comptages78/1 et la constance Root/symbole/adresse/identité de service des660 réponses. Ces vérifications complètent le rejeu générique : son contrat n'impose pas encore ces deux invariants dans toutes les captures futures.

## Preuves et rejeu hors jeu

La suite de validation finale rapporte **992 tests réussis en 31,94 s**. Les sources du contrôleur, de l'analyseur, des helpers concernés et de leurs tests sont figées dans [`runtime/observer-sources-20261028T212056197Z`](../runtime/observer-sources-20261028T212056197Z/manifest.json). L'analyseur utilisé a pour SHA-256 `c5aa755acf16be898e4c0b6ac5e073a3b3c905293726fc22d28eaa0c8355c628` ; le contrôleur `46b47e83017c6c5b3f7f953795dc91aebea26c937cf8351718f66b0bf18e8f76`.

| Preuve | SHA-256 |
|---|---|
| [Brut accepté](../runtime/scenarios/observer-overhead-20261028T212059381502Z.json), 27 917 268 octets | `f6000a1c50ad1495b34419f33c2ae8dd9bc0cea0c0a74a01a7f20e6f715f11da` |
| [Rapport analysé](../runtime/observer-overhead-seed0.json), 93 918 octets | `bb355fb729cf59be9724eb1741b9ecf0e98d56438c96c81162a905552e18df05` |
| [Preuve des deux rejeux](../runtime/observer-overhead-replay-proof.json) | `c6022ad33e1e204a383be0e675b6696776588bb981eeb4c1ebc3a5549a7bee75` |

Les graines Python `0` et `8675309` produisent des rapports identiques octet par octet. Cela valide la reproductibilité de l'analyse du même brut ; ce ne sont pas deux nouvelles acquisitions. Pour refaire uniquement l'analyse depuis la racine du projet, choisir un **nouveau nom de sortie** : le mode de création exclusive refuse tout écrasement.

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe mcp-server/analyze_observer_overhead.py `
  runtime/scenarios/observer-overhead-20261028T212059381502Z.json `
  --expected-sha256 f6000a1c50ad1495b34419f33c2ae8dd9bc0cea0c0a74a01a7f20e6f715f11da `
  --output runtime/observer-overhead-replay-new.json
```

Le SHA du brut est vérifié avant analyse. Les comparaisons ci-dessus se recalculent depuis `result.blocks` et `result.paired` du rapport ; les latences supplémentaires appariées utilisent les médianes par bloc de `blocks[].requests` dans le brut. Aucun nouveau lancement du jeu n'est nécessaire pour ce rejeu.
