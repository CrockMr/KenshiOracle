# Identités des PNJ — audit de phase 1

Depuis **0.9.3**, la canonicalisation utilise l’origine de sauvegarde et les résolveurs publics du moteur. Les trois HAND sauvegardés Ando/Hisako/Ishida sont liés à des objets chargés dont C/CS diffèrent, puis publiés sous leur identité sauvegardée dans les neuf captures du trajet final 0.9.3. Les 27 captures du lot final sont validées indépendamment ; leurs octets natifs/MCP/Python concordent. Le [bilan de livraison](oracle-phase1-delivery.md) distingue cette série de la validation 0.9.5 consacrée à la restitution caméra.

L'audit historique **0.9.1**, conservé ci-dessous, étaye aussi une génération de membres à l'activation pour une cohorte précise de `ville-calme`. Il distingue cette cohorte des trois états individuels déjà présents dans l'ancienne sauvegarde. La chaîne interne responsable du changement de conteneur reste inconnue, même si la résolution moteur de ces trois paires est maintenant observée.

Le schéma d'état **0.1 reste inchangé et neutre**. Les identifiants complets `hand:TYPE:C:CS:I:S` sont toujours opaques ; le natif remplace un HAND courant par son HAND sauvegardé seulement après une liaison complète prouvée. Un nom, une position, une définition ou le couple `I/S` ne devient jamais une clé de rapprochement. Une absence d'origine résolue conserve le HAND courant et ne prouve pas à elle seule une génération.

## Preuve reproductible de l'audit historique 0.9.1

Le lecteur [npc-identity-readonly-091.py](../runtime/oracle-phase1/npc-identity-readonly-091.py) et sa sortie [npc-identity-evidence-091.json](../runtime/oracle-phase1/npc-identity-evidence-091.json) restent dans `runtime/oracle-phase1/`, ignoré par Git. Ils ne contiennent aucune copie des fichiers du jeu. Le JSON conserve les SHA-256 des sauvegardes lues, des captures comparées, du lecteur et des en-têtes SDK utiles, ainsi que les clés et les rapprochements exacts.

Depuis la racine du projet :

```powershell
.venv\Scripts\python.exe runtime/oracle-phase1/npc-identity-readonly-091.py
```

Le programme lit seulement les deux sauvegardes `%LOCALAPPDATA%\kenshi\save\KenshiProbe_test` et `ville-calme`, les captures archivées et les en-têtes référencés. Sa seule écriture est le JSON de preuve. Il ne contacte pas le jeu. Il recalcule les hashes des fichiers de sauvegarde après lecture et échoue si un contenu a changé pendant cette passe.

La lecture suit le [format FCS publié](https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/fcs-mod.md#record), confirmé par le code public de [FcsReader.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Fcs/FcsReader.cs) : en-tête de type 15, tables de propriétés typées, références et instances. Les listes finales de slots sont lues selon [SaveFile.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveFile.cs). Tous les fichiers FCS consultés atteignent exactement leur fin, listes comprises : 373 pour l'ancienne sauvegarde et 29 pour `ville-calme`. Les `.hkt` et le portrait ne sont pas décodés.

Les personnages sont reliés aux états par les identifiants d'états de leur instance, comme dans [SaveGame.BuildCharacters](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveGame.cs). Seuls les fichiers `.platoon` nommés par l'index PLATOON de `quick.save` servent de référence aux comparaisons ; six fichiers non référencés de l'ancienne sauvegarde sont exclus. Chaque comparaison d'identité utilise les cinq composantes du HAND. Les entiers signés du fichier sont rendus non signés en conservant leurs 32 bits, conformément aux champs du [SDK hand](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Include/kenshi/util/hand.h) et aux clés de [Hand.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/Hand.cs).

Ce lecteur est limité aux fichiers de type 15 observés ici ; il refuse les autres versions. Une lecture structurée réussie ne valide pas l'intégralité de la sémantique du moteur. Aucun exécutable ni code décompilé n'a été utilisé pour cette passe.

## Ville calme : personnages absents de la sauvegarde individuelle

Les neuf captures viennent de `runs/ville-calme/20261029T000108.688978Z-ed2aa999`. Les trois répétitions rechargent la même sauvegarde. Le dossier contient 21 fichiers `.platoon`, 92 états GAMESTATE_CHARACTER et 25 états PLATOON.

| Instant du jeu | Personnages, répétitions 1 / 2 / 3 | HAND exactement présents dans les états sauvegardés, par répétition | Autres HAND, répétitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| Initial | 111 / 103 / 99 | 80 / 80 / 80 | 31 / 23 / 19 |
| 120 s | 111 / 103 / 99 | 80 / 80 / 80 | 31 / 23 / 19 |
| 600 s | 124 / 135 / 132 | 92 / 92 / 92 | 32 / 43 / 40 |

À l'instant initial, les 80 HAND communs aux trois captures correspondent tous exactement à des personnages sauvegardés. L'union contient 153 HAND. Les 22 HAND d'escouades sont identiques entre répétitions et présents dans `quick.save`.

Tous les personnages initiaux sans état individuel sauvegardé appartiennent à ces trois escouades :

| État PLATOON sauvegardé | HAND d'escouade sauvegardé et observé | Effectif observé, répétitions 1 / 2 / 3 |
| --- | --- | --- |
| Holy Nation Outlaws_57 | `hand:34:40:1166015616:0:0` | 7 / 1 / 1 |
| Starving Bandits_66 | `hand:34:41:30517578:0:0` | 15 / 11 / 9 |
| Dust Bandits_120 | `hand:34:42:615844736:0:0` | 9 / 11 / 9 |

Les trois enregistrements portent `never been activated=true` et `content file=platoon/`, sans fichier de personnages associé. Leurs serials de personnages et leurs effectifs varient entre chargements, tandis que le HAND de chaque escouade reste identique. Le quatrième PLATOON dans cet état, `Dust Bandits_119` (`C=39`), n'apparaît dans aucune capture initiale. La [documentation des sauvegardes](https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/save.md#folder-and-state-mapping) précise que `platoon/` seul représente l'absence de fichier.

Ces observations étayent une création des membres à l'activation d'escouades déjà sauvegardées sous forme abstraite. Le moment exact de cette création à l'intérieur du chargement n'est pas instrumenté. Elles ne permettent pas de dire que tous les PNJ sont recréés.

Les douze personnages sauvegardés absents des captures initiales proviennent de `Shinobi Thieves_14.platoon` (8) et `Trade Ninjas_2.platoon` (4). Leurs HAND complets sont tous présents à 600 s dans les trois répétitions. Leur apparition tardive ne prouve donc pas une génération de nouveaux personnages. À 600 s, l'intersection des personnages est de 92 HAND, l'union de 207 ; les escouades ont 24 HAND communs, 29 dans l'union.

Le personnage joueur Imai garde le HAND sauvegardé `hand:1:1:751953152:1:3279785216`. Cela ne garantit pas la même propriété pour toute entité.

**Statut du runner :** les neuf dumps constituent des observations d'état. La campagne d'origine a échoué à la restitution de caméra, avec un écart d'environ 0,17248 pour une tolérance de 0,05 ; cet audit ne la présente pas comme une validation globale réussie.

## Seconde série en ville

Les neuf captures de `runs/ville-calme/20261029T001325.437085Z-06ebaeea` sont comparées aux mêmes états sauvegardés. Cette passe réutilise les métadonnées déjà hashées et les fonctions `compare_capture` / `intersections` du lecteur, sans redécoder les 402 fichiers. Ses résultats et les hashes des nouvelles captures figurent dans `additional_city_runs` du même JSON de preuve. La commande de reproduction précédente régénère la première passe ; cette annexe s'obtient en appliquant ces deux fonctions au second dossier et à `saves["ville-calme"]` du JSON.

| Instant du jeu | Personnages, répétitions 1 / 2 / 3 | HAND exactement présents dans les états sauvegardés, par répétition | Autres HAND, répétitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| Initial | 101 / 103 / 110 | 80 / 80 / 80 | 21 / 23 / 30 |
| 120 s | 101 / 103 / 110 | 80 / 80 / 80 | 21 / 23 / 30 |
| 600 s | 123 / 125 / 131 | 92 / 92 / 92 | 31 / 33 / 39 |

Les nouveaux membres initiaux appartiennent encore uniquement à `Holy Nation Outlaws_57` (1 / 3 / 7), `Starving Bandits_66` (12 / 10 / 15) et `Dust Bandits_120` (8 / 10 / 8), les trois escouades sauvegardées sans états individuels et jamais activées. Les 22 HAND d'escouades initiaux sont identiques entre répétitions. L'intersection des personnages vaut 80 HAND initialement, 92 à 600 s ; leurs unions valent 154 et 195. La seconde série reconfirme donc la distinction entre personnages sauvegardés et membres créés à l'activation, sans garantir une identité stable universelle.

Cet audit couvre les identités des dumps. La validation globale de la restitution des contrôles du second runner est rapportée séparément dans [la validation de phase 1](oracle-phase1-validation.md).

## Ancien trajet : trois états de personnages déjà sauvegardés

Les trois captures initiales de `runs/trajet-escouade/20261028T233134.179400Z-04bb9a8d` contiennent chacune 106 personnages, dont 103 HAND exactement présents dans les fichiers de personnages référencés de `KenshiProbe_test`.

Les trois autres lignes possèdent des correspondances de valeurs dans ces enregistrements sauvegardés :

| Nom observé, utilisé comme description | Fichier et état sauvegardés | HAND sauvegardé | C observé dans les trois captures |
| --- | --- | --- | --- |
| Ando | `Outlaw_8.platoon`, `18-Outlaw_8.platoon-INGAME` | `hand:1:372:2911010816:4:3090576128` | 12 |
| Hisako | `Outlaw_9.platoon`, `22-Outlaw_9.platoon-INGAME` | `hand:1:373:2914428672:5:1865356416` | 6 |
| Ishida | `Outlaw_10.platoon`, `20-Outlaw_10.platoon-INGAME` | `hand:1:374:3821533184:6:2201171968` | 4 |

Pour chaque ligne, `I` et `S`, nom, faction, race et position sauvegardée arrondie à la précision du JSON concordent dans les trois captures. `CS` varie à chaque chargement. Les PLATOON sauvegardés associés portent `imprisoned=true`, `persistent=false`, `canref=false` ; les états de personnage portent `slavestate=1` et `in something=2`.

Une vérification supplémentaire recherche directement les cinq clés binaires documentées dans chacun des trois petits fichiers : chaque clé n'apparaît qu'une fois et donne les mêmes valeurs que la lecture structurée. Ces fichiers atteignent leur fin exacte à 6 165, 7 566 et 6 808 octets respectivement.

Ces seules comparaisons de valeurs de l'audit 0.9.1 favorisaient l'explication « état restauré avec changement de conteneur », sans démontrer la chaîne d'appels responsable ni une résolution d'alias par le moteur. Leur JSON conserve cette qualification historique et tous les HAND distincts. La preuve moteur 0.9.3 ci-dessous est séparée ; `I/S` n'est toujours pas supposé globalement unique.

## Implémentation 0.9.3 : origines et résolution publique

Le [lecteur de production oracle_origins.py](../mcp-server/oracle_origins.py) est propre au projet et suit le format public de [FcsReader](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Fcs/FcsReader.cs), [SaveFile](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveFile.cs), [SaveGame](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveGame.cs) et [Hand](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/Hand.cs). Il accepte uniquement le type 15, lit les enregistrements structurés et leurs trailers jusqu'à EOF, et refuse les autres types explicitement. `byteSize` n'est pas utilisé comme une longueur de saut.

`read_saved_origins(save_root, save_name)` lit seulement `quick.save` et les `.platoon` nommés par ses états PLATOON ; `platoon/` seul signifie aucun fichier individuel. Chaque origine conserve le HAND complet, fichier relatif, ID d'état, rang et offset du record ; les personnages conservent aussi la collection, l'instance et le HAND d'escouade indexé. Des limites portent sur le nombre de fichiers, les octets, chaînes, comptages et origines. Les chemins Windows dangereux, liens/jonctions, doublons et associations ambiguës sont refusés. Les composantes int32 du fichier deviennent des décimales uint32 en conservant leurs bits.

La lecture vérifie les hashes des fichiers avant son retour. `verify_saved_origins(save_root, manifest)` les relit et compare les hashes après le chargement, avant le commit du contexte. Le fingerprint SHA-256 couvre les triplets triés chemin relatif/taille/hash de `quick.save` et des fichiers de personnages indexés ; il ne prétend pas couvrir les zones, portraits ou fichiers orphelins. Aucun fichier de sauvegarde n'est copié ni modifié. Les [tests du lecteur](../tests/test_oracle_origins.py) utilisent uniquement des fixtures synthétiques : 136 réussites, un test de création de symlink Windows ignoré faute de privilège, et un test distinct réussi pour le refus de l'attribut reparse.

Le [chargement MCP](../mcp-server/oracle_runner.py) prend la racine publique `SaveManager::getSavePath()` comme référence et refuse une configuration contradictoire. Il lit le manifeste avant `load_save`, attend un monde prêt et en pause, revérifie la source puis transmet les HAND complets par `begin_saved_origins`, `add_saved_origins` en lots d'au plus 128, et `commit_saved_origins`. Aucun contexte partiel n'est publié. Le nom demandé au chargement et l'époque de monde déterminent le contexte ; `SaveManager::getCurrentGame()` n'est pas traité comme une preuve de ce nom.

La sonde construit un HAND avec le constructeur public [`hand(index, serial, type, container, containerSerial)`](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Include/kenshi/util/hand.h), puis appelle `getCharacter()` ou `getPlatoon()`. Le candidat retourné doit correspondre à un objet du recensement chargé ; son pointeur n'est pas déréférencé pour obtenir une identité. La commande de lecture `resolve_saved_handles` expose séparément `saved_id`, `current_id` ou `null`, `resolved` et `loaded`. Elle exige la pause et accepte au plus 128 HAND complets.

La [table native](../plugin/OracleSavedOrigins.h) courant ↔ sauvegardé impose une bijection de HAND complets et refuse les collisions. La preuve est construite au commit avant publication atomique du contexte ; les liaisons sont actualisées avant les captures et conservées seulement pour les HAND courants encore recensés. Une égalité complète peut aussi conserver un objet mort encore chargé, même si le résolveur ne le retourne plus. Le cache ne conserve aucun pointeur d'objet. Un nouveau chargement, un monde indisponible ou une transition de monde invalide ce contexte, y compris lorsqu'une adresse de monde est réutilisée.

La canonicalisation native remplace les IDs de personnages et d'escouades, `squad_id`, cibles d'ordre, membres et chefs par les seules liaisons prouvées, puis trie les collections et refuse les doublons. Les autres références restent sous leur HAND courant. `identity_source`, avec nom, fingerprint et compteurs, appartient à la réponse de l'outil et au rapport, hors de l'état commun 0.1. Un dump sans contexte préparé échoue avec `origin_context_required`. Le suivi de caméra de personnage utilise également la table publiée au commit. La récupération 0.9.5 avec suivi canonique d’Imai et décalage XYZ volontaire est vérifiée dans [le bilan de livraison](oracle-phase1-delivery.md), séparément de cet essai initial.

## Première preuve réelle 0.9.3 et limites

Le fichier local [identities-smoke-093.json](../runtime/oracle-phase1/identities-smoke-093.json), hors Git, contient `completed=true`. Le contexte de `KenshiProbe_test` compte **1 470 origines**, **138 liaisons chargées**, **trois personnages remappés** et **zéro escouade remappée**. Les trois appels publics observés résolvent ces paires :

| HAND sauvegardé | HAND courant retourné dans le recensement chargé |
| --- | --- |
| `hand:1:372:2911010816:4:3090576128` | `hand:1:12:1312499968:4:3090576128` |
| `hand:1:373:2914428672:5:1865356416` | `hand:1:6:3035278336:5:1865356416` |
| `hand:1:374:3821533184:6:2201171968` | `hand:1:4:2488159232:6:2201171968` |

Les trois lignes du dump portent les HAND sauvegardés ; les trois HAND courants correspondants n'y figurent plus. Les 106 personnages, 35 escouades, 114 factions et 12 882 relations forment un état 0.1 valide, de 1 125 265 octets, identique dans les sorties native, MCP et canonique Python : SHA-256 `ec6ab440861f637f1d1e087fd712b06be0b58e2147e6f44662cf5dd0fe0e9824`. La source d'identités porte le fingerprint `sha256:c9a3ec246336efb3ea9fb68f48753f3910131590931caf496ba14826c864379d`. Le même essai conserve le refus explicite d'un dump sans préparation.

Dans ce relevé, `ping.current_save` indique encore `ville-calme` tandis que le contexte préparé et la source vérifiée nomment `KenshiProbe_test`. Ce diagnostic confirme qu'un getter interne de nom peut rester périmé après chargement ; la source du contexte vient du chargement explicitement demandé et des fichiers vérifiés.

L'implémentation règle l'ancien TODO de remappage et la résolution moteur est observée pour ces trois personnages. Elle n'explique pas la chaîne interne des redirections et ne démontre pas une identité universelle entre parties, sauvegardes ou redémarrages. Aucune absence d'origine résolue n'est convertie en preuve de génération. Cet essai initial ne valide pas un remappage d'escouade, la restitution réelle d'un suivi canonique de caméra, ni les trois répétitions de la candidate finale. Ces validations et le statut de publication sont à consulter dans [le bilan de livraison](oracle-phase1-delivery.md).

Les autres pistes publiques restent sans garantie d'identité globale : `RootObject::getInstanceID()` / `getLayoutInstanceID()` ne sont pas démontrés stables sur les personnages ; `Platoon::getPlatoonStringID()` concerne l'escouade ; `getGameData()->stringID` peut être partagé ; `Character::getIDForMemoryTagging()` renvoie encore un HAND. Aucun accès supposé au singleton de `HandleManager`, aucun nom, aucune position et aucun couple I/S ne remplace la preuve complète.

