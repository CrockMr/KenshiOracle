# Ogre::Root::renderOneFrame — mesures 0.8.18

L’original **sans argument** mesure **7,064655 ms murales par frame active à Heng**, pour **7,067360 ms** entre callbacks. Cette entrée fournit une frontière plus large que les entrées GameWorld/Renderer précédemment mesurées : elle englobe notamment callbacks, services imbriqués et attentes. **Pas de CPU exclusif, de temps GPU, de FPS affichés ou de gain moteur déduits.** Les campagnes antérieures restent des cohortes distinctes, sans soustraction de leurs temps à ceux-ci.

La version0.8.18 reste **v100 x64,17 outils MCP et trois systèmes profilés** : charsUpdate,findPath et Root. Root remplace la sélection Renderer ; MainLoop/Havok ne sont pas profilées. Trois detours dédiés et deux de service font **cinq installations effectives**, contre quatre dans le mode Renderer réutilisant son hook de service. Sample **696 octets**, historique chars **2523600** inchangés.

## API, export et binding réellement vérifiés

Le SDK fourni déclare **bool Ogre::Root::renderOneFrame(void)** dans Include/ogre/OgreRoot.h:558 ; une surcharge Real distincte existe à566. Header SHA256 **0ddff53cd07d4da38def00844dc17c0a6d49c633a6385ff47c81c3bb1bda5a62**. OgreMain_x64.lib est déjà lié par le projet, SHA256 **97db9603acaa5ff19fa58f73bf7362e7298f99e96b36243563beba0334337928** ; les symboles d’import et export sans argument correspondent à **?renderOneFrame@Root@Ogre@@QEAA_NXZ**. La surcharge terminée par `_NM@Z` n’est pas choisie. Le mécanisme générique KenshiLib::AddHook vient de Functions.h, SHA256 **0c8a1a51f4446b43fb43aebfdf9878dcb2c93ed593c79651945272f56c639c8b** ; bibliothèque KenshiLib SHA256 **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**.

REA a cette fois fourni une preuve complète **sans import Ghidra** : inspect_native_exports examine les9329 exports du DLL, deux surcharges nommées et non forwardées. Evidence **ev_168b7ae2bbf871a451c524f994080184164bf758fa762a30795664b1e69309ae**, bundle `runtime/rea-root-exports-evidence.json`, SHA256 **4eeacad16803ff2abc5d352b0a762cf83f0a9dacfded2e48842f327f975f692d**. DLL Ogre original SHA256 **7d3888d21398647519f10a89b1f300d8606f761ad159e6021a797b1b9b3df5f6**. Cette table seule ne prouve pas une exécution ; le préflight et les appels réels suivants apportent les autres éléments.

Avant installation, `runtime/root-export-binding-preflight.json` contrôle le même processus historique0.8.17 par chemin/commande/création, le module chargé, tous les octets du répertoire d’exports et32 octets de l’entrée contre le fichier. Les en-têtes ne diffèrent que par ImageBase, observé égal à la base chargée ; ce champ est explicitement vérifié, tous les autres octets sont exigés identiques. Comparaison initiale refusée puis diagnostic `runtime/root-header-comparison.json` conservé ; aucune différence supplémentaire masquée. Handles fermés, aucune fonction du jeu appelée par le préflight.

Le plugin utilise **GetModuleHandleW/GetProcAddress sur le module déjà chargé**, puis le AddHook générique : pas de LoadLibrary, GetRealAddress appliqué à un export Ogre, adresse manuelle ou code du jeu copié. Il expose le chemin UTF-8, symbole et adresse hexadécimale observés. Le contrôleur vérifie dans le nouveau processus que cette adresse vaut base chargée +RVA de l’export exact du fichier identifié. Ces coordonnées sont des preuves, pas des constantes copiées dans le plugin.

`OriginalBoolInvocation` transmet le pointeur, appelle une fois et renvoie le bool original. Tests natifs : false et true, objet attendu/nombre d’appels, exports manquants/module manquant/null, paire de surrogates UTF-16 et surrogate invalide, adresse inchangée sous locale à groupement numérique. L’adresse est formatée avec locale classic. Le helper n’invoque pas l’export Windows utilisé dans le test de résolution ; les appels bool sont ceux de notre mock propre.

## Périmètre et contrôle de cadence

Le profiler existant garde les appels outermost terminés, la création TLS et les huit identités. Fin du chrono avant le verrou d’enregistrement. **Aucun service interne à l’original Root n’est exclu** : travail, attentes, autres mods et hooks/commandes du projet atteints dedans restent inclus. `hook_source=loaded_ogre_export`, `leading_service_excluded=false`, module/symbole/adresse et scope exact le disent. Les spans peuvent traverser les limites de buckets. CPU par appel désactivé ; champs CPU null, pas de faux zéro ni d’estimation GPU.

**777 tests Python passent avant installation**, puis **778 en24,00 s** après l’intégration au consolidateur ; assertions natifs v100 réussies et build final lié. Pas de test/build pendant l’acquisition réelle. Smoke vrai MCP `runtime/root-frame-0818-smoke.json` :17 outils,60 appels terminés, moyenne6,329167 ms, flags/counts/scope/binding conformes et partie en pause. Cadence `runtime/root-frame-0818-cadence.json` :72 frames sur505,178 ms, tail10 moyen **7,586990 ms**, avant activation. La0.8.14 rejetée n’est pas réinstallée.

## Campagne Heng pause/x5/pause

`tests/live_root_frame.py` recharge KenshiProbe_test sous protection de pause/verrou Edge, vérifie le DLL/export/binding, prépare Heng10 s x1 puis attend la disponibilité. Trois fenêtres12 s demandées suivent, chacune après3 s de warmup ; observations0,5 s demandées et inventaires complets limite500. La copie est rechargée en pause et le contrôle caméra libéré en fin d’essai.

| Phase | Frames/appels | Root moyen ms/frame | Max appel ms | Intervalle moyen ms | p99 intervalle ms |
|---|---:|---:|---:|---:|---:|
| Pause avant | 2046/2046 | 6.092581 | 17.320100 | 6.094736 | 7.6277 |
| x5 | 1775/1775 | 7.064655 | 21.655600 | 7.067360 | 10.9783 |
| Pause après | 1850/1850 | 6.776492 | 21.410600 | 6.779735 | 9.8829 |

Même nombre agrégé d’appels et de frames ; cela ne prouve pas un appel dans chacune des frames non affichées, la série individuelle gardant100 lignes finales. Aucun nesting ignoré, overflow ou identité Root inconnue dans les fenêtres. Root rejoint **T37428/création FILETIME134376890854440932**, identité CPU aux deux endpoints et même game_thread/service_thread aux heartbeats encadrants. CPU du **thread entier** :9,15625/9,796875/10,140625 s ; fenêtres OS12,5/12,578/12,578 s. Pas du CPU de la seule fonction.

CPU processus22,96875/30,625/21,953125 s, soit **1,837500/2,434807/1,745359 processeurs logiques**. Résidus signés +0,078125/+0,21875/0 s. Aucune omission avant/actif ; dernière pause : **T25724 etT32984 non observés avant**, donc omis sans inventer leur consommation. Le thread Root est vérifié dans les trois fenêtres. Populations observées385..385/429..448/433..433 ; game_total_hours0/**+0,5762119293212891**/0. Pas de stationnarité ou état PNJ déterminisé supposé.

Requêtes principales n2046/57324 octets, n1775/62323, n1850/57315, une tentative chacune. Octets compacts réencodés, pas taille exacte TCP/MCP. Limite native64K et budget adaptatif inchangés. Fenêtres OS, scène et buckets distinctes ; proximité des moyennes Root/callbacks ne rend pas leurs spans identiques et ne justifie pas une soustraction « hors Root ».

## Provenance, audit et rejeu

Capture complète **runtime\scenarios\root-frame-20261028T192845606379Z.json**, SHA256 **28779a39bfabb747fdd5d800b4793b63fd08a8e6932484ddfdb2a19b95c20d0d** ; analyse `runtime/root-frame-0818-analysis.json`. Le rejeu recontrôle version/flags, trois systèmes/cinq installations, module exact, surcharge sans argument, adresse résolue et jointures CPU. Le fichier brut n’est pas modifié.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_root_frame.py runtime\scenarios\root-frame-20261028T192845606379Z.json --expected-sha256 28779a39bfabb747fdd5d800b4793b63fd08a8e6932484ddfdb2a19b95c20d0d --output runtime\nouveau-rapport-root.json
```

Un **nouveau manifeste** `docs/performance-cohorts-root.json` ajoute Root aux cinq cohortes précédentes : **six cohortes/dix-neuf fenêtres**, sans modifier le manifeste historique. SHA256 **bbff14d3734e95c916f20b8fd74d7f51de600b99afd8cb030daaa427d34ebb2e** ; rapport `runtime/performance-cohorts-root-v1.json`, SHA256 **c2d851ded75f276d9f028fc472aaed6fd37f5b234f964424cd0d7f7f83f70c00**, tableau Markdown homonyme. Preuve `runtime/root-cohorts-replay-proof.json` : deux graines0/8675309 byte-identiques, ancien diagnostic à cinq cohortes toujours byte-identique et résultat Root canonique égal au rejeu spécialisé. Même CLI de consolidation, avec ce manifeste et son SHA ; aucune nouvelle acquisition.

DLL propre **317952 octets/SHA25624ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**, PDB **10398720/SHA256938435e25b0a67a2ae9254447ff6e64bba93ace52b291aadbfeb7734fc310d89**, sous `runtime/symbols/0.8.18`. Archive **crashes/20261028T192441333577Z-deployment-0818**, preuve `runtime/deploy-0818.json`, ancienne0.8.17 préservée. Seuls les processus projet ont été arrêtés après vérification fraîche. Rollback préparé, non utilisé ; il ne réinitialise pas les sources.

Audit **runtime/root-frame-0818-final.json** : jeu **PID8412/créationUnix1793215485.444091**, copie en pause à404,3333339691162 h, caméra normale/contrôle libéré/Edge=true, bataille inactive. **702/702/738 fichiers** source/copie/snapshot conformes, settings identique au préalable, gardes false, watchdog frais sans erreur, WPR inactif, aucun contrôleur restant. Helpers **6396/créationUnix1793215484.518235, 24624/créationUnix1793215484.4811432** : revérifier identité fraîchement avant arrêt. Aucun fichier du jeu ni code décompilé dans Git ; sorties natives/Evidence/captures restent sous runtime ignoré.

## Question suivante

Cette frontière étant observée, évaluer le **mode CPU par appel déjà présent** (`KENSHI_PROBE_FUNCTION_THREAD_CPU`), avec coût et quantification de GetThreadTimes documentés, avant d’en interpréter les sommes. Une nouvelle cohorte devra déclarer ce mode et préserver le rejeu CPUoff ; elle ne sera pas un A/B déterministe. Les deltas CPU entourent aussi du code de mesure et le travail imbriqué : aucune attribution exclusive au moteur. Pas besoin d’un nouvel outil MCP ni d’une nouvelle sonde simultanée. Échéance autonome22 h15 UTC/23 h15 Paris inchangée ; aucune intervention manuelle attendue.
