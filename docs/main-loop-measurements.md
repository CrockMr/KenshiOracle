# Original MainLoop — mesures 0.8.16

L’original `GameWorld::mainLoop_GPUSensitiveStuff` mesure **1,36 ms murale par frame active** à Heng, pour un intervalle moyen de **8,12 ms** entre callbacks. Cette entrée ne couvre pas toute la frame. Aucun coût CPU exclusif, temps GPU ou gain moteur n’est déduit.

## Hook et périmètre

La sélection `mainLoopGPUSensitive` réutilise le hook de service existant ; Havok est désactivée. Trois frontières restent profilées : charsUpdate, findPath et MainLoop. Deux detours systèmes dédiés et deux de service donnent **quatre installations effectives**, contre cinq avec une sélection dédiée. Aucun double detour sur la même adresse.

Le SDK fourni déclare `void GameWorld::_NV_mainLoop_GPUSensitiveStuff(float time)` dans GameWorld.h, ligne 196. Le symbole `?_NV_mainLoop_GPUSensitiveStuff@GameWorld@@QEAAXM@Z` et son import sont vérifiés dans KenshiLib.lib. SHA256 header : `e1c5566b24df65a42d01e884ac8a45125a3b257298469a544ad557b7f43e802f` ; bibliothèque : `d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d`. Preuve locale : `runtime/main-loop-sdk-0816.json`. Aucun RVA ni code du jeu copié dans le plugin.

`OriginalLoopInvocation<GameWorld>` transmet le pointeur et le float inchangés et appelle l’original une fois. Les tests natifs vérifient cinq floats bit à bit, dont −0, et le nombre d’appels. Le chrono démarre après la collecte des buckets, la protection de pause et le drainage initial des commandes. **Ce service initial est exclu ; tout callback atteint à l’intérieur de l’original reste inclus**, ainsi que les attentes, autres mods et travaux imbriqués. Le nom GPUSensitiveStuff ne constitue pas une mesure GPU.

Le profiler conserve seulement les appels outermost terminés et termine le chrono avant le verrou d’enregistrement. Les portées peuvent traverser les bornes de buckets ; la moyenne divise leur somme par les frames retenues. CPU optionnel désactivé, champs CPU null. Les autres sondes peuvent recouvrir cette entrée : ne pas les additionner ou soustraire comme des coûts exclusifs. Sample 696 octets et historique chars 2523600 octets inchangés.

## Validation et méthode

**705 tests Python passent en 21,44 s**, plus les tests natifs v100 de forwarding, buckets et profondeur. Compilation v100 x64 liée. Le smoke via le vrai MCP vérifie 17 outils, les compteurs, aliases, tailles et données réelles : 60 appels originaux enregistrés. Le contrôle de cadence en pause observe 77 nouvelles frames sur 512,807 ms, tail10 moyen **6,583510 ms**. Aucun ralentissement comparable à la candidate 0.8.14 rejetée ; sa cause précise reste inconnue.

`tests/live_main_loop.py` recharge KenshiProbe_test sous protection de pause et verrou Edge, prépare Heng pendant 10 s x1 puis attend sa disponibilité. Trois fenêtres de 12 s demandées suivent, chacune après 3 s de warmup : pause, x5, pause. Observations toutes les 0,5 s demandées, inventaires complets limite 500 et identités OS aux bornes. La copie est ensuite rechargée en pause et le contrôle caméra est libéré. Aucun build ou autre benchmark pendant l’acquisition.

| Phase | Frames/appels | Original moyen ms/frame | Max appel ms | Intervalle moyen ms | p99 intervalle ms |
|---|---:|---:|---:|---:|---:|
| Pause avant | 2021/2021 | 1,084158 | 7,267700 | 6,176169 | 8,4886 |
| x5 | 1549/1549 | 1,363674 | 29,271500 | 8,121418 | 10,9988 |
| Pause après | 1565/1565 | 1,356870 | 7,643000 | 8,016632 | 12,1196 |

Aucun nesting ignoré, overflow ou thread inconnu dans ces fenêtres. L’égalité des compteurs agrégés appels/frames ne prouve pas un appel dans chaque frame non affichée : la série individuelle ne conserve que 100 lignes finales.

Tous les appels sélectionnés rejoignent T26508/création FILETIME `134376829972344393`, identité CPU présente aux deux endpoints OS et mêmes game_thread/service_thread aux heartbeats des bornes. CPU du **thread entier** : 9,296875/9,609375/10,25 s dans des fenêtres OS de 12,5/12,609/12,578 s. Ce n’est pas le CPU de cette fonction. CPU processus : 22,3125/29,953125/23,0625 s, soit 1,785/2,375535/1,833559 processeurs logiques ; résidus signés +0,125/+0,03125/−0,015625 s, aucune omission d’endpoint.

charsUpdate original : 0/0,394788/0 ms par frame. Populations : 388..388/439..456/456..456 ; progression game_total_hours : 0/+0,5779018402100178/0. La ville, l’heure et les états évoluent entre phases : aucune comparaison causale avec les pauses ou une version antérieure. Les intervalles de callbacks ne garantissent pas les FPS affichés. Fenêtres OS et buckets diffèrent ; ne pas calculer un « reste CPU » par soustraction.

Requêtes principales admises sans réduction : n2021/57137 octets, n1549/62156, n1565/57079. Ce sont des octets JSON compacts réencodés, pas la taille exacte TCP/MCP. Limite native 64 Kio inchangée, plans de budget et bornage strict conservés.

## Preuves et rejeu

Capture complète : `runtime/scenarios/main-loop-20261028T174602988613Z.json`, SHA256 **c66a4e7d0f8f638f0509d2dbc56610be0bc9411de9525a029f982c31e986427a**. Analyse : `runtime/main-loop-0816-analysis.json`. Le wrapper vérifie scope, réutilisation, compteurs, CPU et jointures d’identité ; l’analyse chars conserve son comportement 0.8.15 par défaut.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_main_loop.py runtime\scenarios\main-loop-20261028T174602988613Z.json --expected-sha256 c66a4e7d0f8f638f0509d2dbc56610be0bc9411de9525a029f982c31e986427a --output runtime\nouveau-rapport-main-loop.json
```

DLL 302080 octets, SHA256 `e401d956ee236034dd7feac7d9830140de0169a7bfa254bfbc2f69f353a45d8b` ; PDB propre 10374144 octets, SHA256 `660a675987d25a40da7eca128242cff4cf91132893fb4ba16e530678ea6539b7`. Copies sous `runtime/symbols/0.8.16`. Archive `crashes/20261028T174304038130Z-deployment-0816`, preuve `runtime/deploy-0816.json`. Chemin, commande et création des seuls processus du projet revérifiés avant arrêt ; ancienne 0.8.15 préservée.

Audit `runtime/main-loop-0816-final.json` : même jeu PID32008/création Unix1793209397.234438, copie en pause/multiplicateur 0 à 404,3333339691162 h, caméra normale, contrôle temporaire libéré, Edge=true, bataille inactive. **702/702/738 fichiers** source/copie/snapshot identiques ; settings identique au préalable, gardes false, watchdog frais sans erreur, WPR inactif et aucun contrôleur restant. Helpers 5796/création1793209394.2727556 et 38020/création1793209394.2255044 : revérifier fraîchement leur identité avant arrêt. Stats finales n3600/57161 octets.

La prochaine frontière proposée est l’original Renderer::_NV_update via son hook existant, en remplacement de MainLoop. Même limite de trois systèmes profilés, forwarding et signature SDK vérifiés, contrôle de cadence avant activation. Aucun résultat anticipé ni attribution automatique au GPU. Échéance autonome 22 h 15 UTC/23 h 15 Paris inchangée ; aucune intervention manuelle attendue.
