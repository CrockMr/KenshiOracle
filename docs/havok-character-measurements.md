# HavokCharacter::update — 0.8.10

La sonde retrouve **528882 appels terminés** sur le rôle SDK non rendu à Heng x5. Dans les2832 frames sélectionnées, ils totalisent **105,071372 ms murales inclusives**, moyenne **0,037101 ms par frame**, maximum **0,059500 ms par appel**. Aucun appel terminé dans les fenêtres des pauses. Ce coût observé ne suffit pas à expliquer le CPU du worker entier et ne constitue pas un coût CPU exclusif.

La version0.8.10 compile en **v100 x64**, est installée et vérifiée par le vrai MCP. **544 tests passent en21,96 s**, essais natifs sélecteur/buckets/profondeur réussis. Toujours17 outils/trois sondes charsUpdate/findPath/Havok ; Medical est remplacée dans l’unique emplacement sélectionnable, aucun algorithme moteur modifié ni gain annoncé.

## Pourquoi cette fonction

Les douze RIP du moteur déjà capturés sur le rôle non rendu dans la série séparée0.8.9 sont annotés dans `runtime/worker-rip-089/annotations.json`. Le brut source conserve SHA **3d8cab8cf198d92ef47033ad7f56ab79f60c12d1a66fd196608a12c90657875d**. Les outils du projet vérifient le même processus historique39204/création native134376639120505830, les bases/modules conservés, les exports/stubs SDK et les valeurs de toute la table chargée avant/après l’annotation. Cette liaison est vérifiée au moment de l’annotation, sans prétendre avoir lu la table pendant la capture historique.

Cinq régions rejoignent une entrée SDK nommée : NavMesh::getClosestPoint, Character::getCharacterMemoryTag, Blackboard::getMissionTown, HavokCharacter::update et Character::isInCombatMode. Chacune n’est observée qu’une fois ; cinq autres régions n’ont pas d’alias SDK et deux adresses n’ont pas de région unwind. Aucune recherche du symbole voisin ne remplace ces inconnues. Les métadonnées .pdata conservent leur ordre irrégulier et les ambiguïtés éventuelles ; une région unwind ne définit pas forcément tout le corps d’une fonction source. Ces comptes ne donnent aucune fréquence CPU par fonction.

HavokCharacter.h:98 déclare **public void update(float time)**, méthode non virtuelle, non statique et non const. Header7012 octets, SHA **0cc4b2e36748a9259d1f728d79974638950c8a2350c4f77a7bffa8099294dcf9**. Revue indépendante du sous-agent sdk_stack_mapping : export unique/slot3912, entrée réelle0x147f90 et région `[0x147f90,0x148a77)` contenant le RIP0x1483a9. Le commentaire historique0x147eb0 du header diffère ; aucune de ces adresses numériques n’est copiée dans le plugin.

Le skill REA a été appliqué pour la vérification native. Son ouverture confirme l’EXE SHA **504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e**, mais la première requête Ghidra expire pendant l’import/analyse à330 s. Aucun résultat de contenance Ghidra n’est revendiqué ; aucune erreur mémoire n’a été confirmée. Diagnostic complet `runtime/worker-rip-089/rea-container-timeout.json`. Selon sa remédiation, le délai temporaire de prochain démarrage est porté à900000 ms, puis la session est fermée : open=false/cleanup_pending=false, preuves recovery-cleanup/after-close conservées. Aucun import identique relancé ; signature et appairage SDK indépendants suffisent pour cette sonde. Les annotations des outils Python ne sont pas présentées comme des Evidence REA.

## Implémentation et déploiement

`KENSHI_PROBE_FUNCTION_TARGET=havokCharacterUpdate`, original et wrapper typés `void(HavokCharacter*,float)`, argument float transmis inchangé, original appelé une fois. GetRealAddress résout `&HavokCharacter::update` ; AddHook conserve le trampoline typé. La garde de profondeur et les buckets existants sont réutilisés ; le verrou de collecte ne couvre pas l’appel original. Aucun cast depuis AI*, aucune modification d’objet/layout. Ping annonce `havok_character_update_profiling`, les statistiques génériques portent le vrai nom ; alias Medical/Zone/IA/charsUpdateUT/physique inactifs.

CPU par appel désactivé ; création de thread conservée par le cache TLS indépendant. Les528882 appels n’ont pas de mesure CPU, totaux null, pas des zéros mesurés. L’instrumentation a un coût non soustrait. Le build signale le décalage class/struct EdgeCache dans les headers SDK ; compilation et liaison réussissent sans nouvelle correction de dépendance.

Archive `crashes/20261028T140020118382Z-deployment-0810`, preuve `runtime/deploy-0810.json`, anciens jeu39204/helpers14112/33564 fraîchement vérifiés avant leurs seuls arrêts. DLL0.8.9/config/settings/journal préservés. Le premier watchdog échoue avant de lancer un jeu car le nouveau script omettait PYTHONPATH ; journaux `runtime/watchdog-0810-first-launch.*.log` conservés. Script corrigé avec chemins absolus, lancement masqué réussi ; le premier smoke expiré pendant cette absence de jeu n’est pas un crash moteur. Le second smoke réussit : `runtime/havok-0810-smoke.json`.

Symboles propres0.8.10 sous runtime/symbols/0.8.10 : DLL SHA **b2e0a24dadf6ebc0b1f75e8d5fbdad9e1cbf9ba082a7782061a669335c2b8c19**, PDB **d61f24277080dd68bf4b799c5fa35499c3874268b1abb7bf6d066305f6a6e4f3**. Aucun fichier du jeu, SDK, sauvegarde ou code décompilé dans le checkpoint des sources propres.

## Heng pause/x5/pause

Brut `runtime/scenarios/pause-cpu-x5-adaptive-20261028T140511Z.json`, completed=true, SHA **60d74111457fa6d932efd5bf41d19fbf8fee96c3c497f0e57ba535ec8355f34a**. Analyse finale `runtime/havok-0810-analysis-stable.json`, reproductible avec analyze_profiled_function.py. Le premier rapport `runtime/havok-0810-analysis.json` est conservé. Aucun test/build pendant la mesure.

Son rejeu a révélé un classement instable lorsque plusieurs threads partagent le même maximum CPU quantifié. Le tri ajoute maintenant TID puis création comme critères d’égalité, y compris au seuil des douze lignes retenues. Deux tests contrôlent les ex æquo et des processus Python à graines de hachage distinctes. `runtime/havok-0810-canonical-compatibility.json` rejoue sept rapports : tous les compteurs et lignes conservées sont recalculés depuis les bruts ; seul l’ordre d’ex æquo du premier rapport Havok change, sans changement de membres. Les six rapports historiques précédents gardent leurs champs. Cette correction d’analyse n’a nécessité aucun nouvel essai dans le jeu ni nouvelle DLL.

| Phase | Frames/nombre | CPU processus moyen | Progression simulée | Inventaires complets |
|---|---|---:|---:|---:|
| Pause avant |7622..10842/3221|1,796779 processeurs logiques|0 h|400→400|
| x5 |11260..14091/2832|2,388037|+0,933182 h|423→456|
| Pause après |14541..17365/2825|1,744572|0 h|456→456|

Durées OS20,375/20,375/20,313 s, CPU processus36,609375/48,65625/35,4375 s. Résidus signés **−0,015625/+0,046875/−0,046875 s**, une identité sans seconde borne en première pause et deux en dernière, aucune omission x5. Horloge active+0,933181763 h sur20,361778 s ; les inventaires concordent avec les scènes qui les encadrent, mais population et streaming évoluent. Les moyennes d’intervalle de callback6,319963/7,177477/7,178946 ms et p999,5978/11,5935/11,0167 ms ne garantissent pas des FPS affichés.

Tous les appels Havok x5 sont sur **TID39604/création FILETIME134376698083790089**, joint aux compteurs Windows et au rôle SDK world_ai_non_render. Zéro entrée imbriquée omise/troncature. Ce thread entier consomme **6 s CPU** sur20,375 s, dont4,046875 user/1,953125 kernel. Aucune couverture exclusive calculée entre les appels muraux et cette fenêtre OS. Le thread principal/rendu34996/création134376697962686336 consomme16,078125 s CPU à x5 ; le worker5844 consomme5,09375 s, fonction inconnue. Ne pas y transférer les anciens TID ou le nom BirdManager.

Les fenêtres finales de pause ont zéro appel Havok. Le contexte final de3600 frames contient encore64462 appels, car il chevauche la phase active ; ce n’est pas une activité Havok pendant la fenêtre finale en pause. Payloads compacts des fenêtres48456/57444/48469 octets, contextes48459/58551/48933, sous64 Kio dans ces captures. La navigation compte1227 appels à x5 ; cela ne définit pas le coût exclusif du worker non rendu.

## État final et suite

`runtime/havok-0810-final.json` confirme jeu **19264/création Unix1793196196.268632**, copie en pause/multiplicateur0 à **404,3333339691162 h**, caméra normale/contrôle temporaire relâché/Edge=true. Les702/702/738 fichiers source/copie/snapshot sont conformes, settings identique au préalable de ce déploiement, gardes false. Watchdog frais sans erreur, WPR inactif, aucun contrôleur restant,17 outils/sept rôles/trois sondes. Aucun accès administrateur demandé. Helpers17784/32436 identifiés dans l’audit ; revérifier exe/commande/création avant arrêt. Échéance28 octobre22 h15 UTC inchangée.

La faible durée de cette méthode dans la condition mesurée ne l’exclut pas de tout pic futur. Il faut poursuivre une condition de combat lourde ou une frontière SDK plus large correctement résolue, en séparant les rafales initiales du régime établi. Les noms de fonctions, comptes de RIP et coûts de threads entiers ne suffisent pas à annoncer le goulot ni une optimisation ; les campagnes successives ne sont pas une comparaison causale.
