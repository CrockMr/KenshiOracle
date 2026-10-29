# Observations RIP actives sans élévation — 28 octobre 2026

Le PSS léger fonctionne aussi pendant la simulation à Heng : pilote de12 captures, série de60 puis contrôle de cadence de60, tous terminés avec restauration. **Aucun administrateur, clone mémoire, débogueur attaché ni nouveau hook.** Le plugin reste0.8.9, v100 x64,17 outils/trois sondes. Ces observations renseignent des adresses utilisateur et modules ; elles ne donnent ni des piles, ni des pourcentages CPU par fonction.

## Acquisition et reproductibilité

`tests/live_instruction_active.py` sélectionne les quatre identités les plus consommatrices du relevé CPU0.8.9 déjà terminé, vérifie le même PID/chemin/commande/création et prépare Heng depuis KenshiProbe_test. L’identité native du processus est lue avec GetProcessTimes, indépendamment des arrondis flottants. Chaque capture doit retrouver exactement les TID et créations FILETIME demandés. PSS utilise flags0x180/contextes0x100003, sans VA clone ni lecture de piles. Les registres sont copiés avant libération du snapshot ; les modules sont vérifiés avant/après et entre captures.

Le contrôleur borne la série à120 captures et chaque appel complet à250 ms. Les essais réalisés demandent des délais aléatoires0,8..1,2 s, graine conservée. La première série lisait la scène MCP juste avant la capture ; la seconde place le délai **après** cette lecture pour réduire une éventuelle synchronisation avec le thread principal. Les délais réellement conservés entre scène et capture sont0,813308..1,220051 s dans cette seconde série. Ce changement ne prouve pas que tout biais de PSS ou d’ordonnancement est éliminé.

| Essai, dossier sous runtime/instruction-active | Captures | Helper total | Max helper | CPU processus moyen |
|---|---:|---:|---:|---:|
| 20261028T130858520293Z, pilote |12|108,557 ms|10,437 ms|2,389649 processeurs logiques|
| 20261028T131248766820Z, scène puis capture |60|541,348 ms|12,790 ms|2,283443|
| 20261028T131640088252Z, scène puis délai puis capture |60|550,530 ms|12,619 ms|2,160076|

Ces temps helper comprennent ouverture, inventaires de modules, capture, copie et nettoyage. Ils ne sont **pas** la durée exacte de suspension de la cible. L’appel PssCaptureSnapshot seul cumule106,044 ms dans la dernière série ; cela ne mesure pas davantage une pause globale du jeu. Le contrôleur et ses requêtes ont eux-mêmes un coût, non isolé causalement. Aucun test ni compilation pendant les acquisitions.

Chaque dossier contient controller.json. SHA-256 respectifs :

- Pilote : **099ad389c675f3a230de7f651a3dad528e392667a06dd732c22e19336c2e313e**.
- Série initiale : **7c85baacd133854568c3d8fece4a7a1b69f9f396c64b73f99aa945c5307a5881**.
- Série avec séparation : **3d8cab8cf198d92ef47033ad7f56ab79f60c12d1a66fd196608a12c90657875d**.

`mcp-server/analyze_instruction_active.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER` rejoue hors jeu les identités/contextes/modules, comptes, durées, ordre de scènes, caméra/vitesse, progression, compteurs CPU natifs et restitution attestée. Il refuse un fichier de sortie existant. Rapports : `runtime/instruction-pilot-active-analysis.json`, `runtime/instruction-series-active-analysis.json` et `runtime/instruction-series-separated-analysis.json`. Leurs comptes de base restent reproductibles ; les métadonnées de cadence supplémentaires ne sont présentes que dans le dernier rapport. La préservation des fichiers est une attestation du contrôleur conservée dans ces bruts ; l’audit final recalcule séparément leurs manifestes réels.

**505 tests passent en21,18 s**, dont corruption des comptes/cache CPU, identité réutilisée, module contradictoire, création manquante, ordre de capture, caméra, vitesse, horloge de restauration et faux délai de séparation. Les tests réseau nécessitent l’accès local hors bac à sable ; cela n’accorde aucun privilège administrateur Windows.

## Ce que montrent les60 observations séparées

Processus **39204/création FILETIME134376639120505830**, exécutable vérifié. Fenêtre processus64,610 s,139,562500 s CPU, moyenne2,160076 processeurs logiques. Résidu signé **+0,093750 s**, aucune identité de thread omise ; résidu conservé sans affectation à un module. La scène progresse de0,592155457 h sur64,601911 s ; inventaires complets399→440 aux bornes. Population et streaming évoluent.

| Identité TID/création FILETIME | CPU du thread entier | Adresses observées par module, sur60 |
|---|---:|---|
|35744/134376639120505844, principal/rendu|52,203125 s,0,808173 processeur logique|Ogre22, ntdll13, D3D119, RenderSystem7, MyGUI5 ; CRT, moteur, terrain et pilote graphique1 chacun|
|32156/134376639240826668, fonction non attribuée|8,015625 s,0,124092|ntdll56, Plugin_Terrain3, Ogre1|
|13132/134376639240828501, rôle SDK non rendu déjà vérifié|19,265625 s,0,298257|ntdll48, moteur12, chacune des12 RVA moteur observée une fois|
|12820/134376639144112817|10,890625 s,0,168601|ntdll54, pilote graphique4, win32u2|

Les normalisations de thread utilisent leurs propres bornes64,594 s, distinctes de celles du processus. Les observations de modules ne sont pas des parts CPU. Un contexte utilisateur dans ntdll ne prouve ni l’inactivité permanente, ni la fonction appelante, ni le lieu d’exécution en mode noyau. Dans la série précédente,32156 avait60 contextes dans ntdll tout en consommant14,046875 s CPU ; il serait incorrect d’en déduire zéro travail. La séparation RPC/capture change les observations et la scène évolue aussi : aucune différence CPU entre ces séries n’est attribuée causalement à ce seul changement.

Le contrôleur conserve également les adresses non associées à un module : une telle observation sur le thread principal dans la première série reste inconnue, sans rapprochement arbitraire au module voisin. Les noms SDK/BirdManager historiques ne sont pas transférés à32156 à partir de son TID ou du nom d’un module.

## Restitution et prochaine mesure

Les trois essais reviennent à **404,3333339691162 h**, copie en pause et contrôle caméra relâché. Tous les nettoyages PSS sont vérifiés, sauvegardes et settings conservés. L’audit indépendant `runtime/instruction-active-final.json` contrôle à nouveau les702/702/738 fichiers source/copie/snapshot, DLL, rôles, watchdog et échéance. Aucun helper de capture persistant ; watchdog/bootstrap restent bornés au28 octobre22 h15 UTC.

La série élargit les lieux d’exécution observés, sans isoler un nouveau goulot ni justifier un quatrième hook. La prochaine priorité est une condition lourde à x5 avec vitesse/horloge effectives, fenêtres adaptées au nombre réel de frames, inventaires complets et restauration. Une éventuelle annotation d’adresse doit conserver le build exact, la liaison SDK vérifiée et les régions ambiguës ; ne pas remplacer ces preuves par le symbole le plus proche. Aucun algorithme moteur modifié ni gain de performances démontré.
