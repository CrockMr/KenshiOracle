# Construction directe des statistiques agrégées — 0.8.20

La version 0.8.20 évite de construire les deux listes que le mode `aggregates` omet dans sa réponse. Son contrat est comparé à l'ancienne construction complète suivie de la projection : **2 266 assertions natives réussies sur 198 instantanés synthétiques**, avec zéro ligne individuelle construite sur le chemin agrégé. Sur les sept cas non vides du benchmark, la réduction médiane appariée du coût de construction va de **80,8 à 95,4 %**, et de **76,1 à 92,5 %** avec sérialisation. Un pilote réel de **36 blocs et 660 lectures** est aussi accepté : le service agrégé est environ **88,2 % plus court que le service complet de la même DLL** dans les comparaisons appariées. Les résultats synthétiques et réels ont des portées distinctes ; **aucun gain FPS n'est établi**.

L'utilisateur a annulé l'arrêt précédemment prévu à 23 h 15 le 28 octobre et autorisé la poursuite du projet en sa présence. Cette reprise explique les travaux 0.8.20 après la campagne de 24 heures. Elle ne transforme pas les mesures historiques 0.8.19 en validation de la nouvelle DLL.

## Changement et contrat conservé

En [0.8.19](aggregate-statistics-measurements.md), `get_frame_stats(n, detail='aggregates')` construisait la réponse complète, puis remplaçait `per_frame` et `navmesh_slow_calls` par `null`. Cette projection réduisait le payload mais conservait le travail de construction des lignes ensuite jetées. Le [pilote d'observation en pause](observer-overhead-measurements.md) séparait déjà le coût du service natif, la latence MCP, le CPU et les intervalles de callbacks.

Le chemin de production extrait dans [`FrameStatistics.h`](../plugin/FrameStatistics.h) conserve le parcours des samples, les agrégats, les percentiles, les identités, les bornes et les indicateurs de rétention. Le ring des appels lents est toujours copié sous le même verrou, puis filtré selon `completion_frame` dans les bornes de la fenêtre. En mode agrégé, le code compte les lignes retenues sans construire leurs objets JSON ; il saute aussi la construction des lignes `per_frame`.

Le helper [`setAggregateStatisticsDetail`](../plugin/StatisticsDetail.h) produit les mêmes `null` explicites et les trois champs de métadonnées : `mode`, `per_frame_rows_omitted`, `navmesh_slow_rows_omitted`. Les comptes correspondent aux lignes qu'aurait conservées la réponse complète : au plus 100 pour la série individuelle, au plus 32 pour le ring des appels lents filtré. Ils ne sont déduits ni du nombre total d'appels lents ni de la capacité du ring. Une omission demandée reste distincte d'une troncature de rétention.

Le défaut et `detail='full'` continuent de construire les lignes historiques. Les valeurs invalides restent refusées. Aucun nouveau champ public, outil MCP ou hook de système n'est nécessaire ; le registre reste à 17 outils et le plafond de trois systèmes profilés est conservé. Les autres calculs des statistiques et les algorithmes du jeu ne sont pas modifiés par cette optimisation.

## Oracle natif sur une même entrée

[`test_statistics_detail.cpp`](../tests/test_statistics_detail.cpp) exécute le code de production sur des instantanés propres au projet, sans binaire ni données du jeu. [`StatisticsLegacyOracle.h`](../tests/StatisticsLegacyOracle.h) conserve la construction historique de référence. Pour chaque instantané, le test vérifie :

- l'égalité des octets JSON de la réponse complète historique, du défaut actuel et du mode `full` explicite ;
- l'égalité des octets JSON entre l'ancienne réponse projetée et la construction agrégée directe ;
- la conservation des comptes d'omission, bornes et indicateurs, sans modification de l'instantané ;
- l'absence effective de construction des deux catégories de lignes en mode agrégé, grâce à des compteurs présents seulement dans le test.

Les cas couvrent notamment les historiques vides, 1/7/99/100/101/3600 samples, plusieurs dispositions du ring et filtres de bornes, les flags de profilage et cibles de fonction, les champs indisponibles et les comptes invalides. Un test de frontière inclut les appels terminés aux deux extrémités et exclut ceux terminés hors fenêtre ; `start_frame` ne remplace pas ce critère d'admission.

La [preuve native](../runtime/statistics-detail-native-0820/oracle.json), SHA-256 `ed5d772af789fcd9c8e3a24a9fbc3cedeb716f3a193341222310d6e47c288642`, rapporte `passed=true`, **2266 assertions**, **198 instantanés**, `toolset='v100 x64'`, `same_aggregate_projection=true`, `default_full_unchanged=true`, `aggregate_detail_rows_built=0`. Cette égalité porte sur les entrées testées. Elle ne mesure ni le coût des appels concurrents dans le jeu, ni la contention, ni la latence du réseau.

## Benchmark synthétique

Le benchmark terminé compare quatre opérations sur le même instantané immuable : construction complète historique, construction complète actuelle, construction historique suivie de la projection, et construction agrégée directe. La comparaison principale est la dernière contre l'avant-dernière, avec et sans sérialisation JSON ; le chemin complet fournit un contrôle de régression.

[`benchmark_statistics_detail.cpp`](../tests/benchmark_statistics_detail.cpp) couvre un historique vide, des historiques Root peu chargés de 60/100/600/3600 samples et trois cas denses avec rétention complète, filtrée ou ring rebouclé. Il chronomètre la construction et la destruction des objets, plus la sérialisation pour le mode qui l'active. Les contrôles d'égalité restent hors de la section chronométrée. Les opérations tournent dans un ordre décalé à chaque répétition après préchauffage ; chaque bloc de mesure comporte 40 opérations et chaque processus sept répétitions.

Trois processus exécutent ce plan, soit **21 paires de blocs par cas et par mode**. Les durées ci-dessous sont les médianes de ces 21 mesures par opération ; chaque mesure est le temps d'un bloc divisé par 40. La réduction est calculée dans chaque paire `(ancien projeté − direct) / ancien projeté`, puis résumée par sa médiane et son étendue. Ce n'est pas le ratio des deux médianes de durée ; les 21 paires ne sont pas 21 sessions indépendantes.

**Construction et destruction, sans sérialisation :**

| Cas synthétique | Ancien projeté, ms | Agrégé direct, ms | Réduction appariée : médiane [min ; max] |
|---|---:|---:|---:|
| Vide | 0,004883 | 0,004420 | 6,10 % [−32,57 ; 41,59] |
| Root peu chargé, 60 frames | 1,80597 | 0,12971 | 92,68 % [91,55 ; 94,07] |
| Root peu chargé, 100 frames | 3,06511 | 0,13978 | 95,45 % [94,60 ; 96,24] |
| Root peu chargé, 600 frames | 3,02749 | 0,17257 | 94,48 % [93,20 ; 95,35] |
| Root peu chargé, 3600 frames | 3,16588 | 0,30838 | 90,26 % [89,52 ; 91,13] |
| Dense, 600 frames, 32 appels retenus | 4,44731 | 0,52664 | 88,05 % [86,49 ; 89,31] |
| Dense, 600 frames, rétention mixte | 3,74257 | 0,51138 | 86,30 % [82,23 ; 87,00] |
| Dense, 3600 frames, ring rebouclé | 4,69431 | 0,91326 | 80,78 % [76,34 ; 84,11] |

**Même opération avec sérialisation JSON :**

| Cas synthétique | Ancien projeté, ms | Agrégé direct, ms | Réduction appariée : médiane [min ; max] |
|---|---:|---:|---:|
| Vide | 0,008123 | 0,007880 | 4,03 % [−39,77 ; 35,55] |
| Root peu chargé, 60 frames | 1,86915 | 0,23941 | 87,51 % [84,79 ; 89,83] |
| Root peu chargé, 100 frames | 3,16315 | 0,23384 | 92,51 % [91,56 ; 93,71] |
| Root peu chargé, 600 frames | 3,17588 | 0,27110 | 91,57 % [90,10 ; 92,03] |
| Root peu chargé, 3600 frames | 3,27643 | 0,40498 | 87,76 % [85,91 ; 88,87] |
| Dense, 600 frames, 32 appels retenus | 4,76497 | 0,83076 | 82,15 % [80,08 ; 84,04] |
| Dense, 600 frames, rétention mixte | 4,01855 | 0,83626 | 79,40 % [75,84 ; 81,08] |
| Dense, 3600 frames, ring rebouclé | 5,09343 | 1,23052 | 76,05 % [74,38 ; 81,48] |

Les cas non vides montrent une réduction dans toutes les paires observées, dans les deux modes. Le cas vide reste de l'ordre de quelques microsecondes et son étendue traverse zéro ; il ne fournit pas une réduction stable. Les tailles JSON avant et après cette optimisation sont identiques pour chaque entrée : l'agrégé direct fait 3296 octets dans le cas peu chargé n60, jusqu'à 7714 dans le cas dense n3600. La réduction de payload avait déjà été acquise en 0.8.19 ; cette expérience isole le travail de construction évité.

Le rapport conserve aussi les durées `legacy_full` et `direct_full`, dont les différences sont beaucoup plus petites et changent de signe selon les répétitions. Aucun seuil d'équivalence n'a été défini pour affirmer une absence générale de régression de performance du mode complet. Son égalité de contenu repose sur l'oracle, pas sur un résultat de timing.

Le [manifeste du benchmark](../runtime/statistics-detail-native-0820/manifest.json), SHA-256 `09c4f85902cd63b2cbef4fc2061404e57c3efac5f904e01ac8a13f7aab7e3825`, atteste `completed=true`, sources et exécutables inchangés. Il référence les trois bruts, l'oracle et le [résumé](../runtime/statistics-detail-native-0820/summary.json), SHA-256 `b4df19dcdd49558826ca1a5c8c7b3eb6dc7ea2ddb2307201518a7e701c2c2ce3`. Le benchmark v100 x64 a pour SHA-256 `6b07804c90a9dd1246b4f855f59466a55356d3732621d023c04131667294df02` ; l'exécutable de l'oracle `d129c9704248ef13acce8e063c02b85f5fe83bbe20ba874eeed6c24699dc6b1e`. Les mesures ont eu lieu le 28 octobre, de 21:54:59 à 21:57:35 UTC.

Cette réduction de durée murale dans un helper synthétique n'est pas un gain équivalent du service complet en jeu : le benchmark n'inclut ni IPC, ni mutation concurrente, ni contention réelle du verrou, ni rendu. Les samples de test ne reproduisent pas la distribution de travail d'une partie. Le parcours et le tri de l'historique, les autres agrégats et la copie du ring restent exécutés.

## Mesures réelles et limites restantes

La compilation principale v100 x64 a produit une DLL de **322 560 octets**, SHA-256 `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e`, et le PDB correspondant de SHA-256 `36a13b93e3e380fe505e159fbb1d696525a6ffdbdf1178c6f3625c745481045d`. La suite Python précédant la capture rapporte **1023 tests réussis en 31,62 s**.

Le [préflight réel](../runtime/direct-0820-preflight.json), SHA-256 `7650c1a6b67e4c111337ec65e2880ee28c397ad5d99b0492d233bd9fa8075fa5`, est terminé : version 0.8.20, Root profilé, trois systèmes et cinq installations de hooks, processus `28932` créé à `1793224737.4120193`. Les sauvegardes validation/copie et l'ancien snapshot conservent leurs **702/702/738 fichiers** conformes aux manifestes ; settings inchangé, gardes de restauration inactives, copie en pause à `404.3333339691162 h`, contrôle de caméra libéré et Edge rétabli. Le watchdog a repris la copie sans erreur d'autoload, avec `session_until=null` et bootstrap explicitement `unlimited` selon la nouvelle autorisation.

Le pilote accepté conserve le plan d'observation : trois conditions, six triades par fréquence, blocs de 5 s, attente neutre préalable de 1 s, mêmes permutations déterministes et bornes distinctes du [protocole](observer-overhead-protocol.md). Les 36 blocs contiennent 660 requêtes, sans saut ni départ anticipé. Le retard de départ maximal observé est 16,695 ms. Les 108 lectures de scène montrent **106 personnages chargés et une ville active**, pause effective et même heure ; la caméra est stable sous verrou. Les 660 réponses conservent la même liaison Root et l'identité de service `23968 / 134376983374120248`.

Le pilote 0.8.19 comportait 78 personnages chargés et une autre position de caméra. Les sessions successives ne constituent donc pas un A/B de version à scène identique. Les comparaisons suivantes sont **internes à la 0.8.20**.

### Réponses et service en jeu

Pour chaque bloc, on calcule la médiane des 5 requêtes à 1 Hz ou des 50 requêtes à 10 Hz. Le tableau donne ensuite la **médiane [minimum ; maximum] des six médianes de blocs**, sans regrouper toutes les requêtes en réplications indépendantes.

| Hz et réponse | Octets JSON par résultat | Latence client MCP, ms | Service natif, ms |
|---|---:|---:|---:|
| 1, full | 35 922,5 [35 862 ; 35 930] | 12,1784 [8,6932 ; 14,7817] | 2,15375 [2,04570 ; 2,26980] |
| 1, aggregates | 3 940,5 [3 936 ; 3 943] | 8,6749 [6,3356 ; 8,9175] | 0,24415 [0,23860 ; 0,27350] |
| 10, full | 35 923,5 [35 886 ; 35 926,5] | 12,1064 [11,2941 ; 13,2945] | 2,11280 [2,05670 ; 2,16130] |
| 10, aggregates | 3 942,25 [3 941 ; 3 943] | 8,8139 [7,8807 ; 8,9369] | 0,24803 [0,24180 ; 0,26025] |

Les différences sont calculées entre les médianes de blocs de la même triade, `aggregates − full` :

| Hz | Service, médiane [min ; max], ms | Réduction du service appariée | Latence client, médiane [min ; max], ms |
|---:|---:|---:|---:|
| 1 | −1,89150 [−2,03120 ; −1,79980] | 88,195 % [87,588 ; 89,488] | −3,74695 [−6,69690 ; +0,00920] |
| 10 | −1,86487 [−1,91935 ; −1,79645] | 88,182 % [87,346 ; 88,805] | −3,83698 [−4,51255 ; −2,35725] |

Le service diminue dans les six paires à chaque fréquence. La latence client diminue dans cinq paires sur six à 1 Hz et dans les six à 10 Hz. L'attente en file varie dans les deux sens ; les différences médianes sont −0,614 ms et −0,307 ms. Les octets sont ceux du résultat réencodé en JSON compact, sans enveloppe MCP/TCP. Le service natif est une durée murale qui exclut notamment sérialisation réseau et transport ; il ne représente pas du CPU exclusif.

### CPU et callbacks : comparaison appariée

Chaque cellule présente **médiane [minimum ; maximum] ; nombre de différences positives sur six**. Les CPU sont des équivalents de processeur logique calculés avec la durée propre à chaque compteur ; un signe positif signifie une consommation supérieure au témoin indiqué. La durée de callback est la moyenne de sa fenêtre retenue, pas du CPU ni un FPS affiché.

| Hz | Traitement − référence | CPU jeu | CPU thread Root | CPU contrôleur | Callback moyen, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | +0,11971 [−0,20589 ; +0,18384] ; 5/6 | −0,00189 [−0,03249 ; +0,06435] ; 3/6 | +0,00304 [−0,00008 ; +0,00602] ; 4/6 | +0,05039 [−0,13860 ; +0,25479] ; 5/6 |
| 1 | aggregates − baseline | −0,02390 [−0,26433 ; +0,18868] ; 3/6 | +0,01922 [+0,00084 ; +0,04576] ; 6/6 | +0,00297 [−0,00294 ; +0,00884] ; 4/6 | +0,02229 [−0,06156 ; +0,31443] ; 4/6 |
| 1 | aggregates − full | −0,08986 [−0,43036 ; +0,06855] ; 2/6 | +0,00332 [−0,01860 ; +0,04987] ; 3/6 | −0,00007 [−0,00895 ; +0,00891] ; 1/6 | −0,02352 [−0,09470 ; +0,16971] ; 3/6 |
| 10 | full − baseline | +0,08573 [−0,02812 ; +0,25000] ; 5/6 | +0,02053 [−0,01283 ; +0,09458] ; 5/6 | +0,01500 [+0,00586 ; +0,02730] ; 6/6 | +0,11715 [+0,02844 ; +0,15663] ; 6/6 |
| 10 | aggregates − baseline | −0,01876 [−0,09332 ; +0,05265] ; 3/6 | +0,03701 [−0,01067 ; +0,05171] ; 5/6 | +0,00764 [−0,00283 ; +0,01232] ; 5/6 | +0,11369 [−0,15103 ; +0,38784] ; 4/6 |
| 10 | aggregates − full | −0,10886 [−0,30774 ; +0,01811] ; 1/6 | −0,01585 [−0,04287 ; +0,04914] ; 2/6 | −0,00600 [−0,02417 ; +0,00645] ; 2/6 | −0,01812 [−0,30766 ; +0,26793] ; 2/6 |

À 10 Hz, les six comparaisons `full − baseline` montrent encore un intervalle de callback plus long. Les comparaisons `aggregates − full` restent mixtes pour les callbacks et le CPU, malgré les réductions concordantes du service. Le CPU processus baisse dans cinq paires sur six à 10 Hz, mais cette petite série n'établit ni significativité, ni causalité, ni bénéfice universel. Le témoin reste instrumenté et l'ordre équilibré n'est pas randomisé.

Les portées sont distinctes : blocs de requêtes **5,00048–5,01641 s**, compteurs processus **5,06754–5,10665 s**, thread Root **5,06903–5,11832 s**, contrôleur **5,13599–5,19429 s**. Les fenêtres agrégées contiennent **694–745 callbacks**, toutes obtenues en une requête avec n conservé et sous le plafond de 3600 ; leurs intervalles cumulés vont de **5,13974 à 5,19686 s**. Les endpoints et leur sérialisation se trouvent hors de la fenêtre CPU du jeu, sans exclure un effet sur le bloc suivant.

Le CPU du serveur MCP séparé reste indisponible ; le CPU contrôleur n'est donc pas le coût complet de collecte. Sept threads ne sont pas observés à l'endpoint final de cinq blocs, tandis que Root reste identifié. Le résidu signé processus moins somme des threads calculables va de **−0,203125 à +0,21875 s**. Il est conservé sans clamp, sans attribution à une fonction. Les compteurs quantifiés, lectures séquentielles et variations de la machine empêchent de confondre leurs valeurs avec la durée murale du service.

### Restitution et preuves réelles

L'[audit final indépendant](../runtime/direct-0820-final.json) est terminé : même processus `28932`, trois lectures finales en pause à la même heure, `free_camera=false`, contrôle libéré et Edge restitué à `true`. Les fichiers **702/702/738**, les réglages et les gardes sont conformes. Les deux helpers identifiés `21020 / création 1793224737.2479062` et `40676 / création 1793224737.2090707` sont présents ; le watchdog est frais, sans erreur d'autoload ni de publication. Ces identités décrivent l'audit et devront être revérifiées avant tout arrêt futur.

Les déplacements de caméra observés avant verrou, après libération et entre les trois lectures finales sont nuls dans cette acquisition. Le contrôleur ne restaure toujours pas explicitement les coordonnées initiales : ce résultat ponctuel ne promet pas l'absence de dérive lors d'un prochain retour à Edge. Les sources propres au contrôleur, la DLL et les fichiers protégés sont inchangés pendant la capture.

| Preuve réelle | SHA-256 |
|---|---|
| [Capture acceptée](../runtime/scenarios/observer-overhead-20261028T220047030270Z.json), 27 912 370 octets | `f387e96e312fbc0babef82e03b7683d4c934451468abef99cc74a06cb2db6649` |
| [Rapport analysé](../runtime/observer-0820-seed0.json), 94 394 octets | `4b696a62b6b5fbcbfbefefcd2745fa565b7794ba0a6de762f418143ca9f1b34a` |
| [Preuve des deux rejeux](../runtime/observer-0820-replay-proof.json) | `8e73dd1f7a55338c4492ec07800a1f9c8fde9449ede910059d4e78f1d0ce5425` |
| [Contrôles supplémentaires et paires de requêtes](../runtime/observer-0820-supplemental.json) | `2bb68f954386fe0646eea9d70c43e3b5a4b2493e3f257a1da6791af4f2e78c7a` |
| [Audit final](../runtime/direct-0820-final.json) | `45295a9b29f8c89518f5a3d05d86dd020d26835491124afb29452b2d4545ec1f` |

Les graines Python `0` et `8675309` donnent le même rapport octet par octet. Ce sont deux analyses du même brut, pas deux acquisitions. La preuve de rejeu conserve les SHA des sources utilisés, notamment contrôleur `f457732bf39ffffd2b0a68f76b78a9fdb5211a8eeefc29f1729f88e52c7fa33f` et analyseur `0c1285da87bc2e0ea88cacc74e90fcbb0ea69ae7405b0335dd40b918a0a18d2e`.

Pour rejouer l'analyse hors jeu, depuis la racine du projet, choisir un nom de sortie neuf. La capture est contrôlée par SHA, la version doit être explicitement 0.8.20 et le fichier de sortie existant ne sera pas écrasé :

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe mcp-server/analyze_observer_overhead.py `
  runtime/scenarios/observer-overhead-20261028T220047030270Z.json `
  --expected-version 0.8.20 `
  --expected-sha256 f387e96e312fbc0babef82e03b7683d4c934451468abef99cc74a06cb2db6649 `
  --output runtime/observer-0820-replay-new.json
```

Le benchmark prouve une réduction du travail de construction sur les instantanés testés ; le pilote réel confirme un service agrégé plus court que le service complet de la même DLL en pause. La différence de scène avec 0.8.19, l'absence de randomisation, les fenêtres distinctes et le CPU MCP manquant restent explicites. Aucun gain FPS ni réduction générale du CPU moteur n'est déduit de ces seuls résultats.
