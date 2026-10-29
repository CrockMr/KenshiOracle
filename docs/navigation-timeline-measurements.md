# Chronologie des recherches de chemin lentes à Heng

Les deux captures à vitesse x5 montrent une rafale initiale d'appels `findPath` d'au moins 10 ms, puis aucune autre complétion dépassant ce seuil dans la fenêtre retenue. Cette conclusion porte sur les appels lents : la répartition temporelle des recherches rapides reste inconnue. Elle ne prouve pas un régime stationnaire du moteur.

## Résultats hors jeu

| Capture | Frames de la fenêtre | Tous les appels | Détails lents retenus | Répartition sur quatre quarts de frames | Enveloppe QPC des appels retenus |
|---|---:|---:|---:|---|---:|
| Heng x5, 0.8.9 | 501422–504179 (2758) | 778 | 7 sur 7 | 7 / 0 / 0 / 0 | 1997,5414 ms |
| Heng x5, 0.8.10 | 11260–14091 (2832) | 1227 | 8 sur 8 | 8 / 0 / 0 / 0 | 1393,3195 ms |

Les quarts découpent les indices de **frames**, pas quatre durées égales. Les enveloppes vont du premier départ QPC à la dernière fin reconstruite par `started_qpc_ms + elapsed_ms`. Elles ne sont ni une somme CPU, ni toute l'activité de navigation. Les horloges QPC natives et monotones du lecteur CPU restent séparées.

Les complétions lentes occupent respectivement les frames **501516–501771** et **11511–11681**. Tous ces appels sont hiérarchiques et renvoient `false`. Leurs sommes murales inclusives sont **1179,9232 / 1391,0739 ms** ; les sommes de compteurs CPU quantifiés, **1078,125 / 1359,375 ms**. Aucun ratio de couverture exclusive avec le thread entier n'en est déduit.

Les couples XYZ et paramètres capturés sont tous distincts : **7 et 8 groupes**, alors que les paires `start_key/goal_key` n'en forment que **6 dans chaque capture**. Des clés égales ne décrivent donc pas une requête géométrique identique. La projection descriptive conserve radius, water, hierarchical et la taille de sortie initiale ; le brut conserve aussi les clés et les quatre composantes vectorielles. La quatrième composante n'est pas assimilée à une coordonnée spatiale. La validité d'un cache et les causes des retours `false` restent inconnues.

Le contexte de 3600 frames du second relevé contient dix appels lents : les huit mêmes, plus deux complétions hors fenêtre, aux frames **10925 et 10963**. L'analyse déduplique les observations par PID, création du processus, TID et départ QPC. Elle ne somme pas le contexte et la fenêtre principale. Sur les trois phases réunies, les deux captures contiennent respectivement **8 et 10 appels uniques**, avec leur provenance conservée.

Les lignes d'appels ne portent pas la création du thread. Un TID concordant avec une durée de vie stable aux deux bornes CPU est signalé comme **candidat**, sans prétendre prouver une association exacte appel/FILETIME. Les données de processus et threads sont recalculées depuis les compteurs bruts avant lecture des résultats.

## Reproduction et preuves

Analyseur : `mcp-server/analyze_navigation_timeline.py`. Il exige une capture complète restaurée, le mode détaillé et un SHA attendu ; il refuse un fichier de sortie existant. Les réponses `aggregates`, notamment celles du combat 0.8.19, sont explicitement indisponibles pour cette chronologie, jamais converties en zéro appel.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_navigation_timeline.py runtime\scenarios\pause-cpu-x5-adaptive-20261028T133051Z.json --expected-sha256 f1d846061c4f8f905481b82d54303e9e9c7a1d87605d315879ab666a5a0667c3 --output runtime\nouvelle-navigation-089.json
& .\.venv\Scripts\python.exe mcp-server\analyze_navigation_timeline.py runtime\scenarios\pause-cpu-x5-adaptive-20261028T140511Z.json --expected-sha256 60d74111457fa6d932efd5bf41d19fbf8fee96c3c497f0e57ba535ec8355f34a --output runtime\nouvelle-navigation-0810.json
```

Les deux graines Python **0 et 8675309** produisent des rapports identiques octet par octet. Preuve : `runtime/navigation-timeline-replay-proof.json`.

- Rapport 0.8.9 : `runtime/navigation-timeline-089-seed0.json`, SHA **5e7c695f95e3e8a7fd3b3f94d4889748c2852465d06102b963f8fb71ece9b16f**.
- Rapport 0.8.10 : `runtime/navigation-timeline-0810-seed0.json`, SHA **2c7d48aca1d1010e26f96f0a5472aec62abc39effbc4ce1021bc0e7e5e3dc360**.
- **22 tests ciblés passent**, dont identité, QPC, contradictions de doublons, rétention, mode compact, SHA et refus d'écrasement.

La sélection est complète au seuil déclaré dans ces deux fenêtres, sans troncature de slowcalls. Les seules 100 lignes `per_frame` de fin ne permettent cependant pas de reconstruire tous les appels rapides par sous-période. Une acquisition future ne se justifie que pour une hypothèse précise qui exige cette information. Aucune nouvelle capture, DLL, sonde ou API du jeu n'a été nécessaire pour ce résultat.
