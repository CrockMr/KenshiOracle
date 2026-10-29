# Heng à x5 avec fenêtres bornées — 28 octobre 2026

Le scénario **pause/x5/pause** est terminé via le vrai MCP. La vitesse native reste5 pendant les observations actives, l’horloge avance de **0,933923721 h simulée en20,378680 s**, puis la copie est restaurée en pause. Les fenêtres fonctionnelles sont choisies parmi les frames réellement terminées dans chaque phase ; elles ne réutilisent aucune frame de la phase précédente.

Le plugin reste **0.8.9/v100 x64**,17 outils/trois sondes charsUpdate/findPath/MedicalSystem. Aucun algorithme moteur ni binaire modifié, aucun gain annoncé. Le relevé est descriptif : population, streaming et charge extérieure ne sont pas déterminisés.

## Contrôleur et vérifications

Commande utilisée : `tests/live_pause_cpu.py --speed 5 --adaptive-tail --tail-max 3600`. L’option de vitesse accepte les entiers1 et5, vérifie la valeur effective à chaque observation et conserve le libellé running_x5. Le mode historique sans options garde x1 et600 frames fixes.

Après vingt secondes demandées, une scène supplémentaire fournit le compteur de frames. Le nombre demandé est `min(3600, frame_observée − frame_entrée − 1)`. Une phase sans frame terminée strictement après l’entrée est refusée. Le brut conserve le plafond, la scène et le nombre demandé ; l’analyse recalcule la sélection puis contrôle la continuité et les bornes effectives. Une durée de fenêtre CPU ne devient pas pour autant une fenêtre fonctionnelle identique. Les appels sont attribués à leur fin et peuvent avoir commencé avant la fenêtre.

**536 tests passent en21,07 s**, dont vitesse fausse/non annoncée, booléens, ordre des phases, manque de nouvelles frames, compte ou borne de fenêtre contradictoire. Les rapports historiques Medical0.8.9 et Zone0.8.8 sont strictement identiques ; les champs conservés des trois analyses RIP restent inchangés. Preuve : `runtime/x5-legacy-compatibility.json`. Aucun test/build pendant les mesures.

Brut : `runtime/scenarios/pause-cpu-x5-adaptive-20261028T133051Z.json`, completed=true, SHA-256 **f1d846061c4f8f905481b82d54303e9e9c7a1d87605d315879ab666a5a0667c3**. Analyse reproductible : `mcp-server/analyze_profiled_function.py INPUT --output NOUVEAU_FICHIER`, résultat conservé dans `runtime/heng-x5-adaptive-analysis.json`. Jeu39204/création Unix1793190312.050583, chemin/commande vérifiés.

## CPU, horloge et frames

| Phase | Durée CPU processus | CPU processus | Moyenne, processeurs logiques | Progression simulée | Population aux inventaires |
|---|---:|---:|---:|---:|---:|
| Pause avant |20,390 s|36,187500 s|1,774767|0 h|403→403|
| x5 |20,375 s|46,140625 s|2,264571|+0,933924 h|435→453|
| Pause après |20,328 s|36,218750 s|1,781717|0 h|448→448|

Les inventaires sont complets et leurs effectifs concordent avec les scènes qui les encadrent. Les observations intermédiaires actives couvrent toutefois421..453 personnages ; les lectures sont asynchrones et la population évolue. La phase active n’est pas admise comme comparaison de roster complet à horloge fixe. Les résidus signés processus/threads sont **−0,046875/−0,125000/−0,015625 s**, sans omission d’identité ; ils restent conservés sans clamp ni attribution à un système.

| Phase | Frames sélectionnées | Nombre | Intervalle moyen mesuré | p99 de l’intervalle |
|---|---|---:|---:|---:|
| Pause avant |498191..500990|2800|7,276961 ms|11,1295 ms|
| x5 |501422..504179|2758|7,376880 ms|13,2390 ms|
| Pause après |504609..507284|2676|7,587717 ms|11,4859 ms|

Les trois comptes sont inférieurs au plafond3600 et ont été adaptés réellement. Ces intervalles de callback ne garantissent pas des FPS effectivement affichés. Le contexte distinct de3600 frames peut chevaucher une phase différente. Réponses fonctionnelles compactes observées48568/56923/48571 octets, contextes49578/56955/49033 : sous64 Kio pour ces captures, sans garantie universelle.

## Fonctions et threads

MedicalSystem::periodicUpdate : **27501 appels**, total mural inclusif **94,668745 ms**, moyenne0,034325 ms par frame/max appel0,149400 ms dans la fenêtre x5. Tous sur **TID13132/création FILETIME134376639240828501**, joint au rôle SDK non rendu. CPU par appel désactivé :27501 indisponibles, totaux null, sans imbrication omise ni troncature de threads. Zéro appel médical terminé dans les fenêtres des pauses.

Le thread entier13132 consomme5,90625 s CPU à x5 ; cela n’isole pas la fonction médicale. GameWorld/Renderer partagent **35744/création134376639120505844**, CPU entier16,25/15,921875/15,84375 s. Ses normalisations aux bornes propres des threads sont environ0,796334/0,781442/0,778831 processeur logique ; elles n’attribuent pas son CPU exclusivement au rendu. Le worker32156 consomme2,90625 s CPU à x5, fonction toujours non attribuée ; aucun transfert du nom BirdManager historique.

CharsUpdate moyenne0,335819 ms par frame à x5. FindPath : **778 appels sur d’autres threads**,706 true/72 false ; total mural inclusif **1314,563797 ms**, maximum172,785000 ms. Les fenêtres des pauses ont zéro appel findPath terminé. Ces temps inclusifs ne constituent pas une décomposition exclusive à additionner au CPU OS.

Les **sept appels ≥10 ms retenus** sont tous hiérarchiques et false : **162,406900..172,785000 ms murales**, somme1179,923200 ms ; CPU par appel quantifié **140,625..171,875 ms**, somme1078,125 ms. Leur coût n’est donc pas principalement une attente simple dans ces échantillons. Les coordonnées reçues start/goal XYZ forment sept couples distincts, avec paramètres radius/water/hierarchical conservés. Le quatrième composant vectoriel n’est pas utilisé comme une coordonnée spatiale dans ce rapprochement. Ni cause du retour false, ni identité de personnage, ni clé de cache complète/invalidation ne sont établies.

Ces appels portent le **TID11156**, création134376639239445460 identique aux bornes CPU ; ce thread entier consomme1,28125 s CPU sur20,375 s. Les appels se concentrent entre frames501493 et501771, au début de la phase, alors que les battements CPU vont de501420 à504182. Ce n’est pas un coût uniformément réparti sur vingt secondes. Ne pas calculer une couverture CPU exclusive entre les seuls appels retenus et le thread entier. Le détail dérivé est conservé dans `runtime/heng-x5-navigation-detail.json` ; nombres vérifiables directement depuis les sept lignes navmesh_slow_calls du brut, sans les compter une seconde fois dans le contexte élargi.

## Restitution et suite

`runtime/heng-x5-adaptive-final.json` confirme copie en pause/multiplicateur0 à **404,3333339691162 h**, caméra normale et contrôle temporaire relâché/Edge=true. Les702/702/738 fichiers source/copie/snapshot sont conformes, settings byte-identique au préalable du déploiement0.8.9, gardes false. Watchdog frais sans erreur, WPR inactif, aucun contrôleur de scénario restant. Session/bootstrap toujours bornés au28 octobre22 h15 UTC ; aucune intervention administrateur attendue.

La suite utile est de distinguer les rafales de navigation du régime établi et de compléter l’attribution du worker non rendu avec les symboles SDK vérifiés. Les requêtes lentes distinctes ne justifient pas un cache d’échecs par répétition exacte ; les durées d’échantillons ne démontrent pas un goulot global. Une comparaison x1/x5 ultérieure doit conserver ses limites d’état initial et ses propres fenêtres ; les anciennes campagnes ne constituent pas une comparaison causale ni un gain du moteur.
