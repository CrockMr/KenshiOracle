# Collecte 0.8.20 : confirmation randomisée avec CPU du serveur MCP

**La réduction du CPU du serveur MCP reste indéterminée.** À 10 Hz, `aggregates − full` produit trois différences CPU positives et trois négatives ; à 1 Hz, la différence médiane en secondes CPU est nulle. En revanche, le service natif et la latence client diminuent dans les six paires à chaque fréquence. À 10 Hz, leurs différences médianes valent respectivement **−1,93242 ms** et **−3,58830 ms**.

Cette confirmation randomisée est acceptée : **36 blocs, 660 lectures, 330 réveils de témoin, aucun saut**. Elle complète le [pilote 0.8.20](direct-aggregate-statistics-measurements.md) avec le CPU propre au serveur MCP. Elle conserve la DLL et le processus du jeu, mais observe 78 personnages chargés contre 106 précédemment, avec une autre position de caméra. L'activité concurrente peut aussi varier. Aucun gain FPS n'est démontré.

## Préenregistrement vérifié

Le [préenregistrement](../runtime/observer-randomized-20261028T222552055152Z/registration.json) est figé avant capture, SHA-256 **`fc972fefec0fbe94c659256aea7dced759ae0c81703cc13be729f6cf2f643103`**. Il conserve :

- graine entière de randomisation **`4337799577124482768`**, issue d'un unique tirage 64 bits avant acquisition ;
- plan intégral des 36 blocs, protocole `observer-overhead-randomized-v2`, version 0.8.20 et SHA des 20 sources ;
- [protocole préalable](randomized-observer-protocol.md), SHA-256 `0402cc30da4a523b26aff2393b6a04d9afc8edf7dfa5c3b84d14351a72223f96` ;
- DLL `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e` et manifeste de symboles `7305c48a0a7b9466c6780bbb276e973ff0d068f5017b270fa7d6039d8ee54e62` ;
- Python 3.12.14, MCP 1.30.0 et psutil 7.2.2, versions enregistrées pour cette exécution.

La suite précédant ce préenregistrement rapporte **1143 tests réussis en 41,98 s**. Ce résultat valide les contrôles logiciels testés, pas les performances du jeu. Le document de protocole reste inchangé après préenregistrement.

## Plan exécuté et portées

Chaque bloc vise 5 s, après une attente neutre de 1 s et les contrôles communs. Les conditions sont `baseline` sans getter, `get_frame_stats(n=60, detail='full')` et `detail='aggregates'`, à 1 ou 10 Hz. Les six permutations sont présentes une fois par fréquence ; les 12 triades sont mélangées par `make_plan(seed)` sans modifier leur ordre interne. Le préenregistrement précède le début d'expérience déclaré par le contrôleur d'environ 21,19 s. Le rejeu confirme le plan exact, les 660 lectures, les 330 réveils, l'absence de rattrapage ou de chevauchement, les identités, les bornes et la restitution. Le retard maximal de départ des requêtes est **16,893 ms**.

Les unités de comparaison sont les **six paires de blocs d'une même fréquence**. Pour les requêtes, la médiane est d'abord calculée dans chaque bloc, puis soustraite entre conditions de la même triade. Les niveaux présentent la médiane et l'étendue des six médianes de blocs ; les comparaisons appariées conservent les six différences, leur médiane, leur étendue et leurs signes. Les requêtes ne sont pas regroupées comme autant d'expériences indépendantes.

Le service natif et la latence MCP restent des durées murales distinctes. Les octets correspondent au réencodage compact du résultat, sans enveloppe de transport. Les moyennes de callbacks, le CPU du processus jeu, de Root et du contrôleur restent des diagnostics séparés ; le service natif n'est pas assimilé à du CPU exclusif.

## Périmètre du CPU serveur

Le serveur MCP persiste pendant la série. Son identité enregistrée comporte PID, date de création, exécutable, arguments, PID parent et jeton de lancement. Le serveur est **PID 17160**, création `1793226372.3372936`, via le launcher venv **25292**, création `1793226372.3123753`, enfant du contrôleur **1888**, création `1793226371.4070983`. Les chemins, arguments, jeton et chaîne parentale correspondent aux observations. Seul le CPU du **processus serveur identifié** est retenu ; le launcher et une somme récursive d'enfants sont exclus.

Chaque bloc dispose de compteurs utilisateur/noyau avant et après, associés à des bornes QPC propres au serveur et englobant la fenêtre de requêtes. Les deltas sont normalisés par leur propre durée. Le CPU serveur n'est additionné ni au CPU contrôleur ni au CPU jeu comme s'ils partageaient des bornes identiques.

Les valeurs quantifiées et les zéros sont conservés. Un delta CPU nul ne prouve pas l'absence d'exécution ; aucune réduction relative n'est calculée en divisant par une référence nulle. Les comparaisons principales privilégient les différences signées en secondes CPU et en équivalents de processeur logique. Les omissions de threads et résidus signés du jeu restent visibles, sans clamp ni attribution inventée.

## CPU serveur : niveaux et différences signées

Les niveaux sont la **médiane [minimum ; maximum] des six blocs** de chaque condition. Le temps CPU est utilisateur + noyau du seul serveur ; l'équivalent logique divise chaque delta par l'intervalle propre de ce bloc.

| Hz | Condition | CPU serveur par bloc, s | Équivalent de processeur logique | Blocs avec delta CPU nul |
|---:|---|---:|---:|---:|
| 1 | baseline | 0 [0 ; 0] | 0 [0 ; 0] | 6/6 |
| 1 | full | 0,015625 [0 ; 0,031250] | 0,003016 [0 ; 0,006043] | 2/6 |
| 1 | aggregates | 0,015625 [0,015625 ; 0,031250] | 0,003007 [0,002992 ; 0,006052] | 0/6 |
| 10 | baseline | 0 [0 ; 0] | 0 [0 ; 0] | 6/6 |
| 10 | full | 0,156250 [0,078125 ; 0,375000] | 0,030156 [0,015099 ; 0,072066] | 0/6 |
| 10 | aggregates | 0,140625 [0,093750 ; 0,171875] | 0,027128 [0,018098 ; 0,032986] | 0/6 |

Les comparaisons principales `aggregates − full` sont :

| Hz | Delta CPU serveur, médiane [min ; max], s | Signes négatif / nul / positif | Delta équivalent logique, médiane [min ; max] |
|---:|---:|---:|---:|
| 1 | 0 [−0,015625 ; +0,031250] | 2 / 2 / 2 | −0,00001506 [−0,00303856 ; +0,00605177] |
| 10 | −0,015625 [−0,250000 ; +0,046875] | 3 / 0 / 3 | −0,00302509 [−0,04792787 ; +0,00899465] |

À 1 Hz, dans l'ordre des triades 1/2/4/6/8/10, les six deltas sont **+0,031250 ; +0,031250 ; −0,015625 ; 0 ; −0,015625 ; 0 s**. À 10 Hz, pour les triades 0/3/5/7/9/11, ils sont **+0,031250 ; −0,046875 ; −0,250000 ; −0,156250 ; +0,046875 ; +0,015625 s**. Le cas complet le plus élevé contribue à la large étendue à 10 Hz ; les signes ne soutiennent pas une baisse uniforme.

Les deltas CPU observés sont quantifiés en multiples de **15,625 ms**. Les douze témoins et deux blocs complets à 1 Hz ont un delta nul à cette résolution. Ce n'est pas une preuve de coût nul. Deux paires à 1 Hz ont exactement le même delta CPU dans les deux conditions mais une différence d'équivalent logique légèrement négative, parce que leurs durées d'observation diffèrent : la normalisation ne crée pas une économie de CPU démontrée. Aucun ratio utilisant un témoin nul n'est présenté.

Les comparaisons secondaires au témoin reflètent ces mêmes valeurs : à 1 Hz, `full − baseline` est positif dans quatre paires et nul dans deux, `aggregates − baseline` positif dans les six. À 10 Hz, les deux traitements sont positifs dans les six paires. La mesure du serveur est désormais disponible, mais l'hypothèse d'une diminution reproductible de son CPU avec `aggregates` reste **indéterminée dans cette série**.

## Service, client et volume

Chaque cellule est la **médiane [minimum ; maximum] des six médianes de blocs**. Les médianes internes portent sur cinq requêtes à 1 Hz et cinquante à 10 Hz.

| Hz et réponse | Octets JSON par résultat | Service natif, ms | Latence client MCP, ms |
|---|---:|---:|---:|
| 1, full | 35 985 [35 971 ; 35 990] | 2,19970 [2,17190 ; 2,39420] | 11,82005 [9,96630 ; 13,73510] |
| 1, aggregates | 3 946 [3 944 ; 3 949] | 0,22715 [0,22500 ; 0,23600] | 9,03490 [7,01520 ; 10,53880] |
| 10, full | 35 986,75 [35 985 ; 35 989] | 2,16445 [2,13840 ; 2,20900] | 11,52673 [10,67140 ; 11,74630] |
| 10, aggregates | 3 945 [3 944 ; 3 947] | 0,23005 [0,22760 ; 0,24355] | 7,82847 [7,27945 ; 8,85880] |

Les six différences `aggregates − full` sont négatives pour le service, la latence client et les octets à chacune des deux fréquences :

| Hz | Service, médiane [min ; max], ms | Client, médiane [min ; max], ms | Octets, médiane [min ; max] |
|---:|---:|---:|---:|
| 1 | −1,97385 [−2,15820 ; −1,94170] | −2,59050 [−6,71990 ; −0,65860] | −32 038 [−32 046 ; −32 025] |
| 10 | −1,93242 [−1,98120 ; −1,90640] | −3,58830 [−4,29400 ; −1,93815] | −32 041,5 [−32 044 ; −32 039] |

La réduction appariée du service a une médiane de **89,733 % [89,216 ; 90,143]** à 1 Hz et **89,283 % [88,961 ; 89,688]** à 10 Hz. Ce sont les médianes des six ratios par paire, pas les ratios des médianes de niveau. L'attente en file varie dans les deux sens : différence médiane +0,66520 ms à 1 Hz, +0,02422 ms à 10 Hz. Le bénéfice de latence observé ne peut donc être attribué exclusivement à l'attente en file, au CPU serveur ou au service natif.

## Callbacks et CPU du jeu : diagnostics distincts

Les cellules donnent **médiane [minimum ; maximum] ; nombre de différences positives sur six**. Les trois colonnes CPU sont des équivalents logiques, calculés avec leurs intervalles respectifs. Un signe positif signifie une valeur supérieure au témoin indiqué.

| Hz | Traitement − référence | CPU jeu | CPU Root | CPU contrôleur | Callback moyen, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | +0,00328 [−0,13697 ; +0,25619] ; 3/6 | −0,02417 [−0,05687 ; +0,01650] ; 1/6 | −0,00136 [−0,00587 ; +0,00602] ; 3/6 | +0,01704 [−0,18684 ; +0,05138] ; 4/6 |
| 1 | aggregates − baseline | +0,06383 [−0,12909 ; +0,21813] ; 4/6 | −0,01980 [−0,06062 ; +0,02533] ; 2/6 | +0,00136 [−0,00300 ; +0,00567] ; 3/6 | +0,05464 [−0,14526 ; +0,19286] ; 4/6 |
| 1 | aggregates − full | +0,03816 [−0,28579 ; +0,35510] ; 4/6 | +0,01841 [−0,04835 ; +0,03308] ; 5/6 | +0,00134 [−0,00569 ; +0,00861] ; 3/6 | +0,09153 [−0,11550 ; +0,16230] ; 4/6 |
| 10 | full − baseline | −0,03379 [−0,10782 ; +0,14207] ; 2/6 | −0,01052 [−0,04683 ; +0,02936] ; 3/6 | +0,00901 [−0,00614 ; +0,02104] ; 4/6 | +0,16595 [+0,01911 ; +0,29687] ; 6/6 |
| 10 | aggregates − baseline | −0,08238 [−0,15657 ; +0,29956] ; 2/6 | +0,00616 [−0,04603 ; +0,04928] ; 4/6 | +0,00898 [−0,00618 ; +0,01511] ; 5/6 | +0,02283 [−0,05453 ; +0,14071] ; 3/6 |
| 10 | aggregates − full | −0,02837 [−0,18488 ; +0,31476] ; 2/6 | +0,00655 [−0,02046 ; +0,03102] ; 4/6 | −0,00002 [−0,02085 ; +0,01182] ; 3/6 | −0,13727 [−0,25105 ; −0,04645] ; 0/6 |

À 10 Hz, les six paires montrent un callback moyen plus court avec `aggregates` qu'avec `full`, tandis que `full` dépasse le témoin dans les six. Les autres CPU et le résultat à 1 Hz restent mixtes. Les callbacks sont des intervalles de télémétrie ; aucune conversion en FPS affichés ou attribution CPU exclusive n'est faite.

Les témoins varient eux-mêmes : leurs moyennes de callbacks couvrent 6,78910–6,99519 ms à 1 Hz et 6,70610–6,93866 ms à 10 Hz. Leur CPU processus couvre respectivement 1,56355–1,68457 et 1,50874–1,82943 équivalent logique. La pause, l'heure et les inventaires stables ne prouvent pas une charge interne constante. La randomisation ne supprime ni le bruit de la machine ni les effets persistants entre blocs ; cette série unique ne fournit aucun test de significativité ou d'équivalence.

## Fenêtres, identités et restitution

| Fenêtre | Minimum, s | Médiane, s | Maximum, s |
|---|---:|---:|---:|
| Requêtes | 5,00040 | 5,00605 | 5,01592 |
| CPU jeu | 5,06206 | 5,07445 | 5,10272 |
| CPU thread Root | 5,06684 | 5,08012 | 5,10532 |
| CPU serveur MCP | 5,16076 | 5,18388 | 5,22590 |
| CPU contrôleur | 5,16076 | 5,18389 | 5,22592 |

Les intervalles serveur et contrôleur sont proches mais distincts ; ils ne sont pas fusionnés. Les statistiques finales contiennent **732–778 callbacks** par bloc, obtenus en une requête avec n conservé et sous le budget de 3600. Leurs intervalles cumulés couvrent 5,19534–5,26985 s, avec des bornes différentes de celles des compteurs OS. Les contrôles et le réencodage finaux se trouvent hors de la fenêtre CPU du jeu ; un effet sur le bloc suivant reste possible.

Le jeu reste **28932 / création `1793224737.4120193`**. Root conserve **T23968 / FILETIME `134376983374120248`**, même liaison d'export et identité de service dans chaque réponse. Les 110 scènes sous verrou — 108 lectures de blocs plus référence et prélibération — conservent **78 personnages chargés, une ville active**, pause, multiplicateur zéro et heure `404.3333339691162`. Le pilote 0.8.20 précédent observait 106 personnages : le même PID et la même DLL ne suffisent pas à rendre les deux scènes identiques.

Deux threads OS, T40144 et T41080, ne sont pas observés à l'endpoint final du bloc d'indice 5 ; ils restent omis. Le résidu signé processus moins threads calculables va de **−0,375000 à +0,203125 s**, médiane −0,015625 s. Il est conservé sans clamp et ne représente pas une consommation assignable à une fonction.

L'audit indépendant confirme la copie en pause à la même heure, contrôle de caméra libéré, `free_camera=false`, Edge restitué, settings inchangé, gardes inactives et **702/702/738 fichiers** conformes pour validation/copie/snapshot. Le watchdog et ses helpers 21020/40676 restent actifs conformément à l'autorisation de poursuite. Le nettoyage MCP n'a pas employé de secours (`cleanup_events=[]`) ; la scène finale est lue en TCP direct. Les sources et la DLL sont inchangées.

La caméra a bougé d'environ **12,561 unités avant la référence verrouillée**, puis de **10,786 unités après libération**. Sa stabilité pendant la mesure ne signifie pas restauration des coordonnées initiales. L'audit du transport constate séparément la fin des processus serveur **17160**, launcher **25292** et contrôleur **1888** ; il ne termine aucun processus. Le watchdog du jeu n'est pas confondu avec ces processus de mesure.

## Preuves et rejeu

| Preuve | SHA-256 |
|---|---|
| [Capture acceptée](../runtime/scenarios/observer-randomized-20261028T222614566229Z.json), 28 002 828 octets | `3c99c2e0ec9b0b64b9c95f4aedbd1fc6df5caa4894b8235f0c4023e45391873f` |
| [Rapport analysé](../runtime/randomized-observer-seed0.json), 142 152 octets | `ba49c0ff37ce1b479c0a999266626a5973ffc385634d1944f79bc07edb0ac31d` |
| [Preuve des deux rejeux](../runtime/randomized-observer-replay-proof.json) | `4000a2f5e44c256795298dbc0459f978c3601be9a2610525ccd349d81c2d5f57` |
| [Audit final du jeu et des fichiers](../runtime/randomized-observer-final.json) | `30b7f7ed702c4cd187123af46bee8561e60b667272864ae7a6d679bdc91c335e` |
| [Audit de fin du transport](../runtime/randomized-observer-transport-final.json) | `5ca086521ffb3ee381afc95e3ceadae2addeb1f2c1b0351c468630441a4b7caa` |

Les graines de hachage Python `0` et `8675309` produisent des rapports identiques octet par octet. Elles contrôlent la stabilité du rejeu, sans modifier la graine de randomisation ni constituer deux acquisitions. La preuve conserve les 20 SHA de source ; l'analyseur a pour SHA `920a930faa286ffc3816259d5b07e17a1a1f9fc0e555871ce842b2813bfb0c2e`, le contrôleur `3be16ca2a9e88bf6c51171e912259ce324c3dba483d4bc86e002813a028cf530`.

Rejeu hors jeu depuis la racine du projet, avec un nom de sortie neuf ; le SHA de capture est exigé et un fichier existant est refusé :

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe mcp-server/analyze_observer_randomized.py `
  runtime/scenarios/observer-randomized-20261028T222614566229Z.json `
  --expected-version 0.8.20 `
  --expected-sha256 3c99c2e0ec9b0b64b9c95f4aedbd1fc6df5caa4894b8235f0c4023e45391873f `
  --output runtime/randomized-observer-replay-new.json
```

Les niveaux et différences ci-dessus proviennent de `result.blocks`, `result.paired` et `result.paired_request_comparisons`. Le hash externe du préenregistrement est vérifié séparément de son contenu déclaré dans la capture. La conclusion reste limitée : service et latence client plus courts dans ces paires, CPU serveur sans baisse fiable démontrée, aucune conclusion de gain FPS ou de réduction globale du coût du moteur.
