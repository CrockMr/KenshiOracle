# Diagnostic de performances reproductible

**État courant 0.8.20 : neuf cohortes/trente fenêtres historiques et trois séries de collecte séparées.** La [confirmation randomisée](randomized-observer-measurements.md) préenregistre ordre, graine, protocole et sources avant 36 blocs/660 requêtes, sans saut. Le CPU propre du serveur MCP est identifié et mesuré sur ses intervalles distincts. À 10 Hz, les six différences appariées aggregates−full du service et de la latence client sont négatives, médianes −1,93242 ms et −3,58830 ms. Le CPU serveur donne trois différences positives et trois négatives : gain indéterminé, aucun gain FPS/GPU ou CPU exclusif démontré. Les 110 points sous verrou conservent 78 personnages/1 ville, contre 106/1 dans le pilote précédent, malgré la même DLL et le même jeu ; ne pas fusionner les séries comme un A/B de scène identique. **1143 tests Python passent**, rejeu octet-identique sous deux graines ; copie laissée en pause et fichiers protégés conformes. Les paragraphes suivants sont historiques.

**Référence historique 0.8.20 : construction directe des agrégats.** La [construction directe](direct-aggregate-statistics-measurements.md) conserve le JSON sur 198 snapshots natifs et termine 36 blocs/660 requêtes, avec restitution et audit. À 10 Hz dans cette série en pause, le service compact est 88,18 % plus court en réduction appariée médiane que le service full ; aucune conclusion FPS/GPU ou CPU exclusif. Le rechargement présente 106 personnages, contre 78 au pilote 0.8.19 : les séries ne constituent pas un A/B de scène identique. 1023 tests Python, 2266 assertions natives et 61 assertions bootstrap réussis à ce jalon. Les captures et métriques historiques restent inchangées.

**État courant : neuf cohortes et trente fenêtres**, avec les [statistiques compactes0.8.19](aggregate-statistics-measurements.md). Tous les N demandés de la nouvelle campagne sont conservés en une requête chacun ; les détails sont explicitement null avec compteurs d’omission. 892 tests passent en23,21s. Les campagnes précédentes gardent leurs métriques et leurs limites propres, sans comparaison causale de performances entre versions.

**État courant : huit cohortes et vingt-six fenêtres**, dont le [combat40 Root CPU](root-battle-measurements.md). 837 tests passent en24,81s, même DLL0.8.18. Deux séries de ce combat sont des queues raccourcies par le budget de réponse ; leurs p99 ne couvrent pas les pics initiaux omis. Les nouveaux rapports sont octet-identiques sous deux graines et les sept cohortes antérieures strictement préservées. Les extensions à sept/six/cinq cohortes ci-dessous sont historiques.

**Extension courante : sept cohortes et vingt-deux fenêtres**, avec le [mode CPU Root mesuré et calibré](root-cpu-measurements.md). Le même DLL0.8.18 est conservé ; 796 tests passent en23,70s. Les paragraphes à six puis cinq cohortes ci-dessous sont historiques. Les métriques anciennes sont inchangées ; le SHA de source de leur analyseur Root évolue lorsque le mode CPU attendu devient explicite. Les nouveaux rapports à sept cohortes sont octet-identiques sous deux graines Python, sans comparaison causale entre modes.

**Six cohortes et dix-neuf fenêtres sont désormais rejouables hors jeu**, avec leurs empreintes et leurs analyseurs spécialisés, via le manifeste Root ajouté en fin de document. Le manifeste historique à cinq cohortes/seize fenêtres reste inchangé et son rapport demeure byte-identique. Les deux graines Python produisent les mêmes rapports. **778 tests passent en24,00 s**. Le plugin courant est **0.8.18/v100 x64**, avec **17 outils MCP et trois frontières profilées** ; la consolidation elle-même ne lance pas de mesure du jeu.

## Reproduire le manifeste historique sans lancer le jeu

Depuis la racine du projet, les cinq captures locales sous runtime doivent être disponibles. Elles restent ignorées Git ; aucune sauvegarde ni donnée du jeu n’est distribuée par le manifeste. Le CLI ne se connecte ni au MCP ni au watchdog et n’appelle aucun outil de capture. Il refuse un manifeste ou brut dont le SHA diffère, les captures incomplètes, les cohortes répétant le même brut et les sorties existantes.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_performance_cohorts.py docs\performance-cohorts.json --expected-manifest-sha256 895a59dc6fca89d6fd22897c767fff12c4eb4d9ea71db7eea006f8c6b99208a7 --root . --output runtime\nouveau-diagnostic.json --markdown runtime\nouveau-diagnostic.md
```

Manifeste version1 : `docs/performance-cohorts.json`. Rapport accepté : **runtime/performance-cohorts-v2.json**, SHA256 **2cc2069553f320d91fa0a4474997cdc42a7ca99f7b1055820565b9e2050d3312** ; tableau complet **runtime/performance-cohorts-v2.md**, SHA256 **a679c78028f5d87a40112b273a52c2e12f36d2c5d8f1532d5ec9402b6759144d**. Preuve des cinq relectures spécialisées et des deux graines0/8675309 : **runtime/performance-cohorts-replay-proof.json**. Le premier prototype v1 est conservé ; v2 ajoute les jointures SDK/CPU explicites, sans nouvelle acquisition.

Le manifeste fixe version native, sélection, chemin relatif et SHA de chaque capture. Les scénarios y sont des labels déclaratifs ; les scènes et villes réellement présentes sont conservées séparément. Le CLI relance chaque analyse spécialisée depuis les données brutes, ne copie pas un résumé mis en cache. Il garde séparés PID/création, TID/FILETIME, fenêtres de scène, buckets et compteurs OS. Les créations FILETIME restent des chaînes exactes ; aucune fusion entre cohortes à TID égal.

## Cohortes indépendantes, pas un benchmark entre versions

| Cohorte | Conditions retenues | Fait observé dans cette cohorte | Limite principale |
|---|---|---|---|
| Heng/Havok0.8.10 | Pause/x5/pause,3221/2832/2825 frames | 528882 appels Havok actifs,0,037101 ms murale/frame | Fonction inclusive sur un worker ; pas tout son CPU |
| Mongrel/combat0.8.10 |40 PNJ,quatre fenêtres5/5/10/10 s demandées |36 acteurs avec signal de blessure ; premier p99 intervalle66,3855 ms | Population observée176..295 au début, puis renforts ; pas coût marginal par PNJ |
| Heng/chars0.8.15 | Pause/x5/pause,1982/1855/1922 frames | Appel chars actif0,296559 ms/frame ; post-appel0,000073529 ms/frame | Post inclut timer/ordonnancement, pas contention pure |
| Heng/MainLoop0.8.16 | Pause/x5/pause,2021/1549/1565 frames | Original actif1,363674 ms/frame ; intervalle8,121418 ms | Service initial exclu, callbacks internes inclus ; pas toute la frame |
| Heng/Renderer0.8.17 | Pause/x5/pause,2032/1783/1886 frames | Entrée originale active0,000819574 ms/frame ; intervalle7,056608 ms | Pas tout le rendu/GPU ; chrono/trampoline non isolés à cette échelle |

Le tableau complet conserve **toutes les pauses et fenêtres**, leurs populations observées et durées OS. Les valeurs ne sont pas regroupées en moyenne globale, ratio d’amélioration ou différence de « coût de simulation ». Les sessions ont des états, heures, populations et portées différents. Un intervalle de callback n’est pas une mesure garantie des FPS affichés ; soustraire des sondes inclusives ne localise pas le travail restant.

## CPU et portées disponibles

Le JSON conserve, pour chaque fenêtre, user/kernel/processus, durée monotone OS, processeurs logiques, tous les threads calculables, résidus **signés** et omissions. Les jointures de la sélection et des rôles SDK exigent TID **et** création ; un rôle changé n’est pas assigné sur le seul TID. Deux rôles SDK peuvent pointer vers le même thread : leur CPU ne s’additionne pas. Ces nombres portent sur les threads entiers, pas sur leurs seules fonctions visibles.

Exemple : la cohorte Renderer active consomme2,264008 processeurs logiques au niveau processus, dont le thread sélectionné a10,171875 s CPU sur12,609 s OS. Un autre thread manque à l’endpoint final : il est omis, sans consommation inventée. Le temps mural0,000819574 ms/frame de l’entrée Renderer est une autre portée et ne devient pas une fraction CPU de ce thread. Les deux premières cohortes n’ont pas charsUpdate_split : **null signifie indisponible**, sans faux zéro. Leur champ chars historique reste étiqueté jusqu’à l’acquisition du verrou.

Deux adaptations historiques ont été nécessaires : absence de champs chars split avant0.8.15 et absence d’identité processus à la racine de l’ancien contrôleur Havok. Dans ce dernier cas, l’identité provient du premier endpoint CPU et est contrôlée sur toutes les phases ; cette provenance est indiquée. Les bruts et rapports historiques restent inchangés. Aucun échec partiel de combat n’est intégré comme répétition complète.

## Priorités fondées sur les preuves

1. **Localiser le travail hors des entrées déjà chronométrées du thread principal.** Le [trajet startup→Ogre](main-thread-loop-route.md) est observé/statiquement relié, sans pourcentage CPU. King::mainloop a été [écartée avant instrumentation](king-mainloop-candidate.md) ; startup et Renderer::go rejoignent une boucle durable. Le SDK fourni contient une autre candidate finie : **Ogre::Root::renderOneFrame(void)**, ainsi qu’une surcharge avec temps, dans Include/ogre/OgreRoot.h. OgreMain_x64.lib est déjà lié par le projet. **Question historique depuis résolue par la campagne Root0.8.18**, voir [export/binding/retour bool vérifiés](root-frame-measurements.md). La preuve de déclaration initiale reste runtime/root-frame-header-candidate.json ; l’instrumentation remplace Renderer. Ne pas confondre cette méthode avec Renderer::renderOneFrame marqué no_addr, ne pas inventer un export ni coller un RVA. Toujours trois systèmes maximum.
2. **Distinguer la rafale de navigation du régime établi avant une optimisation.** La [campagne x5 antérieure](heng-x5-adaptive-measurements.md), complémentaire aux cinq cohortes du manifeste, contient sept recherches lentes false à coordonnées différentes. Cela ne démontre pas une répétition cachable ni la cause des échecs ; ne pas ajouter un cache d’échecs sur ce seul relevé.
3. **Quantifier avant de remplacer un worker.** L’[objet BirdManager observé](worker-object-validation.md) et le rapprochement de ses piles identifient un trajet ; ils ne donnent pas le CPU exclusif de son calcul. Aucun nom d’API BirdManager absent du SDK n’est inventé. Une nouvelle capture doit répondre à une question précise ; ni clone échoué1450, ni RIP identiques, ni import REA froid ne sont répétés sans condition nouvelle.

Les optimisations propres de [sérialisation](json-serialization-measurements.md) et d’[ownership](json-ownership-measurements.md) sont documentées séparément. Leurs gains synthétiques locaux ne sont pas convertis en FPS ni en gain moteur. Le présent consolidateur ne modifie pas l’algorithme de Kenshi.

## Validation et limites pratiques

Les28 nouveaux tests couvrent empreintes/version/sélection, rejet des doublons et sorties existantes, captures partielles ou contradictoires, absence historique de split/identité, FILETIME au-delà de la précision entière d’un float, rôle SDK à création changée, fenêtres de combat et déterminisme du CLI. Tous les cinq rejeux spécialisés antérieurs ont le même digest canonique ; les deux graines donnent des rapports byte-identiques. Pas de nouveau test natif ni build inutile : tous les anciens fichiers plugin sont inchangés.

Une capture CPU exclusive/pondérée demeure absente. Les populations sont des observations, pas un état PNJ déterminisé. REA a réellement été tenté puis nettoyé après le délai **client450 s** avant son budget900 s ; aucun dossier de fonction obtenu, voir le rapport de trajet. Le replay vérifie les données enregistrées, **pas l’état actuel de la machine** : l’audit live distinct reste nécessaire après une véritable modification. Les lancements futurs de scénarios gardent leurs contrôles d’autorisation et d’échéance ; le replay hors jeu n’enlève pas ces garde-fous.

## Extension Root validée

Le manifeste historique à cinq cohortes reste inchangé. `docs/performance-cohorts-root.json` ajoute la [campagne Root0.8.18](root-frame-measurements.md) : six cohortes/dix-neuf fenêtres, deux graines byte-identiques et ancien diagnostic byte-identique. Root7,064655 ms murales/frame active, intervalle7,067360 ms ; callbacks/services/attentes inclus, pas CPU exclusif/GPU. Le même CLI accepte ce manifeste avec son SHA explicite.778 tests passent ;17 outils MCP inchangés.

Reproduction de l’extension courante :

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_performance_cohorts.py docs\performance-cohorts-root.json --expected-manifest-sha256 bbff14d3734e95c916f20b8fd74d7f51de600b99afd8cb030daaa427d34ebb2e --root . --output runtime\nouveau-diagnostic-root.json --markdown runtime\nouveau-diagnostic-root.md
```

## Extension Root avec compteurs CPU optionnels

Le manifeste `docs/performance-cohorts-root-cpu.json` ajoute une cohorte indépendante à DLL identique, après redémarrage archivé et activation du mode CPU existant. SHA256 **eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675**. Les sept cohortes/vingt-deux fenêtres gardent leurs identités et conditions propres. Les compteurs quantifiés par appel ne représentent pas du CPU exclusif ou une précision par frame.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_performance_cohorts.py docs\performance-cohorts-root-cpu.json --expected-manifest-sha256 eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675 --root . --output runtime\nouveau-diagnostic-root-cpu.json --markdown runtime\nouveau-diagnostic-root-cpu.md
```

Rapport accepté `runtime/performance-cohorts-root-cpu-v1.json`, SHA256 **e66f64669f9bc060cbd1e0f12f208b659ad3e277185b66a6d438f5b3c6884896** ; Markdown homonyme SHA256 **9b1b8c93d87fdd7451beba1a84b14e1a6c1c1bbb92567286ca0ea49ed300b583**. Preuve `runtime/root-cpu-cohorts-replay-proof.json` : deux graines octet-identiques, résultat spécialisé canonique identique, six métriques antérieures identiques ; seul leur SHA de source Root change, les rapports historiques restent conservés. Voir [calibration, campagne et limites](root-cpu-measurements.md).

## Extension combat Root CPU

Manifeste `docs/performance-cohorts-root-battle.json`, SHA256 **6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594**. Rapport `runtime/performance-cohorts-root-battle-v1.json`, SHA256 **ad8c1c5bee25acec1fe826bbfbfed8f1d6a364dbf9c5ca6dc7aeb8fe48081a89** ; preuve `runtime/root-battle-cohorts-replay-proof.json`.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_performance_cohorts.py docs\performance-cohorts-root-battle.json --expected-manifest-sha256 6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594 --root . --output runtime\nouveau-diagnostic-root-combat.json --markdown runtime\nouveau-diagnostic-root-combat.md
```

Les quatre fenêtres conservent40 acteurs et111 observations. Les statistiques retenues346→173 et1065→532 sont explicitement raccourcies ; le CPU OS garde ses fenêtres plus larges. [Protocole, résultats et limites](root-battle-measurements.md). Les limites et questions actuelles sont documentées dans les [questions ouvertes](open-questions.md).

## Extension agrégats compacts0.8.19

Manifeste `docs/performance-cohorts-aggregates.json`, SHA256 **d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9**. Rapport `runtime/performance-cohorts-aggregates-v1.json`, SHA256 **05c42fde3ee3315b0c38608b21ab7b9afe68544713ecf348c3596790b72433e7** ; preuve `runtime/aggregate-cohorts-replay-proof.json`.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_performance_cohorts.py docs\performance-cohorts-aggregates.json --expected-manifest-sha256 d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9 --root . --output runtime\nouveau-diagnostic-aggregates.json --markdown runtime\nouveau-diagnostic-aggregates.md
```

Les deux graines produisent les mêmes nouveaux rapports ; les huit métriques antérieures restent strictement égales. Le seul changement de provenance ancien est le SHA de source de l’analyseur root_battle, désormais paramétré sur la version attendue (0.8.18 par défaut,0.8.19 explicite). Les fichiers historiques sont préservés. Une plage de N callbacks reste distincte des bornes de scène et de CPU OS ; aucune précision exclusive ou couverture exactement5/10s inférée.

## Compléments hors consolidation : navigation et coût de collecte

La [chronologie de navigation](navigation-timeline-measurements.md) rejoue deux captures existantes à SHA vérifié. Les7 et8 appels lents actifs se concentrent dans le premier quart de frames, sans troncature des détails au seuil10ms. Contexte et fenêtre sont dédupliqués ; les coordonnées distinctes ne justifient pas un cache. Cela ne devient pas deux nouvelles acquisitions.

Le [pilote de collecte](observer-overhead-measurements.md) utilise la même0.8.19 en pause :36blocs,660requêtes, fréquences1/10Hz, six ordres équilibrés par fréquence. Deux tentatives sont exclues et conservées : dérive de caméra avant verrou ; puis72réveils anticipés détectés au rejeu. La série corrigée utilise QPC et des échéances revérifiées. 992tests passent et les deux graines de rejeu produisent le même rapport.

La latence client aggregates−full diminue à10Hz dans les six paires (médiane−0,890ms), tandis que le service natif augmente (+0,04975ms). Le CPU du jeu varie et aucun gain moteur/FPS n'est établi. Le pilote reste une étude séparée des neuf cohortes/trente fenêtres ; les données de pause, navigation et combat ne sont pas regroupées en une comparaison causale. Les fichiers historiques de consolidation restent inchangés.
