# Statistiques agrégées — validation 0.8.19

**Le mode `aggregates` conserve toutes les frames demandées tout en réduisant le volume des réponses.** Dans un combat de 40 PNJ à Mongrel, les quatre fenêtres et leurs contextes de 3600 frames ont chacun été obtenus en une requête, avec des réponses compactes d’environ **4,7 Ko**. Cette évolution répond au plafond de réponse qui pouvait imposer de réduire la fenêtre collectée.

Le plugin construit toujours la réponse complète avant d’en retirer deux listes. Le résultat démontre une réduction du volume transmis et la conservation des fenêtres demandées ; **le calcul des statistiques reste inchangé, sans gain de CPU moteur ou de FPS démontré**. Les mesures de combats successifs, avec des populations différentes, ne constituent pas un A/B entre versions.

## Contrat et compatibilité

`get_frame_stats(n, detail='full')` garde son comportement par défaut. L’omission de `detail` et la valeur explicite `full` suivent le chemin complet historique ; aucune métadonnée de projection n’est ajoutée. La valeur `aggregates` est optionnelle, les autres valeurs ou types sont rejetés. Le MCP conserve **17 outils**.

`plugin/StatisticsDetail.h` applique la projection après construction de `stats(n)`. Les tableaux `per_frame` et `navmesh_slow_calls` deviennent explicitement **null**, accompagnés de :

```json
"statistics_detail": {
  "mode": "aggregates",
  "per_frame_rows_omitted": 100,
  "navmesh_slow_rows_omitted": 7
}
```

Les nombres illustrent la première fenêtre de cette campagne. Les agrégats, bornes, identités et indicateurs de rétention restent ceux de la réponse initiale. L’omission demandée est distinguée de la troncature native : la série individuelle ne garde historiquement que les 100 dernières lignes et le registre des appels lents possède sa propre capacité. Une liste omise ne signifie ni zéro appel ni absence de travail.

`mcp-server/statistics_detail.py` vérifie les comptes, bornes, indicateurs et null explicites, y compris le tampon vide. Les analyseurs peuvent ignorer une validation de lignes indisponibles sans inventer ces observations. Les agrégats de navigation restent disponibles ; les rôles dépendant des lignes d’appels lents ne sont pas reconstruits dans ce mode. La campagne déclare `navigation_detail_roles_available=false`.

**88 assertions natives v100 x64** contrôlent notamment la projection d’une même entrée et la conservation exacte des agrégats. La suite finale compte **892 tests Python réussis en 23,21 s**. Un premier passage comportait neuf échecs dus aux fixtures synthétiques dépourvues de métadonnées de navigation exigées par le validateur ; seules ces fixtures ont été complétées. Ce n’était pas un défaut observé dans le jeu.

Le smoke réel MCP valide les trois formes : défaut, `aggregates`, puis `full` explicite. Pour n60, la réponse complète observée fait **36671 octets**, la compacte **4701 octets**. Ces requêtes adjacentes portent sur les frames 469–528, 471–530 et 472–531 : elles ne prouvent pas une égalité des agrégats d’une même fenêtre figée. Cette égalité sur entrée identique vient des tests natifs. Le contrôle de cadence avant campagne observe **71 frames sur 512,088 ms**, avec une moyenne des dix dernières de **7,322660 ms** ; il ne mesure pas le coût isolé de la projection.

## Campagne à Mongrel

La version reste **v100 x64**, trois systèmes profilés charsUpdate/findPath/Root, avec trois detours dédiés et deux services, soit **cinq installations effectives**. Root utilise l’export sans argument déjà vérifié, CPU optionnel activé. Aucun nouveau hook ou algorithme de jeu.

La campagne recharge la copie KenshiProbe_test sous protection, prépare Mongrel puis 20 paires de combattants, et observe quatre fenêtres de **5/5/10/10 s demandées à vitesse x5**. Le contexte dispose d’un historique de 3600 frames avant son emploi. La caméra reste sous contrôle pendant la mesure ; la copie est rechargée en pause et le contrôle libéré au nettoyage final.

| Fenêtre | Frames demandées et reçues | Octets des statistiques | Frames du contexte | Octets du contexte | Lignes individuelles omises | Lignes de navigation omises, statistiques / contexte |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 221 | 4731 | 3600 | 4742 | 100 | 7 / 20 |
| 2 | 565 | 4705 | 3600 | 4744 | 100 | 0 / 20 |
| 3 | 1097 | 4713 | 3600 | 4759 | 100 | 0 / 20 |
| 4 | 1053 | 4711 | 3600 | 4741 | 100 | 0 / 20 |

Chaque demande réussit à sa première tentative, sans diminution de n. Les tailles sont celles du JSON compact réencodé et vérifié par l’analyseur, pas le nombre exact d’octets TCP/MCP. Le plafond natif de 64 Kio reste inchangé. Les contextes de 3600 frames sont des fenêtres glissantes plus larges que les quatre périodes de mesure ; leur contenu ne doit pas être attribué entièrement au combat d’une seule période.

Les **40 acteurs** restent suivis sur **110 observations**, avec **34 acteurs présentant un signal de blessure**, jusqu’à **neuf inconscients**, aucun mort observé dans les fenêtres et **35 observations de cible extérieure**. Les variations médicales ne donnent ni nombre de coups ni attribution certaine à un attaquant.

| Fenêtre | Root mural moyen ms/frame | Max Root ms | Intervalle moyen ms | p99 intervalle ms | CPU utilisateur Root ms | CPU noyau Root ms | Population observée |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 23,292300 | 131,651900 | 23,267331 | 124,8890 | 2406,250 | 468,750 | 178–326 |
| 2 | 9,347930 | 25,375200 | 9,352127 | 14,1701 | 3515,625 | 546,875 | 322–336 |
| 3 | 9,331531 | 18,227700 | 9,336716 | 14,1052 | 6296,875 | 1078,125 | 325–375 |
| 4 | 9,665162 | 18,035200 | 9,670818 | 15,2680 | 6234,375 | 1437,500 | 335–401 |

Root compte respectivement 221/565/1097/1053 appels, tous avec compteurs CPU disponibles. Les sommes CPU sont **2875 / 4062,5 / 7375 / 7671,875 ms**. La forte variation initiale accompagne ici une population croissante ; sa cause exclusive n’est pas établie. Ces valeurs ne prouvent pas un coût marginal par PNJ ou une accélération comparée à un combat antérieur.

Les appels Root sont inclusifs : travail original, code de mesure et callbacks, sondes ou services imbriqués. L’admission des appels terminés dans les buckets, les instantanés de scène et les endpoints CPU OS ont des bornes différentes. La moyenne Root peut donc légèrement dépasser la moyenne des intervalles de callbacks sans permettre d’en déduire une attente ou une incohérence. Aucune soustraction murale/CPU ni fraction de couverture exclusive n’est interprétée.

## CPU, identités et précision

Root rejoint **T18784 / création FILETIME134376935315380313**, présent aux deux endpoints CPU et identifié comme thread principal/service rendu aux bornes. Son CPU entier vaut **2,9375 / 4,09375 / 7,40625 / 7,703125 s** dans des fenêtres OS de **5,250 / 5,328 / 10,281 / 10,219 s**. Ces compteurs du thread entier ne sont pas ceux des seuls appels Root retenus.

Le processus consomme **9,53125 / 12,671875 / 25,734375 / 22,609375 s CPU**, soit **1,815476 / 2,378355 / 2,503100 / 2,212484 processeurs logiques**. Les résidus signés processus moins threads calculables sont **−0,109375 / +0,078125 / +0,078125 / −0,09375 s**. Deux threads, T31840 et T43484, ne sont pas observés à l’endpoint final de la première fenêtre ; T20104 manque à l’endpoint initial de la troisième. Ils restent omis, sans consommation inventée. L’identité Root est vérifiée dans les quatre fenêtres.

Le démarrage de cette DLL observe **0,235001 µs par lecture CPU**. La [calibration distincte](root-cpu-measurements.md) du helper propre reste référencée dans la capture, avec son SHA. Elle n’est pas une garantie de résolution ou de coût du hook en jeu. L’unité de 100 ns ne signifie pas précision de 100 ns ; les zéros et deltas quantifiés supérieurs au temps mural d’un petit appel sont conservés sans clamp.

## Provenance et reproduction

Capture complète : **runtime/scenarios/aggregate-battle-20261028T204139893880Z.json**, SHA256 **8a69d77558235340f8d2cf51a875b6ab379d054f326ee0af58f50ec9f427662f**. Analyse spécialisée : `runtime/aggregate-0819-analysis.json` ; résumé : `runtime/aggregate-0819-summary.json`. Le rejeu vérifie les contrats Root/CPU, les bornes, le combat et la restauration, ainsi que la conservation de chaque n demandé en une requête et les tailles compactes recalculées.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_aggregate_battle.py runtime\scenarios\aggregate-battle-20261028T204139893880Z.json --expected-sha256 8a69d77558235340f8d2cf51a875b6ab379d054f326ee0af58f50ec9f427662f --output runtime\nouveau-rapport-aggregates.json
```

Le manifeste **docs/performance-cohorts-aggregates.json**, SHA256 **d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9**, porte le diagnostic à **neuf cohortes et trente fenêtres**. Rapport `runtime/performance-cohorts-aggregates-v1.json`, SHA256 **05c42fde3ee3315b0c38608b21ab7b9afe68544713ecf348c3596790b72433e7** ; Markdown homonyme SHA256 **7394cb0c27843b94b8396dfb8e272dea70e76c4d6405407a3548cd5e91795bbd**.

La preuve `runtime/aggregate-cohorts-replay-proof.json` conserve deux rejeux octet-identiques sous graines différentes, l’égalité de l’analyse spécialisée et les huit anciennes métriques strictement identiques. Seule la provenance SHA du source `analyze_root_battle.py` évolue avec son paramètre de version attendue, 0.8.18 par défaut et 0.8.19 explicitement. Le rapport historique à huit cohortes n’est donc pas annoncé octet-identique après cette évolution ; ses captures et son manifeste sont préservés.

## Déploiement et restitution

Déploiement archivé sous **crashes/20261028T203850754003Z-deployment-0819**. DLL propre de **322560 octets**, SHA256 **796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3** ; PDB de **10406912 octets**, SHA256 **0d2b29b027345d0b0af8294cae87ae9d2c747d1d92c547a77ffcdb347f0c82de**. Les binaires, captures et fichiers du jeu restent hors Git.

L’audit indépendant **runtime/aggregate-0819-final.json** vérifie le jeu **32156 / créationUnix1793219931.5380297**, exécutable et commande du projet. La copie est restaurée en pause, multiplicateur zéro, à **404,3333339691162 h**, caméra normale, contrôle temporaire relâché, Edge restitué et bataille inactive. Les **702/702/738 fichiers** de validation/copie/ancien snapshot correspondent aux références, settings inchangé, deux gardes de restauration false, watchdog frais sans erreur et WPR inactif. La dernière lecture agrégée n3600 réussit en une requête de **3954 octets**.

Les helpers observés sont **38176 / créationUnix1793219931.3160987** et **43920 / créationUnix1793219931.3597145** ; leurs identités devront être revérifiées avant un arrêt. Ces constats décrivent cet audit, pas un état futur garanti. L’échéance autonome reste **le 28 octobre à 22 h 15 UTC / 23 h 15 Paris**.
