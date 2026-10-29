> État actif : plugin **0.8.1**, rôles SDK conservés ; cible IA sélectionnée update4Frame, [relevé actuel](ai-target-selection-measurements.md). Les chiffres 0.7.9 et antérieurs ci-dessous restent historiques.

# Rôles de threads SDK — état courant 0.7.9

**Le chargement de ressources et le générateur de navigation sont désormais reliés à des identités Windows exactes, mais ils n'expliquent pas le worker restant le plus coûteux dans cet essai.** Les sept rôles exposés correspondent à cinq threads vérifiés, un alias physique et une identité de sauvegarde indisponible. La version 0.7.9 reste à 17 outils MCP et trois sondes de systèmes, en v100 x64 ; aucun algorithme du moteur n'est remplacé.

## Accès SDK groupés

ResourceLoader.h déclare ResourceLoader::getInstance() et l'héritage public ThreadClass (base secondaire, ajustée par le compilateur C++). SaveFileSystem.h déclare getSingleton() et l'héritage ThreadClass. NavMesh.h expose publiquement generator ; NavMeshGenerator.h définit son héritage ThreadClass. Les getters sont liés par la bibliothèque SDK officielle et appelés réellement en jeu. Aucun décalage de base n'est réencodé, aucun constructeur n'est appelé. Lecture facultative uniquement depuis le callback principal, monde prêt en pause et sans save/load en attente ; aucune nouvelle lecture du champ name ni nouveau hook.

Les rôles facultatifs resource_loader, save_file_system et navmesh_generator s'ajoutent à world_physics_interface. Les trois rôles initiaux restent obligatoires. La réanalyse des données 0.7.7 conserve exactement la jointure historique mise en cache (runtime/sdk-077-compatibility-079.json). Les alias et les rôles présents à une seule borne ou non vérifiés gardent leur traitement explicite.

SaveFileSystem existe ici, mais son champ SDK threadID vaut 0 et son identité n'est pas exploitable : available=true, identity_verified=false, CPU inconnu. Cela ne signifie ni un coût nul de toute sauvegarde ni l'absence de threads délégués.

## Relevé à Heng

- Nouveau jeu PID **7716** après archive crashes/20261028T055854044666Z-deployment-079 (ancienne DLL 0.7.8/config/préférences/journal, motif deployment_0.7.9).
- Smoke : runtime/sdk-079-smoke.json ; les sept lignes sont rendues, six identités de rôle vérifiées dont l'alias physique, une identité indisponible.
- Brut MCP : **runtime/scenarios/sdk-roles-20261028T060036Z.json**, SHA-256 **4e64161ad08bb63fe22e9eeb0a7bf29718d0e541e1e6f5464ff146758f3c4367**.
- Analyse recalculée : **runtime/sdk-079-analysis.json** ; état final **runtime/sdk-079-final.json**.

Le scénario recharge la copie, prépare Heng, stabilise le streaming, lit les rôles en pause, exécute x1 puis mesure vingt secondes demandées. Il relit les rôles en pause et restaure la copie. Pas de pytest pendant l'intervalle CPU. Les identités SDK encadrent les scènes et correspondent aux TID/créations des deux bornes OS.

**48,234375 secondes CPU en 20,375 secondes réelles = 2,367331 processeurs logiques moyens.** L'horloge avance de 0,186876 heure, population de 406 à 446. Cinq threads manquent à la seconde borne et sont explicitement exclus ; résidu signé processus moins somme couverte **−0,046875 s CPU**, non normalisé.

| Rôle SDK | TID | CPU du thread entier (s) | Processeurs logiques moyens | Part du processus |
| --- | ---: | ---: | ---: | ---: |
| world_ai_non_render | 23468 | 5,500000 | 0,269939 | 11,4027 % |
| world_navmesh | 32120 | 0,171875 | 0,008436 | 0,3563 % |
| physics_backthread | 19104 | 0,953125 | 0,046779 | 1,9760 % |
| world_physics_interface | 19104 | même thread que ci-dessus | même thread | même thread |
| resource_loader | 16792 | 0,078125 | 0,003834 | 0,1620 % |
| navmesh_generator | 40520 | 0,000000 mesuré | 0,000000 mesuré | 0,0000 % mesuré |
| save_file_system | inconnu | inconnu | inconnu | inconnu |

Le zéro du générateur est un delta de compteur quantifié, pas une preuve d'absence absolue de travail. Les rôles vérifiés restent stables avant/après. Après déduplication de l'alias physique : **5 threads uniques, 6,703125 s CPU, 0,328988 processeur logique, soit 13,8970 % du CPU processus**. L'analyse expose known_sdk_thread_cpu séparément de la jointure historique pour conserver les anciens caches. Elle ne somme jamais deux fois le même TID/création.

Le worker non identifié **TID 19272**, création FILETIME **134376407470372177**, consomme **6,500000 s CPU / 0,319018 processeur logique** ; le suivant, TID 33784, 0,183282. Ils ne sont attribués à aucune fonction par ordre de création ou ressemblance avec les anciennes versions. Le tableau porte sur des threads entiers, pas les coûts exclusifs de toutes les ressources/IA/navigation/physique. Aucune comparaison de gain entre versions, panneau RE_Kenshi non vérifié visuellement, charge des autres applications non quantifiée.

## Validation, restauration et prochaine hypothèse

**230 pytest passent en 3,99 s**, avec rôles distincts/alias/identité indisponible, couverture CPU dédupliquée et inconnus conservés. Compilation/liaison v100 x64 réussies avant déploiement ; les nouveaux getters et conversions sont confirmés en jeu. Le paramètre natif facultatif reste fonctionnel et les chaînes mal typées refusées. Le lancement masqué Start-Process libère le handle parent ; aucun avertissement Popen observé.

Le jeu **7716**, watchdog wrapper **12552**/enfant **37596**, sont les identités du contrôle final, à relire avant action. Copie rechargée en pause, vue normale de référence, Edge scrolling=true, combat suivi inactif et contrôle temporaire relâché. **702/702/738 fichiers** source/copie/ancien snapshot conformes ; settings.cfg byte-identique au préalable, gardes false. Watchdog frais sans erreur, autoload réussi ; échéance et activation **1793225700** inchangées. Aucun contrôleur de mesure actif. L'ancien snapshot existe sur disque mais sa propriété en mémoire n'est plus présumée.

Ces nouvelles identités écartent les deux objets comme explication majeure de ce CPU dans cet échantillon. Un profilage CPU identique ne préciserait pas les fonctions du worker inconnu. Prochaine hypothèse exploitable sans quatrième sonde : mesurer les appels publics AI::_NV_periodicUpdate(float), dans AI/AI.h, en **remplacement** de la sonde physique peu coûteuse, avec cumul par identité de thread et vérification des signatures/liaison. Cela peut isoler un coût inclusif de fonction sur un thread connu ou inconnu ; aucune optimisation avant preuve, aucun GetRealAddress sur le membre virtuel periodicUpdate lui-même. Le pilote de piles CPU administrateur reste en attente ; ne pas répéter la question ni l'erreur sans changement utilisateur.

Les nombres d'anciennes sections ci-dessous appartiennent à leurs processus et restent historiques.

# Historique : rôles de threads SDK — 0.7.8

**L'interface physique principale et son back-thread sont le même thread Windows dans les scènes vérifiées.** Cette piste n'ajoute donc pas un worker identifié. La version 0.7.8 reste à 17 outils MCP et trois sondes de systèmes ; aucun algorithme du jeu n'est remplacé.

## Nouvelle preuve sans répéter le CPU

PhysicsActual.h déclare publiquement PhysicsInterface : ThreadWannabe : ThreadClass, et GameWorld.h expose physics. Le lecteur facultatif ajoute world_physics_interface à côté de physics_backthread, avec le même contrôle de TID/PID/création et les mêmes gardes de pause/save/load. Aucun nouvel offset ou hook.

Après chargement de KenshiProbe_test, puis à Heng après dix secondes de simulation x1 et stabilisation, les deux rôles ont la même identité : **PID 30380, TID 16028, création FILETIME 134376399467422055**. Deux lectures en pause à Heng, frames 8453 et 8854, retrouvent cette identité ; 404 personnages dans les deux lectures. Les autres rôles observés sont world_ai_non_render TID 30104 et world_navmesh TID 32792. Ces identités appartiennent à ce processus et ne se joignent pas aux mesures des anciennes versions.

- Smoke MCP et contrôles natifs : runtime/sdk-078-smoke.json.
- Scène Heng : runtime/scenarios/sdk-alias-20261028T054744Z.json, SHA-256 **0a5f46ea9ca3cad0663f364c66d53abb419ae0f61d1ba9e37adc0809b250677e**.
- Contrôle final : runtime/sdk-078-final.json.
- Archive de déploiement : crashes/20261028T054533762503Z-deployment-078 ; motif deployment_0.7.8, ancienne DLL 0.7.7/config/préférences/journal conservés.

Le contrôleur n'a pas exécuté un nouvel intervalle CPU : l'alias ne fournit aucune attribution supplémentaire à mesurer. Les chiffres CPU 0.7.7 ci-dessous restent historiques. Aucun pourcentage n'est transféré au PID 30380 ; aucun gain entre versions n'est annoncé. L'observation de l'alias ne garantit pas son invariance dans toute partie ou version du jeu.

## Compatibilité et défaut corrigé

Les trois rôles initiaux restent obligatoires pour l'analyse ; world_physics_interface est facultatif. Les anciens relevés se réanalysent sans modifier leurs jointures mises en cache, attesté par runtime/sdk-077-compatibility-analysis.json. Si le rôle supplémentaire n'est présent qu'à une borne, son CPU reste inconnu. Les alias comptent comme une seule identité, et non deux consommateurs à sommer. Les rôles inconnus, doublons ou rôles obligatoires manquants restent refusés.

Le contrôle préalable a révélé que l'appel natif sans thread_details échouait sous 0.7.7 avec missing field, alors que le serveur MCP fournissait toujours false. **0.7.8 rétablit la valeur par défaut false au niveau natif** : omission et false explicite validés réellement en jeu, chaîne mal typée toujours rejetée. Le serveur MCP conserve sa validation booléenne. Aucun changement du nombre d'outils.

**227 pytest passent en 3,78 s.** La compilation initiale en environnement restreint a échoué C1902 (gestionnaire PDB), puis la compilation autorisée locale et la liaison v100 x64 ont réussi. Installation après liaison réussie. Le watchdog est lancé avec Start-Process -WindowStyle Hidden et son handle parent est libéré explicitement ; aucun avertissement Popen observé lors de ce lancement. Les chemins --config sont comparés après résolution, car PowerShell a produit un mélange de séparateurs valide.

## État restauré et suite

Jeu 30380, watchdog wrapper 2440/enfant 32296 lors du contrôle final : revérifier chemin/commande/création avant toute action. Copie rechargée en pause, caméra normale de référence, Edge scrolling=true, combat suivi inactif et contrôle temporaire relâché. **702 fichiers source, 702 copie et 738 ancien snapshot** tous conformes ; settings.cfg byte-identique au préalable, gardes de récupération false. Watchdog frais sans erreur, échéance/activation **1793225700** inchangées. Les contrôleurs de test ont terminé. Aucun contrôle visuel du panneau RE_Kenshi après ce redémarrage.

Le worker restant de 0.7.7 n'est pas identifié par cet ajout. Les en-têtes contiennent d'autres objets ThreadClass accessibles : ResourceLoader::getInstance(), SaveFileSystem::getSingleton() et NavMesh::generator (NavMeshGenerator). Ces accès sont seulement repérés, ni liés ni lus dans 0.7.8 ; il faudrait vérifier leurs déclarations complètes, durée de vie et liaison avant toute extension. Éviter une succession de redémarrages pour un champ à la fois. Autre hypothèse ciblée : AI/AI.h déclare AI::_NV_periodicUpdate(float), dont une sonde pourrait remplacer la sonde physique peu coûteuse ; coût inclusif et appels délégués resteraient à distinguer. Ne pas dépasser trois sondes, ne pas appeler GetRealAddress sur une méthode virtuelle. Le pilote de piles CPU administrateur reste en attente ; aucune nouvelle tentative sans changement.

# Historique : rôles de threads SDK reliés au CPU — 0.7.7

Un worker consommateur est maintenant relié à l'objet retourné par **GameWorld::AINonRenderThread()** : son thread représente **0,271672 processeur logique, soit 11,40 % du CPU du processus**, dans le relevé x1 à Heng. Le navmesh et le back-thread physique sont également reliés à des identités Windows exactes. Ces rôles décrivent les threads référencés par des objets SDK ; ils n'isolent pas les fonctions qui ont consommé ce CPU.

La version **0.7.7 est compilée/liée en v100 x64, installée et validée par MCP stdio réel**, avec toujours **17 outils et trois sondes de systèmes**. Aucun nouveau hook : l'évolution ajoute une lecture facultative à get_scene_state. Aucun algorithme du moteur n'est remplacé.

## Sources et contrat de lecture

Les accès viennent des en-têtes SDK installés :

- GameWorld.h : AINonRenderThread(), navmesh et physics.
- PhysicsActual.h : PhysicsInterface::getBackthread(), héritage ThreadWannabe puis ThreadClass.
- NavMesh.h : héritage ThreadClass.
- ThreadClass.h : threadHandle et threadID.

`get_scene_state(thread_details=true)` exige un monde prêt, **en pause**, sans chargement ou sauvegarde en attente. Par défaut false, aucune de ces requêtes d'identité n'est effectuée. Le serveur valide le booléen et la DLL le revérifie. Le paramètre ne crée pas un dix-huitième outil.

Pour chaque objet, le lecteur copie le TID SDK, duplique son handle avec le seul droit THREAD_QUERY_LIMITED_INFORMATION, puis vérifie **GetThreadId, GetProcessIdOfThread et GetThreadTimes**. Le TID doit correspondre au champ SDK et le PID au jeu courant. La création FILETIME est rendue comme chaîne décimale exacte. Seule la copie du handle est fermée par un garde de portée ; le handle emprunté au jeu n'est jamais fermé. Aucun pointeur ou handle brut n'est conservé dans la réponse ou entre lectures.

Le champ public name n'est pas lu, faute de garantie sur ses modifications concurrentes. Les libellés world_ai_non_render, world_navmesh et physics_backthread décrivent les accès SDK employés ; ils ne viennent pas de noms Windows ou d'une pile déduite. Le drapeau identity_verified atteste l'identité, pas que le thread est actuellement en cours d'exécution ni qu'il n'effectue qu'un système. Objet absent, handle invalide ou désaccord sont rendus sans inventer un TID valide.

## Preuves et déploiement

- Archive : `crashes/20261028T051812394044Z-deployment-077`, ancienne DLL 0.7.6, configuration, préférences et journal ; motif `deployment_0.7.7`, pas crash du moteur.
- `runtime/deploy-077.json` : identités relues avant arrêt du jeu 19920 et des watchdogs 19296/36144, empreintes de DLL. Seuls les processus du projet ont été arrêtés.
- Nouveau jeu **25120**, watchdog wrapper **6412**/enfant **10988** au contrôle final, chargement automatique de la copie confirmé.
- `runtime/sdk-077-smoke.json` : trois identités SDK/Windows vérifiées en pause.
- Brut : `runtime/scenarios/sdk-roles-20261028T052110Z.json`, SHA-256 **966b4871b06953bce3d52dc75a378e2e131227302ab709d58fe693842c5108f9**.
- Analyse recalculée depuis le brut : `runtime/sdk-roles-analysis.json`.
- État final : `runtime/sdk-077-final.json`.

Le parent Python de déploiement a affiché un avertissement de finaliseur Popen, WinError 6, après le lancement détaché. Le watchdog et son jeu ont ensuite été vérifiés réellement actifs, sans erreur de publication ; l'avertissement du parent n'est pas classé comme crash du jeu ni passé sous silence. Pour un futur lancement détaché, préférer Start-Process masqué et une gestion explicite du handle du parent, puis vérifier les processus.

## Mesure x1 à Heng

Le contrôleur prépare Heng depuis KenshiProbe_test, laisse le streaming prévu et capture les rôles en pause. Il active x1, laisse trois secondes de stabilisation, puis mesure vingt secondes demandées avec compteurs CPU OS par thread et scènes toutes les 0,5 seconde. Après la mesure, une seconde lecture en pause doit retrouver les mêmes rôles et créations. Une requête de détails en cours de simulation a été **refusée nativement**, comme prévu, sans modifier la vitesse.

Le processus consomme **48,531250 secondes CPU en 20,360 secondes réelles**, soit **2,383657 processeurs logiques moyens**. L'horloge avance de 0,186529 heure, la population observée varie de 415 à 430. Un thread manque à la seconde borne et reste explicitement exclu ; le résidu signé processus moins somme des threads vaut **−0,171875 seconde CPU**, sans normalisation.

| Rôle de l'objet SDK | TID vérifié | Secondes CPU du thread entier | Processeurs logiques moyens | Part du CPU du processus |
| --- | ---: | ---: | ---: | ---: |
| world_ai_non_render | 26984 | 5,531250 | 0,271672 | 11,3973 % |
| world_navmesh | 5372 | 0,093750 | 0,004605 | 0,1932 % |
| physics_backthread | 18656 | 0,953125 | 0,046814 | 1,9639 % |

Les créations sont identiques avant/après et correspondent exactement aux échantillons CPU. Les trois rôles sont distincts dans ce cas ; le protocole permet néanmoins des alias, et l'analyse compte les identités uniques plutôt que sommer automatiquement les rôles.

Le worker **16564**, environ **0,333067 processeur logique**, reste en tête des threads hors de ces trois rôles et du service principal. Son rôle n'est pas attribué par proximité de TID, ordre de création ou ressemblance avec un ancien processus. Les anciennes données 0.7.5/0.7.6 ne sont pas jointes au nouveau PID.

Ces valeurs portent sur les threads entiers. Elles ne sont ni le coût exclusif de toute l'IA, de toute la navigation ou de toute la physique, ni une pile de fonctions. La population, les caches et les autres applications ne sont pas fixés pour une comparaison entre versions. Le panneau RE_Kenshi n'a pas été vérifié visuellement après ce démarrage ; aucun gain de performances n'est annoncé.

## Reproduction et validation

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_sdk_thread_roles.py
& ./.venv/Scripts/python.exe mcp-server/analyze_sdk_thread_roles.py runtime/scenarios/sdk-roles-20261028T052110Z.json
```

La première commande conduit un nouvel essai et restaure la copie ; la seconde réanalyse seulement le brut. Le rapport refuse une jointure mise en cache contradictoire, une régression de frame ou des lectures SDK qui n'encadrent pas les scènes de l'intervalle CPU. Identité changée/non vérifiée ou thread absent d'une borne donne une valeur inconnue, jamais un zéro inventé.

**222 tests Python passent en 3,96 s**, dont booléen transmis/validé, désaccords SDK/noyau, TID réutilisé, alias et bornes de preuve. La DLL a aussi rejeté le paramètre natif mal typé ; preuve dans le contrôle final. Les captures réelles attestent la liaison SDK et les trois getters en jeu.

Les **702 fichiers de KenshiProbe_validation, 702 de KenshiProbe_test et 738 de l'ancien snapshot** restent conformes. settings.cfg est identique avant/après déploiement et essai ; les gardes de récupération restent false. Copie rechargée en pause, vue normale de référence, Edge scrolling=true, aucun combat suivi actif ou contrôle temporaire. Watchdog frais, zéro erreur de publication, échéance **28 octobre 22 h 15 UTC** inchangée. Aucun helper de mesure ne reste actif.

La prochaine preuve utile doit préciser le worker restant ou les fonctions exécutées par le rôle non rendu. PhysicsInterface hérite lui aussi de ThreadClass : le rôle de l'interface world->physics pourrait être comparé à celui de getBackthread(), sans présumer qu'ils soient distincts. Une telle extension doit rester compatible avec les anciens relevés à trois rôles et ne pas ajouter de hook. Le pilote de piles CPU administrateur reste en attente ; aucun contournement de politique n'a été effectué.
