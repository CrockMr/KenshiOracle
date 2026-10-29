# Piles utilisateur sans administrateur — plugin0.8.5

Les piles des trois threads ciblés de Kenshi ont été enregistrées sans administrateur, sans session ETW et sans ajouter de hook. Quatre minidumps filtrés ont ensuite été déroulés hors ligne, après restauration de la copie en pause. Le trajet actif du worker restant rejoint statiquement une méthode virtuelle de BirdManager ; son objet dynamique reste à confirmer.

Cette réserve a depuis été levée dans une [campagne distincte de vérification de l’objet](worker-object-validation.md), sous 0.8.7 inchangée. Les chiffres et identités de ce rapport restent ceux des captures 0.8.5 ; le CPU exclusif d’une fonction BirdManager reste inconnu.

La DLL0.8.5 et ses trois sondes sont inchangées. Les captures n’établissent ni un gain de performances ni une répartition statistique du CPU par fonction.

## Méthode effectivement validée

thread_minidump.py appelle MiniDumpWriteDump depuis un helper externe et filtre les threads par IncludeThreadCallback. Chaque sélection doit garder le PID, le chemin du jeu, le TID et la création FILETIME exacts. Le fichier inclut les contextes et piles des trois threads, les informations de création et une plage de métadonnées SDK vérifiée. Les segments de code/données des modules et les fenêtres d’instructions par thread sont exclus ; il n’y a aucun dump mémoire complet. Les fichiers .dmp restent locaux dans runtime, ignoré Git.

La [documentation Microsoft MiniDumpWriteDump](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump) recommande l’appel externe ; la [sélection IncludeThreadCallback](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ne-minidumpapiset-minidump_callback_type) permet de limiter les threads concernés. La bibliothèque peut les interrompre temporairement pour les capturer ; cette observation n’est donc pas passive ni sans coût.

Le helper tests/dump_stacks.cpp compile en **v100 x64** et utilise DbgEng uniquement sur les fichiers enregistrés : OpenDumpFile/GetStackTrace, jamais AttachProcess ni lancement d’un inférieur. Les chemins de symboles sont locaux et les variables de recherche réseau sont ignorées. Le déroulement et le formatage des noms se font après le retour de la copie en pause, hors de l’intervalle observé.

## La carte SDK est liée au build exact

Les commentaires RVA des en-têtes ne correspondent pas tous au binaire installé. Par exemple charsUpdateUT porte0x7857d0 dans le commentaire, mais la table de ce build donne0x785ea0. Aucun delta global n’est appliqué.

Le [contrat officiel KenshiLib](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Source/core/Functions.cpp) relie un stub à un index de table, puis à la base de l’EXE. Le fichier Steam_1.0.65.br est ici un tableau d’int32, malgré son extension. Le parser sdk_address_map.py vérifie les PE AMD64, exports, stubs FF25, table et bornes de sections. Il conserve tous les alias.

Sources exactes :

| Fichier | SHA-256 |
|---|---|
| Re_Kenshi/KenshiLib.dll |5b6240622d06801dc39896e385efb834b8e1fe2fcdf86067d071ae7a04f6c83b|
| RE_Kenshi/RVAs/Steam_1.0.65.br |573c395997ed8d93dd837e27f89a440323089edd1ba93f68291631b448f9cbd0|
| RE_Kenshi/Kenshi_x64.exe |504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e|

Les7622 stubs vérifiés correspondent à7630 entrées, dont les huit dernières pointent vers des données non exécutables et ne servent pas à nommer une fonction. Les exports nomment7618 slots, avec alias conservés. loaded_sdk_map.py vérifie aussi les en-têtes chargés, les octets des stubs et les7622 pointeurs réels. Chaque minidump x1 contient ensuite cette table : les7622 valeurs lues dans **ce même fichier** correspondent à ExeBase+RVA. La preuve n’est pas une simple supposition sur le fichier installé.

Les77508 régions .pdata du jeu comportent deux régressions d’ordre et413 chevauchements. Le parser garde ordre et indices originaux ; un index de consultation séparé ne les répare pas. Un chevauchement reste ambigu ; un nom est ajouté uniquement lorsque l’entrée SDK égale exactement le début de la région unique. Les fragments chaînés et fonctions sans région restent explicites. La [documentation Microsoft x64](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64) décrit ces régions d’unwind ; elles ne sont pas automatiquement toute une fonction source. Aucun symbole précédent n’est utilisé pour inventer une fin.

## Captures à Heng x1

Contrôleur : **runtime/stacks/heng-20261028T101436907912Z/controller.json**, completed=true, admin=false, SHA-256 **c51fb4edf498683df6de65a484f07d0dbac7197e521ddfc41c56989c1976cc06**. Les quatre dumps font149869/152789/152693/147941 octets. Chaque fichier conserve ses trois créations exactes, sa table SDK vérifiée et son empreinte. Les HRESULT du déroulement sont0, sans atteindre le plafond64 frames.

Les captures durent respectivement0,234250/0,226660/0,217172/0,232056 s dans le helper, total0,910138 s. Ces durées incluent davantage que l’éventuelle suspension des threads : elles ne mesurent pas la durée d’arrêt du jeu et ne sont pas soustraites pour annoncer un débit corrigé.

Intervalle OS englobant7,438 s, horloge+0,063837 h, vitesse1 et caméra contrôlées aux bornes de chaque capture. CPU processus2,235144 processeurs logiques moyens, résidu signé−0,03125 s et aucune omission aux bornes. Ce contexte inclut les interruptions et requêtes d’observation ; aucun contraste causal avec la campagne précédente n’est calculé.

| Thread et création FILETIME | Observation des piles |
|---|---|
|40448 /134376529869010045|Thread principal/rendu ; piles passant par Ogre et KingOfRenderThread::startup. startup est un ancêtre durable, pas une preuve de redémarrage ou de coût exclusif.|
|34252 /134376529988183642|Rôle SDK world_ai_non_render. Une pile contient MedicalSystem::periodicUpdate, une autre ZoneManager::updateRendertimeThread. Les autres captures attendent dans ThreadWannabe::threadProc. Le nom du rôle n’isole donc pas toute l’IA.|
|10688 /134376529988181936|Une capture est active aux RVA0x2602a6 puis0x262cd0, avant ThreadWannabe::threadProc. Les trois autres attendent dans cette boucle commune. Aucun alias SDK exact ; la vftable et le RTTI relient statiquement ce trajet à BirdManager.|

Les deux workers totalisent chacun2,03125 s CPU dans cet intervalle ; cela n’attribue pas ce CPU aux fonctions visibles dans quelques captures. Les comptes de piles ne sont jamais transformés en pourcentages CPU.

La région active du worker10688 est0x260210..0x2602e8 ; sa chaîne d’unwind remonte à0x2601c0. Celle de l’appelant remonte à0x2627f0. Ce sont des fragments de métadonnées, sans borne globale de fonction supposée. L’adresse de retour originale est conservée sans correction−1.

L’[analyse statique complémentaire](worker-stack-static-085.md) vérifie les appels et retours, le slot SDK `ThreadWannabe::backThreadUpdate(float,bool)`, la vftable et la hiérarchie RTTI BirdManager → ThreadWannabe → ThreadClass. Le helper effectue une sélection géométrique de voisin, avec une prévention de cycle probable. Le vptr de l’objet dynamique n’a pas été lu et un partage de code compilé n’est pas exclu. Ce rapprochement ne nomme pas toutes les fonctions, ne fournit aucune API BirdManager dans le SDK et n’attribue pas au système d’oiseaux tout le CPU du thread. Il faut confirmer l’objet puis quantifier avant de proposer une optimisation.

## Reproduction hors jeu et contrôles

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_thread_dumps.py runtime\stacks\heng-20261028T101436907912Z\controller.json --output runtime\stacks-085-analysis.json
```

Cette commande vérifie à nouveau les empreintes, threads, table SDK dans chaque dump, bornes de scènes et jointures SDK/CPU. Elle n’attache pas de processus et ne déroule pas de nouveau les piles ; les observations DbgEng sont conservées dans les résultats. Les sources de l’installation avec leurs empreintes exactes sont nécessaires pour recalculer la carte. Aucun binaire de jeu n’est distribué dans le dépôt.

**366 pytest passent en5,08 s** ;40 nouveaux tests du parser SDK couvrent PE/stubs/imports/.pdata/alias/chevauchements. Les tests minidump couvrent les données incomplètes et les slots inutilisés légitimes du répertoire. L’ABI x64 a aussi été vérifiée par compilation v100 : ADDRESS64=16, KDHELP64=112, STACKFRAME64=264, CONTEXT=1232, offsets Rsp152/Rip248.

Deux voies antérieures restent documentées :

- Le clonage PSS VA fonctionne sur notre helper mais échoue sur Kenshi avec1450 « ressources insuffisantes » ; cause exacte inconnue, pas un refus administrateur. Aucun clone n’a été conservé, aucune répétition inchangée. Voir stack-pilot-20261028T094933567322Z.json.
- Le PSS léger sans clone réussit, mais ne fournit que des RIP, pas des piles. Le premier minidump normal en pause a été acquis correctement ; son contrôleur avait refusé des slots de répertoire inutilisés0/0/0 répétés. Le parser corrigé les accepte avec test. L’original completed=false est conservé et sa revalidation hors jeu n’a pas nécessité de nouvelle capture : minidump-pilot-20261028T100423984944Z.validation.json.

Le recours à une capture utilisateur évite l’intervention administrateur pour cette question de piles. Il ne valide pas une nouvelle capture ETW ni une couverture des piles noyau. La copie a été rechargée en pause, la caméra relâchée et les702/702/738 fichiers source/copie/snapshot ainsi que settings.cfg sont conformes. La restauration ancienne de cette campagne réglait encore la vitesse par plusieurs commandes et retirait brièvement la pause. Cette limite a depuis été corrigée par la [restauration validée sous 0.8.7](pause-preserving-speed-validation.md) ; les mesures historiques ci-dessus restent celles de 0.8.5. Aucune identité complète de l’état PNJ n’est annoncée.

Le contrôle final indépendant **runtime/stacks-085-final.json** confirme PID33936/création inchangés, pause/mode normal, Edge=true et contrôle caméra relâché,17 outils/sept rôles SDK, trois sondes, watchdog frais sans erreur et WPR inactif. Les702/702/738 fichiers sont conformes et les octets settings.cfg identiques au préalable du déploiement0.8.5. Les helpers13460/14864 restent bornés à1793225700 ; aucun contrôleur de capture ne reste actif. Les empreintes du lecteur v100, de DbgEng/DbgHelp et des sources observées après capture figurent dans runtime/stacks-085-toolchain.json ; cette date n’est pas présentée comme une attestation antérieure.

Le champ runtime_binding_verified de la carte statique reste false par construction. Le champ loaded_table_in_same_dump_verified des annotations et les contrôles sdk_binding_from_dump apportent la preuve propre à chaque fichier, séparément. Cette distinction évite de réutiliser une validation de processus comme une propriété universelle de la carte.
