# Combat depuis un snapshot à horizon simulé commun

Quatre parcours **x1, x5, x5, x1** ont rechargé le même snapshot de deux PNJ hostiles à Mongrel, sans nouveau tirage de personnages. Chaque départ a des valeurs identiques pour la santé, les positions, l'horloge et la caméra observées. Les résultats médicaux divergent néanmoins, y compris entre parcours à même vitesse. Ce protocole permet de mesurer un horizon d'horloge commun ; il ne fournit pas encore un travail de combat identique pour comparer un coût marginal ou un gain d'optimisation.

Plugin **0.7.5 inchangé, v100 x64, 17 outils MCP, trois hooks de systèmes**. Les commandes passent par une vraie session MCP stdio. Aucun nouveau hook, déploiement, arrêt de processus, PNJ créé ou fichier de sauvegarde écrit pendant cette campagne.

## Preuves et reproduction

- Brut : `runtime/scenarios/snapshot-horizon-20261028T033243Z.json`, SHA-256 **02c0864cfe331d5fcc02ce814ce9b20740ec610522c5aa878a36f10c0a986f42**.
- Synthèse : `runtime/snapshot-horizon-analysis.json`, empreinte du brut conservée.
- Contrôle final indépendant : `runtime/scenarios/snapshot-horizon-075-final.json`.
- Snapshot : `KenshiProbe_test_scene_20261028T022539600581Z`, manifeste de 738 fichiers dans la preuve de création ; référence visible issue de `snapshot-paused-settling-075.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_snapshot_horizon.py --snapshot-proof runtime/scenarios/snapshot-20261028T022539600581Z.json --baseline-proof runtime/scenarios/snapshot-paused-settling-075.json
& ./.venv/Scripts/python.exe mcp-server/analyze_snapshot_horizon.py runtime/scenarios/snapshot-horizon-20261028T033243Z.json --output runtime/snapshot-horizon-analysis.json
```

La première commande nécessite que le plugin courant possède encore ce snapshot. Cette association en mémoire ne survit pas au redémarrage ; un refus ne doit pas être contourné par un nouveau tirage présenté comme identique. La seconde commande réanalyse uniquement les fichiers. Le script refuse désormais de commencer dans les trente dernières minutes, vérifie une marge avant chaque parcours et garde du temps pour restaurer la copie initiale dans finally.

## Bornes observées

L'horizon demandé est **0,5 heure de jeu**. Le contrôleur lit la scène toutes les 0,2 seconde réelle, puis met en pause au franchissement. Les heures réellement observées et leur dépassement sont conservés, sans corriger artificiellement la durée.

| Ordre | Vitesse | Heures de jeu observées | Secondes réelles, horloge | Secondes CPU du processus | Population au départ | Population pendant les lectures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | x1 | 0,501579 | 55,015 | 123,281250 | 156 | 156–273 |
| 2 | x5 | 0,508999 | 11,535 | 23,390625 | 176 | 186–292 |
| 3 | x5 | 0,508982 | 11,507 | 24,437500 | 156 | 156–344 |
| 4 | x1 | 0,501266 | 55,104 | 119,187500 | 162 | 162–305 |

Le dépassement atteint environ **1,80 % de l'horizon cible** à x5 contre 0,25–0,32 % à x1. Les secondes réelles par heure de jeu ont des médianes de 109,807 à x1 et 22,635 à x5, soit un rapport descriptif d'environ 4,85. Cet intervalle court inclut activation, streaming et requêtes ; il n'est pas directement comparable aux fenêtres stabilisées en ville des anciennes campagnes.

Le CPU est mesuré sur l'intervalle englobant, légèrement différent de celui de l'horloge : 55,016 ; 11,547 ; 11,500 ; 55,094 secondes réelles. Le coût inclut rendu, tous les modules, commandes, relevés OS et bornes en pause. Les résidus signés processus moins somme des threads sont respectivement **+0,031250 ; +0,093750 ; −0,093750 ; +0,015625 seconde CPU** ; aucun thread n'est exclu pour identité manquante dans ces quatre relevés. La quantification et la lecture séquentielle restent visibles. L'absence d'un worker de navigation dans les appels lents retenus d'un parcours ne signifie pas CPU de navigation nul.

## Résultats médicaux

Pour l'acteur `KenshiProbeFight_1_0` :

| Parcours | Variation de sang finale | Variation de somme flesh finale | Inconscient à la dernière lecture | Première inconscience observée, secondes réelles | Heures simulées à cette observation |
| --- | ---: | ---: | --- | ---: | ---: |
| x1, ordre 1 | −45,944 | −216,602 | oui | 18,796 | 0,170565 |
| x5, ordre 2 | −29,814 | −150,211 | non | aucune observée | — |
| x5, ordre 3 | −27,853 | −152,398 | oui | 3,515 | 0,146616 |
| x1, ordre 4 | −18,750 | −95,440 | oui | 16,563 | 0,148819 |

Ces temps indiquent la première **observation**, pas l'instant exact d'un événement. L'autre acteur perd respectivement 15,471 ; 0 ; 0 ; 30,086 de somme flesh. Aucun décès de la cohorte n'est observé en fin de parcours. Ne pas convertir ces différences en nombre de coups ou en nombre de tâches terminées.

Le deuxième parcours contient neuf lectures de cible extérieure à la cohorte ; les autres n'en contiennent pas. Leur absence dans l'échantillon ne démontre pas un combat isolé. Les populations initiales et leurs trajectoires varient ; santé et pose des deux acteurs ne couvrent ni tous les états IA/équipements ni tous les personnages du monde. Les mêmes gardes visibles à x1 donnent déjà des dommages très différents. Rien ici ne permet d'attribuer causalement les différences de dommages à la vitesse.

La charge des autres applications n'est pas fixée ni quantifiée. Une suite pytest de quatre secondes a notamment été exécutée pendant le premier parcours x1. Les relevés mesurent toujours le seul processus de jeu, mais cette concurrence limite davantage toute comparaison de performances entre conditions. Les deux répétitions par vitesse restent descriptives.

## Correction du contrôleur et gardes

Le pilote `snapshot-horizon-20261028T033127Z.json` s'arrête avant la mesure, car **set_game_speed retire elle-même la pause**. La copie, le snapshot et les préférences ont été restaurés/conservés ; ce pilote reste dans les preuves, sans être compté comme parcours terminé. La signature publique `GameWorld::setGameSpeed(float,bool)` a été vérifiée dans GameWorld.h ; son effet de dépausage est observé nativement, pas supposé à partir du nom du booléen.

La correction place l'horloge et le début CPU **avant** cette commande, puis vérifie la vitesse effective à chaque lecture. Les quatre parcours suivants passent les gardes de départ avec zéro différence médicale, spatiale et d'horloge ; aucune tolérance n'a été élargie. L'ancien rejet vertical de 1,897339 unité reste valide dans les autres preuves : cette campagne ne l'efface pas. Le contrôleur refuse également noms dupliqués, valeurs non finies, formes médicales incomplètes, caméra déplacée, perte d'acteur ou changement de PID.

**145 tests Python passent en 3,94 s.** Les tests supplémentaires couvrent les gardes, exclusion des parcours incomplets, dépassement de l'horizon, identité du processus et distinction des deux horloges pour les observations médicales.

## État laissé et prochaine étape

PID 19892/date de création inchangés, copie initiale rechargée, caméra de référence en mode normal, pause active, Edge scrolling=true et contrôle temporaire relâché. Les **702 fichiers de KenshiProbe_validation et les 702 de KenshiProbe_test**, ainsi que les **738 fichiers du snapshot**, correspondent à leurs manifestes. settings.cfg est identique octet pour octet après campagne ; les gardes de restauration restent false. Watchdog sain, zéro erreur de publication, borne finale inchangée **28 octobre 22 h 15 UTC**.

Le prochain diagnostic CPU par piles reste conditionné au pilote Windows administrateur déjà demandé ; aucune nouvelle trace n'est apparue. En parallèle, améliorer l'observation de l'environnement et des états non couverts, puis définir une scène et un critère de travail comparables avant toute optimisation du moteur. Répéter immédiatement le même quartet n'établirait pas une cause. Aucun gain d'optimisation n'est annoncé.

Suivi : environment-preflight-measurements.md confirme ensuite, sans simulation de combat, une variation de 172 à 147 personnages dans la liste de mise à jour. Un garde d'environnement est maintenant ajouté au contrôleur pour les futurs parcours ; il ne faisait pas partie du quartet historique décrit ici. Son rejeu sur les nouveaux bruts accepte le premier environnement et rejette le second. Aucun résultat historique n'est reclassé comme comparaison contrôlée de tout le monde du jeu.
