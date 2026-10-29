# charsUpdate : appel, intervalle vers le verrou et identité du thread

**0.8.15 sépare les deux intervalles du timer historique.** À Heng/x5,1855 appels totalisent **550,117199 ms pour l’appel original** et **0,136396 ms après celui-ci jusqu’à l’acquisition du verrou de télémétrie**. Ce second intervalle représente **0,024788 %** du total historique de550,253596 ms dans cette fenêtre. Il inclut horloge et ordonnancement : ce n’est pas du CPU ni de la contention pure. Aucun appel n’est admis dans les deux fenêtres en pause.

Le thread **28836/création FILETIME134376802586702846** correspond aux IDs du jeu et du service Renderer aux deux bornes,avec création Windows vérifiée indépendamment par les endpoints CPU. Aucune jointure à un rôle SDK non rendu n’est trouvée. Cela localise cette entrée instrumentée ;une durée faible à cette frontière n’exclut pas du travail délégué ou exécuté ailleurs. Aucun gain moteur/FPS n’est annoncé.

## Frontière de mesure et API

Le vieux hook prenait sa fin après `Guard` ;le champ `charsUpdate_mean_ms` contenait donc l’appel original plus l’intervalle jusqu’à l’acquisition de ce verrou. Sous0.8.15,GetCurrentThreadId et la création TLS sont résolus avant le départ,la fin est prise immédiatement après l’original,puis une troisième horloge suit l’acquisition de Guard. L’original est appelé une fois,verrou hors original. Le champ historique garde son périmètre « jusqu’au verrou » ;les champs supplémentaires distinguent les intervalles.

Signature SDK relue : **void GameWorld::charsUpdate()**,GameWorld.h ligne216 ;symboles fournis **?charsUpdate@GameWorld@@QEAAXXZ** et import correspondant dans KenshiLib.lib. Header SHA **e1c5566b24df65a42d01e884ac8a45125a3b257298469a544ad557b7f43e802f**,bibliothèque SHA **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Le binding demeure GetRealAddress/AddHook existant,sans RVA copié. Les signatures des hooks de service existants ont aussi été relues :MainLoop_GPUSensitiveStuff(float),Renderer::_NV_update(). Aucun nouvel appel Game,layout SDK ou quatrième hook système.

`systems.charsUpdate_split` expose les comptes,totaux/moyennes par frame/maxima de `call_wall`, `post_call_to_lock` et `legacy`,huit identités TID/création au maximum,overflow non attribué et indicateur de troncature. Les moyennes divisent par le nombre de frames retenues,pas par le nombre d’appels. Tous les appels terminés sont comptés,nestés inclus s’il y en a ;les temps sont inclusifs et peuvent se chevaucher. CPU désactivé/null,création FILETIME en chaîne exacte,un échec initial restant inconnu pour la durée de vie TLS.

L’admission au bucket intervient **à l’acquisition du verrou** ;l’appel peut avoir commencé ou fini avant sa frontière de frame. Les bornes des statistiques sont celles des buckets,pas une preuve que chaque portée originale est contenue dans l’intervalle CPU. Deux champs par frame ajoutent call_wall et calls ;l’agrégat fournit post_call_to_lock séparément. Une durée quantifiée à zéro n’est pas l’absence d’appel :le compte reste nécessaire.

## Variante lente rejetée et contrôle A/B

**0.8.14 n’est pas une version validée.** Elle embarquait le nouveau bucket dans chaque Sample,portant celui-ci de696 à1392 octets. Le smoke a expiré après120 s de chargement ;le mêmePID12240 a ensuite été prêt en pause,mais le tail10 mesurait **258,952410 ms/frame**,9 nouvelles frames en2328,671 ms et2,453125 s CPU processus,avec zéro appel charsUpdate. Aucune phase active de cette version n’a été lancée.

Preuves :**runtime/chars-0814-slow-cadence.json**,audit protégé **runtime/chars-0814-before-ab.json**. Source propre exacte et manifest **runtime/source-checkpoint-0814-rejected.json** :186 sources sélectionnées,snapshot **runtime/source-snapshots/0.8.14-rejected-cadence**,manifest SHA **d124cf3a5389848c38cb442264ebd248dd1d2b3e830e4c6b6905fec7b5ebaa23**. Aucun jeu,SDK,sauvegarde ou binaire dans ce snapshot de sources. Les tests691 et le helper natif étaient passants :ils ne remplaçaient pas la validation réelle de cadence.

Retour contrôlé au binaire propre0.8.13,identités fraîchement vérifiées,archive **crashes/20261028T164443639055Z-diagnostic-ab-return-0813**,preuve runtime/deploy-chars-ab-0813.json. Le contrôle **runtime/chars-ab-0813-cadence.json** retrouve **6,683460 ms/frame**,73 nouvelles frames/514,344 ms. Les fichiers protégés restent identiques.

La candidate0.8.15 conserve Sample à **696 octets** et utilise un **CharsHistory préalloué/tagué de2523600 octets**,3600 emplacements. Copie/reset sous le même verrou que le legacy ;aucune allocation spécifique chars par frame,tag manquant=erreur et jamais zéro. Les slots inactifs d’un bucket ne sont pas effacés après clear ;size=0 les exclut,chaque réemploi écrit identité et totaux. Le contrôle **runtime/chars-0815-cadence.json** retrouve **6,551690 ms/frame**,78 nouvelles frames/513,947 ms,puis la campagne complète conserve sa cadence. **La cause interne précise de la variante0.8.14 n’est pas établie** :ne pas inventer un défaut d’allocateur,ABI ou GPU sur ces seuls changements de stockage et lancements.

Le maximum brut est désormais Sample3600×696=2505600 octets plus ring2523600,soit **5029200 octets**,hors conteneur et temporaires. Ce n’est pas une réduction de mémoire globale par rapport aux5011200 octets bruts de0.8.14 ;le stockage et le profil d’allocations diffèrent. L’ancienne version0.8.13 utilisait2505600 octets bruts pour les Sample seuls.

## Vérifications natives et coût de l’observateur

`tests/test_chars_telemetry.cpp` couvre bucket/merge/overflow,TID réutilisé avec création différente,unknown/reset,écrasement ring1→3601 et erreur de tag manquant. Un helper retient volontairement le verrou après l’appel synthétique ;les captures prouvent la séparation des intervalles sans agir sur le jeu. Le premier build du test manquait NOMINMAX,puis correction ;un test de ring modifiait son propre frozen input avant une assertion15 appels,fixture isolée puis corrigée. Aucun de ces rejets n’était un échec d’appel Game.

**runtime/chars-native-0815/controller.json**,SHA **247cc6a96445e42fdf567c9df0c430b95f845c7022d0a52ce886251a00ab7a69**,conserve stdout et binaires propres,empreintes des sources,header/bibliothèque et symboles SDK. Les preuves0.8.14 restent séparées sous runtime/chars-native-0814. Microbenchmark v100/O2/x64,single-thread sans contention,création TLS préchauffée :3 processus×7 paires×100000 appels,durée complète timer/enregistrement moyenne **0,067416 µs legacy contre0,105523 µs split**,écart0,038108 µs. Charge ambiante et quantification restent présentes ;exclus premier GetThreadTimes,copie/reset d’historique,merge Sample,construction JSON et coût réel global de sonde.

**691 tests Python passent en22,29 s**,39 contrôles nouveaux ;natifs v100 réussis. L’analyse vérifie appels/totaux/moyennes/maxima,legacy=call+post,threads/overflow,identités précises et séries tronquées ou complètes. Les profils CPU restent des endpoints OS distincts,recalculés depuis les compteurs bruts,avec résidus signés non bornés.

## Campagne réelle Heng

CopieKenshiProbe_test rechargée avec protection de pause/verrou Edge,préparationHeng,10 s x1 et disponibilité stable,puis trois phases12 s demandées,pause/x5/pause,3 s de warmup chacune. Observations demandées toutes0,5 s,inventaires complets bornés à500 aux deux extrémités,rôles SDK copiés en pause avant/après la séquence. L’horloge game_total_hours est immobile en pause et avance de **0,5752525329590412 h** dans la phase active ;game_time_stamp brut ne sert pas à mesurer la simulation.

| Phase | Frames retenues | Intervalle moyen ms | p99 ms | Calls chars | Appel moyen/frame ms | Post moyen/frame ms |
|---|---:|---:|---:|---:|---:|---:|
| Pause avant |1982|6,324554|8,5173|0|0|0|
| x5 |1855|6,746956|8,8393|1855|0,296559|0,000073529|
| Pause après |1922|6,533679|9,0457|0|0|0|

Actif :appel original total550,117199 ms,max0,891700 ms ;post total0,136396 ms,max0,001600 ms ;legacy550,253596 ms,moyenne0,296633 ms/frame. Aucun overflow ou thread chars non vérifié dans ces fenêtres. Le thread28836 rejoint les IDs GameWorld/Renderer au heartbeat des deux bornes et les créations OS des deux endpoints ;aucun rôle SDK brackettant ne porte cette identité. CPU du **thread entier9,859375 s**,pas CPU de ces appels.

Processus CPU :22,078125/31,3125/23,53125 s sur12,563/12,547/12,593 s,soit **1,757393/2,495616/1,868598 processeurs logiques**. Résidus signés **+0,1875/−0,03125/+0,03125 s**,aucune omission d’identité d’endpoint. Populations observées405..405/435..440/440..440 ;ces phases successives changent aussi de temps et d’environnement. **Pas de comparaison causale ni de soustraction des sondes murales concurrentes au CPU/temps de frame.** Les intervalles instrumentés ne garantissent pas les FPS affichés.

Les trois requêtes principales sont admises sans réduction :n1982/**55058 octets**,n1855/**62409**,n1922/**55063** compacts réencodés depuis le résultat. Ces nombres ne sont pas le fil TCP exact ;la limite native64 Kio reste en vigueur. Le contrôleur conserve le budget et les éventuelles erreurs de taille,réduit uniquement les getters si nécessaire ;aucun manque interprété comme zéro.

Capture **runtime/scenarios/chars-split-20261028T170111506769Z.json**,completed=true,SHA **f553cfba8aab37bbf54824ab3b7a688be34a9c41b3f4de128970f7992ddb3b2a**. Rapport **runtime/chars-split-0815-analysis.json**. Rejeu :

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_chars_split.py runtime\scenarios\chars-split-20261028T170111506769Z.json --expected-sha256 f553cfba8aab37bbf54824ab3b7a688be34a9c41b3f4de128970f7992ddb3b2a --output runtime\nouveau-rapport-chars.json
```

## État final

DLL0.8.15 **298496 octets/SHA3a7f6f2839dcd8eedf4057b1532adb8854edb0c704d674b5e41d82c63115c45e**,PDB propre **10374144 octets/SHA62b151b60e4243de0cd651d42884db7f4774ec7cc6fcf397c63a548a64763b32**,sous runtime/symbols/0.8.15. Archive **crashes/20261028T165719366149Z-deployment-0815**,preuve runtime/deploy-0815.json ;ancienne version et preuves de la variante rejetée conservées. Toujours17 outils,trois sondes charsUpdate/findPath/Havok,v100 x64 ;FUNCTION_THREAD_CPU=0,AI_THREAD_CPU=0,NAV_THREAD_CPU=1,COMMAND_TIMING=1. Pas d’algorithme moteur modifié.

Audit indépendant **runtime/chars-split-0815-final.json** :même jeu **15772/création Unix1793206658.6702836**,copie restaurée en pause/multiplicateur0 à **404,3333339691162 h**,caméra normale/contrôle temporaire relâché/Edge=true,bataille inactive. **702/702/738 fichiers** source/copie/snapshot conformes,settings byte-identique au préalable de déploiement,gardes false,watchdog frais/zéro erreur,WPR inactif,aucun contrôleur restant. Helpers **34588/création1793206656.1918323** et **35104/création1793206656.1481395**,à revérifier fraîchement avant arrêt. Dernier audit stats n3600 admises en55048 octets compacts.

La mesure montre ici un petit intervalle post-appel ;elle ne localise pas le reste d’une frame de6,75 ms ni tout le travail des personnages. Une prochaine sonde doit répondre à la question du thread principal,en réutilisant au besoin un hook de service existant comme cible sélectionnée **à la place d’Havok**,pour garder trois systèmes profilés et éviter une seconde installation sur la même adresse. Vérifier prototypes/bindings et distinguer service/commande de l’original avant tout changement. Aucun résultat de cette future mesure n’est annoncé.

Échéance autonome22 h15 UTC/23 h15 Paris inchangée ;aucune intervention utilisateur/administrateur attendue.
