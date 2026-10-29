# Root : compteurs CPU optionnels, même DLL 0.8.18

Le mode CPU existant a été activé après un redémarrage archivé, sans modifier ni réinstaller la DLL. À Heng, la fenêtre x5 conserve **1651 appels Root**, **7,160992 ms murales par frame** et une somme de compteurs CPU de **8531,25 ms**. Ces compteurs entourent aussi du code de mesure et les callbacks imbriqués. Ils ne donnent ni CPU moteur exclusif, ni temps GPU, ni gain par rapport aux campagnes précédentes.

Le MCP garde **17 outils**, le plugin **v100 x64**, trois systèmes profilés charsUpdate/findPath/Root et cinq installations effectives : trois detours dédiés et deux services. Aucun nouvel appel Game ou hook. La signature bool sans argument et le binding chargé restent ceux du [rapport Root précédent](root-frame-measurements.md).

## Calibration avant activation

`tests/benchmark_thread_cpu.cpp`, compilé par `tests/benchmark-thread-cpu-v100.cmd`, lit les compteurs de son propre thread ; il n’ouvre aucun processus du jeu. Trois processus exécutent chacun sept répétitions de 20000 paires de lectures, puis un scan avec activité CPU bornée à 500 ms. Toolset v100, x64, /O2. Les scènes avant/après confirment la même heure de jeu en pause.

La médiane des 21 répétitions vaut **0,529625 µs par paire**, minimum **0,491300**, maximum **0,548815 µs**. Ce coût inclut boucle, conversions et contrôles du helper ; il n’est pas le coût complet du hook dans Kenshi. Le contrôle de démarrage de la DLL observe séparément **0,23 µs par lecture** sur 200 lectures ; les deux protocoles ne sont pas interchangeables.

| Processus du helper | Lectures du scan | Deltas positifs | Somme CPU ms | Incrément positif observé ms |
|---|---:|---:|---:|---:|
| 1 | 1353891 | 31 | 484,375 | 15,625 |
| 2 | 1347331 | 32 | 500,000 | 15,625 |
| 3 | 1358541 | 31 | 484,375 | 15,625 |

Les autres deltas du scan valent zéro. **L’unité FILETIME de 100 ns n’est pas sa précision.** L’incrément observé ici ne garantit pas une résolution dans le jeu ou sur une autre machine. Un zéro par appel ne démontre aucune absence de travail CPU ; un delta supérieur à la durée murale de cet appel peut résulter de la quantification. Les analyseurs conservent ces valeurs sans les clamper. Les moyennes suivantes sont des sommes divisées par le nombre de frames retenues, sans précision CPU garantie par frame.

Contrôleur : `runtime/thread-cpu-calibration/20261028T195531645597Z/controller.json`, SHA256 **dc16044be1c418673c1d69b4578c150680474fb37cfe4694f69c905bc33e425f**. Rejeu : `runtime/thread-cpu-calibration-analysis.json`. Il vérifie les empreintes des deux sources, de l’exécutable et de chaque stdout, le plan, les partitions zéro/positif, les histogrammes, les sommes et le PGCD observé. Exécutable propre SHA256 **e4899cb08584ac7488ec16a51957b8d3b065dc8f89d975db480f1f366db54576**, sous build ignoré Git.

## Campagne CPU activé

`KENSHI_PROBE_FUNCTION_THREAD_CPU=1` est fixé au lancement. La sélection Root, AI CPU désactivé, Nav CPU activé, timing des commandes et échéance ne changent pas. La DLL est strictement celle de 0.8.18, SHA256 **24ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**. L’archive **crashes/20261028T200628106023Z-root-cpu-mode-on** conserve l’état précédent ; `runtime/root-cpu-restart.json` constate `native_dll_reinstalled=false` et les identités vérifiées avant arrêt.

Smoke réel MCP : 60 appels, 60 compteurs disponibles, aucun indisponible. Cadence avant campagne : 78 frames sur 513,9912 ms, moyenne des dix dernières 6,95081 ms. **796 tests Python passent en 23,70 s** ; ils se terminent avant l’acquisition. Les nouveaux contrôles couvrent notamment les compteurs quantifiés, les modes CPU explicites, les partitions et la compatibilité CPU désactivé.

`tests/live_root_cpu.py` recharge la copie KenshiProbe_test sous protection, vérifie le module/export/adresse chargés, prépare Heng 10 s à x1 et attend la stabilité. Il demande trois fenêtres de 12 s, pause/x5/pause, après 3 s de warmup chacune ; observations toutes les 0,5 s demandées et inventaires complets, limite 500. La copie est rechargée en pause et la caméra libérée dans le nettoyage final.

| Phase | Frames/appels | Root mural moyen ms | Intervalle moyen ms | p99 intervalle ms | CPU utilisateur ms | CPU noyau ms | Somme CPU ms | Somme CPU / frames ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pause avant | 1795/1795 | 6,843799 | 6,964272 | 11,9179 | 5656,250 | 2937,500 | 8593,750 | 4,787604 |
| x5 | 1651/1651 | 7,160992 | 7,331158 | 11,9149 | 6484,375 | 2046,875 | 8531,250 | 5,167323 |
| Pause après | 1795/1795 | 6,852462 | 6,962866 | 11,9017 | 6734,375 | 2500,000 | 9234,375 | 5,144499 |

Tous les appels ont un compteur disponible ; zéro nesting ignoré, overflow ou identité inconnue. Maxima muraux : 12,806600 / 40,236800 / 12,582600 ms. Le nombre agrégé appels=frames ne prouve pas un appel dans chaque frame non affichée : seules les 100 dernières lignes individuelles sont gardées. Les durées murales et les compteurs CPU ont des points de lecture différents ; ils incluent du travail imbriqué et peuvent traverser les frontières des buckets. Les écarts Root/intervalle ne constituent pas une mesure d’overhead ou d’attente par soustraction, et la calibration hors jeu n’établit pas la neutralité du hook complet.

L’identité Root **T18372 / création FILETIME134376915914545795** rejoint le thread principal et le service rendu aux bornes, ainsi que les deux endpoints CPU OS. Son CPU entier vaut **8,984375 / 9,015625 / 9,578125 s**, dans des fenêtres OS **12,532 / 12,141 / 12,531 s**. Ce sont d’autres fenêtres que celles des appels retenus : aucune fraction de couverture exclusive ni « CPU restant » n’est déduite.

CPU processus : 18,703125 / 26,234375 / 21,796875 s, soit **1,492429 / 2,160808 / 1,739436 processeurs logiques**. Résidus signés processus moins threads calculables : 0 / +0,0625 / +0,015625 s. Aucune identité omise aux endpoints. Populations 397..397 / 449..454 / 454..454 ; progression de game_total_hours 0 / **+0,5561561584472088 h** / 0. Les états PNJ ne sont pas déterminisés et ces séquences ne sont pas un A/B CPU activé/désactivé.

## Rejeu et compatibilité

Capture complète : **runtime/scenarios/root-cpu-20261028T200957553841Z.json**, SHA256 **41dbf03088c48eb2a36d2adfa1c355030a9361dfb590410c2448d1fcb033924d**. Analyse : `runtime/root-cpu-0818-analysis.json`. Depuis la racine :

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_root_cpu.py runtime\scenarios\root-cpu-20261028T200957553841Z.json --expected-sha256 41dbf03088c48eb2a36d2adfa1c355030a9361dfb590410c2448d1fcb033924d --output runtime\nouveau-rapport-root-cpu.json
```

Le manifeste **docs/performance-cohorts-root-cpu.json**, SHA256 **eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675**, garde séparées **sept cohortes et vingt-deux fenêtres**. Les deux manifestes précédents restent inchangés. Rapport `runtime/performance-cohorts-root-cpu-v1.json`, SHA256 **e66f64669f9bc060cbd1e0f12f208b659ad3e277185b66a6d438f5b3c6884896** ; Markdown homonyme.

`runtime/root-cpu-cohorts-replay-proof.json` prouve le rejeu octet-identique sous graines 0/8675309 et l’égalité canonique de l’analyse CPU spécialisée. Les métriques des six anciennes cohortes restent identiques. La seule provenance antérieure qui change est le SHA du source de l’analyseur Root, car son mode CPU attendu devient explicite ; le rapport historique n’est donc pas annoncé octet-identique après cette évolution de source. Le rejeu spécialisé CPU désactivé demeure strictement égal au résultat enregistré : `runtime/root-cpu-off-compatibility.json`.

## Audit et suite

`runtime/root-cpu-0818-final.json` confirme le jeu **37556 / créationUnix1793217991.454578**, copie en pause à **404,3333339691162 h**, caméra normale, contrôle temporaire relâché, Edge restitué et bataille inactive. Les **702/702/738 fichiers** de validation/copie/ancien snapshot correspondent aux références ; settings inchangé, deux gardes de restauration false, watchdog frais sans erreur, WPR inactif et aucun contrôleur de test restant. Helpers 5948 / création1793217991.2477891 et 41992 / création1793217991.2881176 ; vérifier fraîchement chemin, commande et création avant tout arrêt.

Cette mesure rend le CPU inclusif de Root observable en agrégat, avec ses limites. La prochaine campagne utile porte sur le scénario lourd de combat avec la même frontière et le même mode, plutôt qu’une comparaison de versions ; elle doit conserver fenêtres, inventaires, budget adaptatif, restauration et cohortes séparées. Aucune optimisation moteur n’est justifiée par la simple différence murale/CPU. La fermeture autonome reste impérative au plus tard le **28 octobre à22h15UTC** ; aucune nouvelle acquisition ne doit retarder sa préparation.
