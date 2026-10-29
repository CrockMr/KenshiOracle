# Original Renderer — mesures 0.8.17

L’original `Renderer::_NV_update()` mesure **0,819574 microseconde murale par frame active** à Heng, pour **7,056608 ms** d’intervalle moyen entre callbacks. Cette entrée précise est très courte dans la campagne ; **elle ne mesure pas tout le rendu ni le GPU**. Aucun gain moteur ni CPU exclusif n’est annoncé. À cette échelle, le coût propre du chronométrage et du trampoline n’a pas été isolé : ne pas traiter la moyenne comme un temps moteur pur.

## Sélection et périmètre

`rendererUpdate` remplace la sélection MainLoop et désactive également Havok. Le hook Renderer existant est réutilisé : deux detours systèmes dédiés (charsUpdate/findPath), deux de service, **quatre installations effectives et trois frontières profilées**. Pas de double detour à la même adresse ni de quatrième système profilé.

Signature fournie : `void Renderer::_NV_update()`, Renderer.h ligne 44, alias non virtuel de la déclaration virtuelle ligne 43. Symbole et import `?_NV_update@Renderer@@QEAAXXZ` vérifiés dans KenshiLib.lib. SHA256 header : **49367b8a20dda80a495870ee54df655768d909607f5a327a75102b3a0af5009c** ; bibliothèque : **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Preuve : `runtime/renderer-sdk-0817.json`. Aucun RVA de commentaire n’est utilisé pour le binding et aucun code du jeu n’est copié.

`OriginalRendererInvocation<Renderer>` transmet le même pointeur et appelle l’original une fois. Le test natif vérifie l’identité du pointeur, le compteur et l’absence d’appel à un second objet ; les sélecteurs MainLoop/Renderer restent distincts. La réussite de l’installation Renderer active la sélection après ce hook, et le journal de sélection est émis ensuite.

Le chrono commence après heartbeat, protection de pause, drainage initial des commandes et service de l’état de chargement. **Ces travaux initiaux sont exclus ; tout callback atteint à l’intérieur de l’original reste inclus**, ainsi que les attentes et autres travaux imbriqués. `hook_source=existing_renderer_service_hook`, `leading_service_excluded=true` et le scope natif explicite ne promettent aucune exclusion totale des services ni du temps GPU.

Profiler outermost existant, TLS de création lu une fois, capacité huit identités, fin murale avant verrou d’enregistrement, CPU par appel désactivé/null. Les portées peuvent traverser les bornes de buckets. Les autres sondes peuvent les recouvrir : aucune somme ou soustraction exclusive. Sample **696 octets**, historique chars **2523600**, anciens helpers de télémétrie et sérialiseur inchangés.

## Validation et campagne

**721 tests Python passent en 22,05 s**, dont 16 nouveaux contrôles Renderer. Tests natifs v100 : pointeur/appel unique, séparation des sélecteurs et anciens floats/buckets/profondeur réussis. Compilation v100 x64 liée. Le smoke via le vrai MCP vérifie 17 outils, 60 appels Renderer réels, flags, scopes, tailles et aliases. Contrôle de cadence en pause : **74 frames sur 508,269 ms**, tail10 moyen **6,944480 ms**. Pas de ralentissement comparable à la 0.8.14 rejetée ; cause de cette ancienne anomalie toujours inconnue.

`tests/live_renderer.py` reprend la copie KenshiProbe_test avec protection de pause/verrou Edge, prépare Heng pendant 10 s x1 puis attend la disponibilité stable. Trois fenêtres de 12 s demandées suivent après 3 s de warmup chacune : pause/x5/pause. Observations toutes les 0,5 s demandées, inventaires complets limite 500, identités OS aux bornes. Aucun build ni benchmark concurrent pendant l’acquisition. Copie rechargée en pause en fin d’essai, contrôle caméra libéré.

| Phase | Frames/appels | Original moyen µs/frame | Max appel µs | Intervalle moyen ms | p99 intervalle ms |
|---|---:|---:|---:|---:|---:|
| Pause avant | 2032/2032 | 0,781987 | 6,9001 | 6,181928 | 7,8976 |
| x5 | 1783/1783 | 0,819574 | 35,3999 | 7,056608 | 9,4361 |
| Pause après | 1886/1886 | 0,775767 | 3,9999 | 6,627360 | 8,8295 |

Les champs natifs sont en millisecondes ; la colonne des appels est convertie ici en microsecondes (×1000). Aucun nesting ignoré, overflow ou thread Renderer inconnu. L’égalité agrégée appels/frames ne prouve pas un appel dans chaque frame non affichée : seules 100 lignes individuelles finales sont conservées.

Tous les appels rejoignent **T29164/création FILETIME134376841722811107**, identité retrouvée aux deux endpoints CPU et dans game_thread/service_thread des heartbeats encadrants. CPU du **thread entier** : 9,65625/10,171875/9,875 s, dans des fenêtres OS de 12,594/12,609/12,516 s. Ce n’est pas le CPU de l’entrée Renderer. CPU processus : 22,078125/28,546875/23,203125 s, soit 1,753067/2,264008/1,853877 processeurs logiques. Résidus signés +0,03125/−0,078125/−0,078125 s. Un thread **T22944 non observé après** la fenêtre active est omis ; sa consommation n’est pas inventée. Les deux pauses n’ont aucune omission, et le thread Renderer est vérifié dans les trois fenêtres.

charsUpdate original : 0/0,347020/0 ms par frame. Populations : 410..410/443..452/452..452 ; game_total_hours : 0/+0,57817459106451/0. L’état, l’heure et la population évoluent ; pas de comparaison causale avec une autre phase ou version. Les callbacks ne garantissent pas les FPS affichés. Fenêtres CPU et buckets distincts ; ne pas attribuer un « reste » par soustraction ni convertir les autres campagnes en parts additives.

Requêtes principales admises sans réduction : n2032/57426 octets, n1783/61983, n1886/57531 ; stats finales n3600/58181. Octets compacts réencodés, pas taille exacte TCP/MCP ; limite native 64 Kio et plans de budget inchangés.

## Preuves et rejeu

Capture : `runtime\scenarios\renderer-20261028T180433342866Z.json`, completed=true, SHA256 **ada3a6bd984db83f78d28ea8359f9199be794228b0517b11d9b392d5d71ff33b**. Rapport : `runtime/renderer-0817-analysis.json`. Le wrapper vérifie source/scope, aliases, nombre de hooks, sélection unique et jointures CPU à partir des données brutes. Les anciens rejeux MainLoop et chars sont contrôlés lors du checkpoint.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_renderer.py runtime\scenarios\renderer-20261028T180433342866Z.json --expected-sha256 ada3a6bd984db83f78d28ea8359f9199be794228b0517b11d9b392d5d71ff33b --output runtime\nouveau-rapport-renderer.json
```

DLL **304128 octets/SHA2566a4d4735ee608503fc4ecb626b531b96efbca3a938d6298265bcf3da8a82a976**, PDB propre **10382336/SHA25607dbec057c9bb93f180de43c3484dca89bef0ef729ccb940113d01c03a0982a8**, sous `runtime/symbols/0.8.17`. Archive `crashes/20261028T180240899551Z-deployment-0817`, preuve `runtime/deploy-0817.json`. Seuls les processus du projet, vérifiés fraîchement par chemin/commande/création, sont arrêtés ; ancienne 0.8.16 préservée.

Audit `runtime/renderer-0817-final.json` : **PID38472/créationUnix1793210572.281109**, copie en pause/multiplicateur 0 à 404,3333339691162 h, caméra normale, contrôle temporaire libéré, Edge=true, bataille inactive. **702/702/738 fichiers** source/copie/snapshot conformes, settings identique au préalable, gardes false, watchdog frais sans erreur, WPR inactif et aucun contrôleur restant. Helpers **3644/création1793210570.6763327** et **5464/création1793210570.6396365** ; revérifier leur identité avant arrêt.

## Question suivante

Les entrées MainLoop et Renderer mesurées n’expliquent pas toute l’activité du thread principal. Les piles utilisateur précédemment validées passent par Ogre et KingOfRenderThread::startup ; ce dernier est un ancêtre durable, pas un coût CPU démontré et pas une bonne cible d’appels terminés si son original dure toute la session. Le SDK déclare aussi `KingOfRenderThread::mainloop(float)`, candidat fini à vérifier dans les symboles et les observations avant une sélection dédiée. Son nom ne prouve ni fréquence ni couverture. Une éventuelle sélection remplacerait Renderer et inclurait ses callbacks internes ; trois systèmes au maximum. Pas d’ajout aveugle de sonde, de capture administrateur attendue ou de nouvel essai lourd identique sans hypothèse.

Échéance autonome **22 h 15 UTC/23 h 15 Paris** inchangée. Aucune intervention manuelle attendue.

Suite du diagnostic : la candidate KingOfRenderThread::mainloop(float) a été [écartée sans hook](king-mainloop-candidate.md), après vérification de son entrée en fichier et en mémoire. La 0.8.17 reste inchangée ; le [trajet startup vers Ogre](main-thread-loop-route.md) est résolu statiquement. REA a atteint le délai client450 s, sans dossier ; session nettoyée.
