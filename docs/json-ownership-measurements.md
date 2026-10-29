# Transfert de propriété des réponses JSON — 0.8.13

**Trois copies explicites de réponses remplacées par des échanges de propriété**, sans changer les données ni le protocole. Sur deux fixtures synthétiques20,8/25,9 Kio, le pipeline mesuré passe en moyenne de0,844577 à0,344029 ms et de1,096040 à0,448945 ms. Dans deux sessions réelles en pause, le service des statistiques n60 passe de2,111800 à1,935500 ms en moyenne, **mais la durée totale MCP ne baisse pas**. Les deux lancements et leur ordonnancement diffèrent : aucun gain global/FPS ni CPU exclusif n’est établi.

## Ownership et synchronisation

`json::Value::swap` échange type,bool,double,string,map,vector, y compris les champs inactifs. Le cas self-swap est neutre. Les autres opérandes doivent être des objets indépendants, pas un parent et son propre descendant. Les conteneurs ont l’allocateur standard dans le module ; la méthode échange leurs ressources sans cloner leurs arbres.

Le chemin de succès utilise ce transfert à trois frontières : payload local vers l’enveloppe finale, retour de execute vers Work.response, puis Work.response vers reply après un WaitForSingleObject réussi. Le service n’accède plus à la réponse après SetEvent ; son shared_ptr et celui du réseau conservent Work jusqu’à la fin de leurs usages. Un timeout n’emprunte pas le transfert réseau ; les règles d’annulation et le message « exécution peut avoir commencé » restent inchangés. Les erreurs,le heartbeat réseau,la sérialisation0.8.12,les accès Game et les hooks ne changent pas.

Les primitives de signal et d’attente Windows utilisent les barrières appropriées d’ordonnancement mémoire ; voir la [documentation Microsoft](https://learn.microsoft.com/en-us/windows/win32/sync/synchronization-and-multiprocessor-issues). Cette garantie est combinée à la relecture des accès et durées de vie de notre propre code ; elle ne rendrait pas sûr un accès supplémentaire après signal. Aucune fonction du SDK ni signature Game nouvelle.

Les tests natifs v100 couvrent36 couples de types avec tous les champs,les retours d’échange/self-swap,−0 et payload NaN caché,Unicode/id/enveloppe consommée,200 transferts après événement et un timeout sans consommation suivi d’une complétion tardive. Ce dernier est un test de helper propre, pas une nouvelle suspension/redémarrage du jeu ni une preuve exhaustive de tous les scénarios d’annulation. Les anciens tests de parseur/sérialiseur et leurs comparaisons d’octets passent aussi.

## Microbenchmark propre

`tests/benchmark_json_ownership.cpp` utilise textuellement le même générateur déterministe que notre benchmark précédent. Aucun SDK,fichier ou donnée du jeu. Trois tailles80/20806/25928 octets ; enveloppe copie/transfert et pipeline copie/transfert,ordre tournant,7 répétitions×60 itérations dans chacun de3 processus natifs. MSVC2010/v100 x64,/O2 /EHsc /MD /W3 ; QPC mural,destructions incluses.

**Les deux variantes clonent d’abord le payload synthétique commun** pour disposer d’un objet local consommable. Le pipeline représente les affectations de réponse et ne mesure ni la construction réelle de la scène Game,ni l’événement/thread,ni la sérialisation,envoi ou MCP. Le compilateur peut élider certains retours ; les nombres d’affectations du source ne sont pas des compteurs d’allocations. Les deux variantes sont appariées dans le même processus/répétition et leurs sorties sont comparées octet par octet avant les mesures. Charge ambiante,caches,allocations et ordonnancement restent non isolés.

| Fixture | Enveloppe copie ms | Transfert ms | Rapport médian | Pipeline copie ms | Transfert ms | Rapport médian |
|---|---:|---:|---:|---:|---:|---:|
|80 octets |0,002434|0,001846|1,294847|0,003853|0,002042|1,908250|
|20806 octets |0,568893|0,350601|1,508115|0,844577|0,344029|2,422126|
|25928 octets |0,677781|0,439740|1,559300|1,096040|0,448945|2,499459|

Temps =moyennes de21 cellules de60 opérations chacune. Différences moyennes appariées du pipeline :0,001811/0,500548/0,647096 ms. Rapports min..max des deux grands pipelines :2,266934..2,869197 et2,246944..2,701178. Le petit objet est plus bruité : une paire d’enveloppes donne même0,924052, donc pas de promesse universelle pour les petites réponses.

Capture **runtime/json-ownership/20261028T155027902251Z/controller.json**, SHA **d78e0da25835f2121d291b6c529ad9da67b9572fa7b9d9d373ed882e85821401** ; stdout bruts et binaire propre exact conservés. Rapport **runtime/json-ownership-0813-analysis.json**. Le rejeu vérifie les hashes du contrôleur/stdout/binaire,plan/compiler/architecture/ordre,durées/unités,fingerprints de fixtures et checksum consommé112560. Le header json.h du benchmark correspond exactement au header construit pour0.8.13.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_json_ownership.py runtime\json-ownership\20261028T155027902251Z\controller.json --expected-sha256 d78e0da25835f2121d291b6c529ad9da67b9572fa7b9d9d373ed882e85821401 --output runtime\nouveau-rapport-ownership.json
```

## Lectures MCP réelles en pause

`tests/live_json_copy_probe.py` ne mute aucune scène ni sauvegarde. Deux lancements0.8.12 et0.8.13,12 lectures tournantes de ping/scène/statistiques n60 par lancement,0,1 s d’attente demandée entre appels. La première lecture est conservée. Un warmup séparé conservé exige un historique de60 frames entièrement postérieur à l’entrée de phase ; toutes les statistiques retenues restent dans cette phase en pause. Caméra stable,horloge de jeu identique,pas de bataille,contrôle temporaire caméra relâché et identité Windows du service vérifiée indépendamment avant/après chaque série.

| Lecture | Version | Service moyen ms | Attente moyenne ms | MCP moyen ms |
|---|---|---:|---:|---:|
| ping |0.8.12|0,234683|1,696108|6,164100|
| ping |0.8.13|0,195133|2,351417|6,838692|
| scène |0.8.12|0,093192|2,887450|7,349117|
| scène |0.8.13|0,067125|3,942208|8,186375|
| statistiques60 |0.8.12|2,111800|3,369417|11,211783|
| statistiques60 |0.8.13|1,935500|3,853992|11,541950|

Le service inclut execute/affectation logique de réponse/debug log, excluant la sérialisation réseau et le client ; les scopes restent inchangés. **Aucune soustraction de ces horloges ne donne du CPU exclusif.** Les réponses/frames et mondes chargés ne sont pas entièrement déterminisés ; ces moyens entre lancements sont descriptifs, pas une comparaison causale appariée comme le microbenchmark. Le service stats a un maximum3,027200 ms après,contre2,342800 avant. Les attentes augmentent dans ces relevés,avec durée MCP moyenne supérieure pour les trois groupes ; ne pas annoncer un MCP globalement plus rapide.

Avant :PID24320,T23940/création FILETIME134376754273623707. Après :PID32476,T11724/création134376767267123146. Les identités sont vérifiées dans chaque processus et **ne sont pas jointes entre lancements**.1 puis2 ping/12 passent par Renderer ; ce drapeau ne signifie pas menu affiché.

Captures **runtime/json-copy-probe/0.8.12-20261028T155324459806Z.json**, SHA **19bad2babb59058856f7deff5920264f6bfba28e44a9df3e0b8ef41ce517c111** et **runtime/json-copy-probe/0.8.13-20261028T160113516354Z.json**, SHA **6ef89c08e51e35942a459a4f1371d4955e63a951059490d282217e6700bd8489**. Rapport **runtime/json-copy-0813-analysis.json**. Rejeu avec analyze_json_copy_probe.py AVANT APRES --before-sha256 SHA --after-sha256 SHA --output NOUVEAU_FICHIER. L’analyse vérifie ordre/quantités/clocks/frames,tailles recomptées,pause/caméra,identités Windows propres et résumé dérivé, sans attribution exclusive des différences.

## Déploiement et état stable

**652 tests Python passent en21,88 s**,dont28 nouveaux contrôles de benchmark et de probe,tests natifs JSON/ownership passent. Premier test d’analyse caméra attendait ValueError mais le validateur commun levait RuntimeError ; erreur normalisée dans l’analyse,puis suite complète réussie. Ni échec natif ni capture de jeu invalide.

La production ne change que json.h (swap et include algorithm) et Probe.cpp (trois transferts/commentaire/version). Le sérialiseur reste textuellement identique à0.8.12 ; pas d’autre changement Game/file/hooks. DLL0.8.13 **280576 octets/SHA2d611c1323d7c581ead1bf28df056b8fee5fc07c099c69b9d29c2efd073a1c9c**,PDB propre **10341376 octets/SHA f4057e5a4827a41bf5502cb37e026b91ba6f9de18522802fb8a2636ef0957050** sous runtime/symbols/0.8.13. Archive **crashes/20261028T155839631284Z-deployment-0813**,preuve runtime/deploy-0813.json,ancienne DLL0.8.12 préservée ; identités des seuls processus du projet fraîchement contrôlées avant arrêt.

Smoke vrai MCP **runtime/json-ownership-0813-smoke.json**,17 outils/trois sondes charsUpdate/findPath/Havok,métadonnées/rôles SDK et pause corrects. **runtime/json-ownership-0813-wire-1793203310150406700.json** valide les quatre erreurs JSON/UTF8/duplicate/idUnicode et ping après, sans mutation. Audit indépendant **runtime/json-ownership-0813-final.json** :pause/horloge de jeu/caméra/Edge restitué,sauvegardes et snapshot/settings identiques,watchdog frais/zéro erreur,WPR inactif et aucun contrôleur restant. Aucun nouveau combat40 ou test de gel réel inutilement rejoué.

## Prochaine question de profilage

La relecture du source montre que l’ancien timer charsUpdate calcule `now()-t` **après acquisition de Guard**. Son agrégat inclut donc l’attente éventuelle de ce verrou de télémétrie, ainsi que l’appel original ; il n’identifie pas son thread. Dans l’ancien combat40 x5,charsUpdate_mean_ms vaut0,557418/0,226448/0,203638/0,239164 ms pour des intervalles moyens12,991564/10,222859/9,447618/9,826232 ms. Ces valeurs ne localisent pas le reste du temps et ne doivent pas être soustraites aux autres systèmes potentiellement concurrents.

Priorité suivante : vérifier la frontière de ce timer et identifier ses threads dans **le hook déjà existant**, distinguer durée d’appel et intervalle post-appel jusqu’au verrou en conservant l’ancien champ historique. Vérifier signature SDK et buckets avant ajout ; toujours trois sondes maximum. Repartir des mesures du moteur plutôt que multiplier les optimisations de petits getters. Aucune nouvelle mesure moteur ni correction de ce timer n’est encore réalisée sous0.8.13.

Échéance autonome22 h15 UTC/23 h15 Paris inchangée ; aucune intervention utilisateur/administrateur attendue.
