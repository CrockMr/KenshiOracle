# Worker Heng 0.8.5 : rapprochement statique de la pile

Le trajet échantillonné rejoint une méthode virtuelle de **BirdManager**, classe identifiée par le RTTI du binaire. Elle dérive de **ThreadWannabe**, puis **ThreadClass**. Son corps contient notamment une recherche de voisin par distance et orientation. Cela étaye un travail de simulation des oiseaux à cet instant ; ce relevé ne mesure pas sa part du CPU et ne démontre aucune optimisation possible.

La [campagne dynamique suivante](worker-object-validation.md), sous le plugin inchangé 0.8.7 et avec de nouvelles identités de processus/threads, a depuis vérifié le vptr de l’objet dans le même minidump que son contexte. Les limites propres à l’analyse statique historique ci-dessous restent conservées.

## Périmètre et identité

Analyse statique uniquement, le 28 octobre 2026. Cible : `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe`, 36 713 984 octets, SHA-256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. VA préférée `0x140000000` ; tous les nombres ci-dessous sont des RVA, indépendantes de l'ASLR. Aucun processus du jeu ouvert, aucun hook, aucune injection ni modification de fichier du jeu par cette analyse.

Source dynamique antérieure, lue hors ligne : `runtime/stacks/heng-20261028T101436907912Z/controller.json`, sample 1, TID 10688, création FILETIME `134376529988181936`, jeu PID 33936. Pile enregistrée : RIP `0x2602a6`, retour `0x262cd0`, retour suivant `0x25fe08`. Le contrôleur indique capture et analyse hors ligne valides ; les 7 622 pointeurs SDK sont vérifiés dans ce même dump. Les deux premiers corps n'ont pas d'alias SDK. Les adresses de retour sont conservées sans ajustement à PC-1.

## Chaîne vérifiée dans le fichier

1. Les données d'unwind du RIP remontent de `[0x260210,0x2602e8)` vers `[0x2601ec,0x260210)`, puis vers la région primaire `[0x2601c0,0x2601ec)`. Celles du caller remontent de `[0x26287b,0x263664)` vers `[0x26281b,0x26287b)`, puis `[0x2627f0,0x26281b)`. Il s'agit de fragments, sans borne globale de fonction inventée.
2. L'appel à `0x262ccb` atteint le thunk `0x46254`, qui saute à `0x2601c0`. Son adresse de retour est exactement `0x262cd0` : cohérence statique avec la pile.
3. Dans `ThreadWannabe::threadProc`, l'appel virtuel au slot `+0x10`, à `0x25fe04`, a pour retour `0x25fe08`. Les arguments proviennent du float à `this+0x40` et du booléen à `this+0x44`. Le SDK déclare `backThreadUpdate(float,bool)` à ce même slot dans `Include/kenshi/PhysicsActual.h:107` ; il déclare les champs de base dans `ThreadClass.h`.
4. La vftable statique `0x16aad48` possède au slot `+0x10` le thunk `0x23bd7`, qui saute à `0x2627f0`. Ses slots `+0x08` et `+0x18` rejoignent respectivement `0x25fca0` et `0x25fbe0`, entrées SDK réelles de `threadProc` et `forceLoopMT`. Aucun commentaire RVA historique n'est employé pour cette jointure.
5. Le pointeur précédant cette vftable désigne le Complete Object Locator `0x1816d48` : signature 1, offset 0, déplacement constructeur 0, auto-RVA cohérente. Son TypeDescriptor `0x1c53d98` porte le nom RTTI **BirdManager**. La hiérarchie `0x1816d78` contient, dans l'ordre, BirdManager, ThreadWannabe, ThreadClass ; les déplacements PMD sont tous `(0,-1,0)`.

La combinaison du slot, du RTTI et des cibles soutient l'interprétation **override de BirdManager pour ThreadWannabe::backThreadUpdate**. BirdManager n'est pas déclaré dans les en-têtes KenshiLib locaux : ce résultat ne constitue pas une nouvelle API SDK, et aucun prototype ou layout de BirdManager n'est ajouté. Le vptr de l'objet dynamique n'a pas été lu ; l'attribution de classe à l'échantillon reste un rapprochement statique étayé, sans prétendre exclure tout partage de code compilé.

## Comportement minimal du trajet

Le corps à `0x2601c0` parcourt un tableau de pointeurs, avec compteur à `+0xc0` et stockage à `+0xc8`. Il ignore le demandeur lui-même et les candidats dont l'état à `+0x38` vaut 0, 4 ou 5. Les imports nommés Ogre établissent une soustraction Vector3, `Quaternion::zAxis`, `Vector3::dotProduct` et `Vector3::squaredDistance`. Il retient un candidat avec produit scalaire strictement positif et distance carrée inférieure au meilleur seuil, initialisé au carré du paramètre float. Le RIP observé est une comparaison flottante de ce seuil.

Le produit scalaire utilise l'axe Z du **candidat** et le vecteur candidat moins demandeur ; ce n'est pas une preuve que le candidat se trouve devant l'orientation du demandeur. Après sélection, le corps suit les liens `+0x30` et retourne null si la chaîne atteint le demandeur. Une sélection de voisin avec prévention de cycle est une interprétation algorithmique, pas le nom original retrouvé de cette fonction. Les significations des états restent inconnues.

Le caller `0x2627f0` parcourt des enregistrements de groupe espacés de `0xf0` octets et des listes de pointeurs internes. Les imports attestent des calculs de vecteurs/quaternions, des plans de frustum et des opérations géométriques. Des appels directs, via thunks, atteignent exactement les entrées SDK `UtilityT::getApproxTerrainHeightFromRenderer` (`0x9b1180`) et `UtilityT::random(float,float)` (`0x9b0db0`), déclarées dans `Include/kenshi/util/UtilityT.h:107` et `:83`. Cela complète le contexte sans démontrer que tous ces chemins ont été parcourus dans cet échantillon. Les types Bird et BirdGroup existent aussi dans les noms RTTI du fichier ; leur présence seule ne valide aucun layout complet.

## Preuves et limites

Sorties locales ignorées par Git dans `runtime/re-worker-085/` : `unwind-chains.json`, `call-resolution.json`, `static-vtable-refs.json`, `rtti-chain.json`, `static-validation.json`, trois sorties dumpbin bornées et scripts reproducteurs. `manifest.json` enregistre leurs tailles et SHA-256, les sources et la version de l'outil. `validate_static.py` revérifie le hash cible, les trois branches directes, les quatre slots de vftable, le slot virtuel du thread et le nom/ordre de la hiérarchie. Aucun code du jeu ni désassemblage n'est recopié dans ce document.

REA `inspect_with_objdump(file_headers)` a répondu `capability_unavailable` : objdump absent, sans Evidence ID nouveau. Aucun nouvel import Ghidra n'était nécessaire ; aucune session native ouverte et aucun nettoyage provider requis. Fallback Microsoft dumpbin **10.00.30319.01**, lectures bornées seulement. Une première commande sandbox bloquée a été interrompue proprement ; les commandes hors sandbox ont terminé. Aucun helper d'analyse restant détenu par cette sous-tâche. L'Evidence REA préalable des exports SDK reste `ev_140eb033dfeac2b7ffb9f8b9b438236f7b28d39172e5740dd25b977c7a08403d` ; elle n'est pas présentée comme Evidence du RTTI du jeu.

La première plage dumpbin commence au milieu d'une instruction ancienne ; l'analyse du helper commence à son entrée établie `0x2601c0`. La plage caller est bornée et n'établit pas un CFG complet. La table `.pdata` globale est non entièrement triée et comporte des chevauchements ; les fragments sélectionnés et les instructions ont été examinés directement, sans transformer l'index de lookup en validation Windows générale. Pas de fraction CPU, de fréquence d'appel, de nombre d'oiseaux actif, de coût exclusif, de gain ni de nom source du helper déduit de ces seules données.

Sources de format : [Microsoft : unwind x64 et chaînes](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170) ; [tests compilateur Microsoft/Clang du RTTI ABI x64](https://github.com/microsoft/clang/blob/master/test/CodeGenCXX/microsoft-abi-rtti.cpp). Ces sources expliquent le décodage ; les observations propres au jeu proviennent uniquement du fichier identifié ci-dessus.
