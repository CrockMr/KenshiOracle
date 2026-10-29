# Combat de 40 PNJ : Root et compteurs CPU, 0.8.18

Une campagne à Mongrel, à vitesse x5, a suivi **40 PNJ sur 111 observations**. **36 acteurs présentent un signal de blessure**, jusqu’à 12 sont inconscients dans les observations ; aucun mort ni cible extérieure au groupe n’est observé. Les quatre fenêtres sont terminées et la copie est restaurée en pause. Les identités et compteurs Root sont disponibles dans toutes les séries retenues.

**Deux séries ont été raccourcies par le plafond natif de 64 Kio.** Leurs moyennes et p99 décrivent la fin des fenêtres, sans garantir la couverture des pics du début. Cette limite est aussi importante que les temps mesurés. La campagne ne démontre ni gain moteur, ni coût marginal par PNJ, ni CPU exclusif ou temps GPU.

## Conditions et vérifications

Même processus que la campagne Heng CPU activé : PID37556, créationUnix1793217991.454578, même DLL0.8.18 SHA256 **24ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**. Aucun redémarrage, build ou changement natif pendant cette campagne. **17 outils MCP, v100 x64, trois systèmes profilés**, trois detours dédiés plus deux services. Root remplace les autres sélections ; CPU Root activé, identité TLS et modes de navigation inchangés.

Le contrôleur `tests/live_root_battle.py` vérifie avant mutation l’exécutable et sa création, les empreintes des sauvegardes, la DLL du plugin, le module Ogre chargé, son export sans argument et l’adresse résolue. Il recharge KenshiProbe_test sous verrou temporaire de caméra, prépare Mongrel et attend sa disponibilité, puis crée vingt paires Bloodraiders/Mercenary Guild avec hostilité mutuelle vérifiée. La référence de calibration GetThreadTimes reste celle du [rapport Root CPU](root-cpu-measurements.md), avec SHA du rapport compagnon. Elle ne garantit aucune précision CPU par frame.

Quatre fenêtres demandées **5/5/10/10 secondes**, observations toutes les0,25s demandées, inventaires complets avant/après avec limite500. L’heure simulée progresse dans chacune. Le seed et l’état complet des PNJ ne sont pas contrôlés. Les captures Heng et l’ancien combat Havok restent des cohortes distinctes, sans comparaison causale.

**837 tests passent en24,81s avant l’acquisition**, dont les contrôles du nouvel analyseur Root combat, de sa compatibilité avec l’ancien combat, des compteurs quantifiés, des identités et de l’adaptateur du consolidateur. Une revue indépendante du contrôleur n’a trouvé aucun défaut bloquant ; les attestations finales ont été renforcées pour inclure heure, bataille inactive, caméra normale et SHA de la source. Aucun test ni build pendant l’acquisition.

## Séries effectivement retenues

| Fenêtre | Durée demandée s | Frames demandées → retenues | Root mural moyen ms/frame | Intervalle moyen ms | p99 intervalle ms | Max appel Root ms |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 346 → 173 | 9,904946 | 9,908775 | 15,2745 | 17,793500 |
| 2 | 5 | 585 → 585 | 8,966793 | 8,971941 | 14,1192 | 15,529700 |
| 3 | 10 | 1065 → 532 | 9,415041 | 9,424072 | 16,6824 | 25,363300 |
| 4 | 10 | 1073 → 1073 | 9,544408 | 9,549954 | 15,0027 | 30,994700 |

Les nombres agrégés d’appels Root correspondent aux frames retenues, sans prouver un appel dans chaque frame non affichée. Les statistiques par frame ne conservent que100 lignes finales. Aucune identité Root tronquée/inconnue, aucun appel CPU indisponible. Les temps incluent le travail original, les callbacks/services imbriqués et des attentes ; leurs points de lecture diffèrent de ceux du CPU et de l’intervalle entre callbacks.

Réponses principales compactes : **64367/63148/63046/63806 octets**. Les fenêtres1 et3 ont nécessité une seconde requête après rejet pour taille. Les contextes diagnostiques demandés à3600 ont été réduits à **225/450/900/1800**, avec respectivement5/4/3/2 tentatives. Toutes les tentatives sont conservées. Ces octets sont ceux d’un réencodage compact, pas le nombre exact sur le fil TCP.

Une nouvelle requête avance aussi dans le temps : les réductions ne sont pas de simples coupes d’un instantané immuable. Les scènes bornent les buckets retenus, mais les p99 ci-dessus ne résument pas l’intégralité des fenêtres OS, surtout les fenêtres1 et3. Les commandes et leurs répétitions font partie de la charge de collecte ; leur effet n’est pas isolé par cette campagne.

## CPU et populations

| Fenêtre | CPU Root utilisateur ms | CPU Root noyau ms | Somme CPU Root ms | CPU thread entier s | Fenêtre OS s | CPU processus s | Processeurs logiques |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1218,750 | 187,500 | 1406,250 | 3,859375 | 5,266 | 10,609375 | 2,014693 |
| 2 | 3343,750 | 546,875 | 3890,625 | 3,937500 | 5,281 | 12,390625 | 2,346265 |
| 3 | 3250,000 | 484,375 | 3734,375 | 7,984375 | 10,375 | 22,703125 | 2,188253 |
| 4 | 6265,625 | 1218,750 | 7484,375 | 7,546875 | 10,282 | 23,875000 | 2,322019 |

Root rejoint **T18372 / créationFILETIME134376915914545795**, les deux endpoints CPU et les TID game_thread/service_thread des heartbeats encadrants. Les sommes Root portent sur les seuls appels retenus ; les colonnes thread/processus portent sur des fenêtres OS plus larges. **Aucune soustraction ou fraction de couverture exclusive n’est calculée.** Les compteurs autour des appels sont quantifiés et incluent du code de mesure ; zéros ou deltas supérieurs au wall ne sont pas clampés.

Résidus signés processus moins threads calculables : **−0,109375/−0,015625/−0,046875/−0,109375s**. Les sept lignes de rôles SDK représentent cinq identités uniques ; les deux rôles physiques sont alias et SaveFileSystem reste non vérifié. Aucune identité omise aux endpoints CPU ; les résidus restent signés, sans consommation inventée. Populations observées **169..295 / 289..289 / 289..331 / 309..344**. Progression de game_total_hours **+0,226564 / +0,241835 / +0,475594 / +0,471228h**. Les variations de population et de blessures sont observées, sans attribution exclusive des temps à ces changements.

## Preuves et rejeu

Capture **runtime/scenarios/root-battle-20261028T202347708754Z.json**, SHA256 **59e8a609a75a4cd32606d83fc3bdd6ab40ef6f1e323f851afe597d27b5258ecc**, completed=true, erreurs d’acquisition/restauration absentes. Analyse `runtime/root-battle-0818-analysis.json` et résumé `runtime/root-battle-0818-summary.json`. Depuis la racine :

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_root_battle.py runtime\scenarios\root-battle-20261028T202347708754Z.json --expected-sha256 59e8a609a75a4cd32606d83fc3bdd6ab40ef6f1e323f851afe597d27b5258ecc --output runtime\nouveau-rapport-root-combat.json
```

Nouveau manifeste **docs/performance-cohorts-root-battle.json**, SHA256 **6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594** : **huit cohortes et vingt-six fenêtres**. Rapport `runtime/performance-cohorts-root-battle-v1.json`, SHA256 **ad8c1c5bee25acec1fe826bbfbfed8f1d6a364dbf9c5ca6dc7aeb8fe48081a89** ; Markdown homonyme SHA256 **3b9d23d6ce7c87fe3e84236095b5b58127088f7e76561d31a2a76eed35f2ae54**. Preuve `runtime/root-battle-cohorts-replay-proof.json` : deux graines Python octet-identiques, analyse spécialisée canonique identique, sept cohortes antérieures strictement identiques. Aucun brut ou manifeste historique modifié.

Audit indépendant **runtime/root-battle-0818-final.json** : même processus, pause/multiplicateur0 à **404,3333339691162h**, caméra normale et contrôle temporaire relâché, Edge restitué, bataille inactive. **702/702/738 fichiers** source/copie/ancien snapshot conformes ; settings inchangé, gardes de restauration false, watchdog frais sans erreur, WPR inactif, aucun contrôleur de test restant. Les deux helpers restent5948/41992, avec les créations du rapport CPU précédent ; revérifier toutes leurs identités avant arrêt.

## Amélioration maintenant étayée

Le plafond de réponse a effectivement retiré une partie des premières fenêtres de mesure. La prochaine amélioration de l’outil est une réponse statistique compacte conservant les agrégats sur toute la plage demandée, avec détails volumineux optionnels et omissions explicites. Elle peut rester dans l’outil MCP existant. Critères : mêmes agrégats que la réponse complète sur des fixtures propres, sélection temporelle clairement définie, réponse sous plafond et validation réelle sous charge. Il faudra vérifier son coût de collecte ; augmenter arbitrairement le plafond ou comparer les p99 tronqués aux anciennes campagnes ne résout pas cette limite.
