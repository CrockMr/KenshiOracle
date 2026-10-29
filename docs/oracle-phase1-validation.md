# Validation de l'oracle phase 1 — 29 octobre 2026

> Rapport historique. Le [bilan de livraison 0.9.5](oracle-phase1-delivery.md) et la [grille d’acceptation](phase1-acceptance.md) décrivent les sources, tests et validations finales ; les résultats ci-dessous gardent leur version et leur portée initiales.

Complément ultérieur : la [ville calme et la correction du contrôle caméra](oracle-ville-calme-validation.md) portent les séries réussies à neuf répétitions et 27 captures, et la suite Python à 1 310 réussites. L'[audit des PNJ](npc-identities-phase1.md) distingue génération à l'activation et changement de conteneur d'entités sauvegardées. Les mesures ci-dessous restent historiques ; elles ne sont pas rétroactivement soumises à la nouvelle fenêtre de stabilité.

La sonde **0.9.1**, avec les contrats d'état et de scénario **0.1**, a exécuté trois répétitions réelles de `trajet-escouade`, puis trois de `petite-bataille`, via le serveur MCP stdio. Les **18 captures** de ces deux campagnes réussies sont conformes au schéma et leurs octets correspondent exactement à la normalisation Python et aux fichiers natifs sources. Déplacement, ordre d'attaque, blessures et restitution des contrôles propres aux scénarios sont observés dans les conditions détaillées ci-dessous. Le retour final à la pose de caméra antérieure à la phase n'est toutefois **pas validé exactement**. Les états complets diffèrent entre répétitions : cette validation ne démontre pas un déterminisme universel de Kenshi. Un premier essai de bataille terminé en échec de restitution reste conservé séparément.

## Périmètre et preuves locales

Le jeu observé est Kenshi **1.0.65 Steam**, plugin **0.9.1**, instance `34736:1222705718`. La campagne commence le 28 octobre 2026 à 23:31 UTC, soit le 29 octobre en heure de Paris. Elle ne constitue pas une campagne de performance. Les preuves volumineuses restent dans les répertoires locaux ignorés par Git :

- `runtime/oracle-phase1/live-trajet-091.json` : résultat MCP, identité du processus aux bornes, neuf empreintes de captures, contrôles avant/après et vérification des sauvegardes protégées.
- `runs/trajet-escouade/20261028T233134.179400Z-04bb9a8d/report.json` et `report.md` : exécutions, chargements, actions, instants réels et comparaison champ par champ.
- Dans ce même répertoire, `scenario.json`, puis `1/`, `2/`, `3/` avec les captures `initial.json`, `en-route.json`, `arrivee.json` et les journaux `execution.json`.
- `runtime/oracle-phase1/first-real-dump.json` : première preuve de capture réelle, antérieure à la campagne répétée.
- `runtime/oracle-phase1/native-canonical.json` : comparaison du format C++/Python sur 59 états synthétiques, distincte des captures réelles.

Le scénario archivé recharge `KenshiProbe_test` à chaque répétition, choisit la vitesse 1, envoie à l'instant 0 un ordre `move` à l'escouade `hand:34:1:3701293824:0:0`, puis capture aux instants 0, 120 et 600. Les actions à un même instant précèdent la capture : `initial` contient donc déjà l'ordre de déplacement. Une commande de pause à 600 précède la dernière capture. Chaque instant est une durée en **secondes du calendrier du jeu** depuis l'horloge relevée après ce rechargement, et non une durée murale.

## Mouvement et identités observées

Les deux personnages gardent leur identité, leur escouade et leur position initiale dans les trois répétitions :

| Personnage | Identifiant | Position initiale x, y, z |
| --- | --- | --- |
| Ryers | `hand:1:1:3701293824:1:1415283200` | `50533.593750, 1005.236938, -13895.199219` |
| Okada | `hand:1:1:3701293824:2:1858032256` | `50540.773438, 1005.285950, -13891.675781` |

Leur tâche initiale est `move_cus_ordered`, avec la destination demandée `50573.593750, 1005.236938, -13895.199219`. Leur position change avant le checkpoint 120 ; leur tâche est alors `null`. Dans chaque répétition, ils restent à cette position au checkpoint 600 et sont vivants. Cela atteste un effet de l'ordre dans le jeu, au-delà de son simple accusé de réception. Cela n'affirme pas que chaque membre atteint exactement les coordonnées de destination.

| Répétition | Déplacement horizontal de Ryers | Déplacement horizontal d'Okada | Distance horizontale finale de Ryers à la cible | Distance horizontale finale d'Okada à la cible |
| --- | ---: | ---: | ---: | ---: |
| 1 | 39,164 | 23,438 | 1,502 | 9,792 |
| 2 | 38,934 | 24,110 | 1,741 | 9,094 |
| 3 | 39,993 | 24,718 | 0,983 | 8,468 |

Les distances sont en unités des coordonnées du monde, calculées sur x/z. L'écart maximal entre positions finales, en trois dimensions, vaut 1,136 pour Ryers et 1,325 pour Okada. À l'arrivée, seuls leurs trois champs de position varient entre répétitions ; les autres champs de leurs enregistrements sont stables dans ce rapport.

La stabilité des identités reste limitée à la cohorte réellement observée et à ces rechargements dans la même instance. À l'instant initial, les trois captures contiennent chacune 106 personnages mais seulement **103 identifiants communs** ; leur union en contient 112. Les 35 escouades par capture ont 32 identifiants communs, 41 dans l'union. Trois lignes portant respectivement les noms Ando, Ishida et Hisako ont une composante `containerSerial` différente à chaque rechargement, ainsi que l'escouade associée. Leur cause n'est pas établie : on ne les fusionne pas par nom et on ne prétend pas avoir prouvé qu'il s'agit de nouvelles entités. La stabilité après redémarrage du jeu reste à vérifier.

## Variabilité et temps réel des captures

| Checkpoint | Personnages, répétitions 1 / 2 / 3 | Escouades, répétitions 1 / 2 / 3 | Champs stables | Champs variables |
| --- | --- | --- | ---: | ---: |
| initial, 0 s | 106 / 106 / 106 | 35 / 35 / 35 | 42 922 | 511 |
| en-route, 120 s | 106 / 106 / 106 | 35 / 35 / 35 | 42 239 | 1 377 |
| arrivee, 600 s | 181 / 180 / 180 | 64 / 65 / 70 | 44 815 | 2 329 |

Ces nombres comptent les chemins de valeurs du comparateur, pas des personnages indépendants ni une probabilité de réussite. Le rapport distingue valeur différente et absence d'une entité. Respectivement 450, 438 et 1 185 chemins variables comportent au moins une absence. À l'arrivée, 170 identifiants de personnages sont communs aux trois captures, sur une union de 196 ; les populations chargées ne sont donc pas interchangeables.

Les neuf captures contiennent les mêmes 114 factions et 12 882 paires directionnelles. Aucune relation ne varie entre répétitions aux checkpoints 0 et 120. À 600, la valeur de `1085-gamedata.base` vers `56098-rebirth.mod` vaut `-0.03875`, `-0.0425`, `-0.03875`. L'ensemble des factions est stable ; cela ne rend pas toutes leurs relations constantes.

| Répétition | Dépassement à 120 s | Dépassement à 600 s |
| --- | ---: | ---: |
| 1 | 0,156097 s | 0,073242 s |
| 2 | 0,094299 s | 0,244903 s |
| 3 | 0,204162 s | 0,169372 s |

`run_until` s'arrête au premier franchissement observé sur le thread principal ; il n'impose pas un pas de simulation découpé exactement au seuil. Le dépassement maximal de cette campagne est donc **0,244904 seconde du calendrier du jeu** après arrondi supérieur à six décimales. Le résidu initial d'environ `1.82e-7` seconde vient de la comparaison de l'horloge non quantifiée avec sa représentation canonique à six décimales ; il ne constitue pas une progression observée à l'instant 0. Toutes les captures sont en pause avec `clock.speed = 0`.

## Restitution et sauvegardes

Le rapport du runner indique `restoration.verified: true`, puis le relevé MCP extérieur confirme `settings_restored_exactly: true`. Les valeurs avant/après sont égales pour la pause, la vitesse sélectionnée connue, le mode caméra, le défilement latéral, le centre, la position, le quaternion, la position locale du nœud, le zoom et la cible suivie. Les valeurs de cette vérification sont : pause active, sélection 1, mode libre désactivé, défilement activé, zoom local signé `-1887.5`, cible suivie `null`.

La correction du zoom signé et de l'ordre des opérations de caméra est donc observée sur cette pose sans suivi. Le suivi d'un personnage et les autres modes de caméra ne sont pas validés par cette campagne. La sélection 1 avait été établie explicitement par `set_game_speed(1, preserve_pause=True)` ; aucun getter public ne permet de déduire la sélection antérieure inconnue. La restitution des contrôles et le rechargement de la sauvegarde du scénario ne restaurent pas une partie non sauvegardée.

Le relevé de contrôle atteste que les sauvegardes `KenshiProbe_validation`, `KenshiProbe_test` et `KenshiProbe_test_scene_20261028T022539600581Z` sont inchangées. Il n'atteste pas l'identité de tous les fichiers de l'installation.

## Bataille répétée et récupération d'un échec

Le second relevé, `runtime/oracle-phase1/live-bataille-prepared-091.json`, confirme trois répétitions réussies et neuf captures dans `runs/petite-bataille/20261028T234412.193109Z-5000999d`. Le pilote charge d'abord la sauvegarde du scénario avant de mémoriser ses contrôles ; chaque répétition la recharge ensuite. `completed`, `settings_restored_exactly` et les trois contrôles de sauvegardes protégées sont vrais. La pose restituée est sans suivi, mode stratégique, zoom signé `-10`, pause active et sélection connue 1. Les neuf captures ont aussi été relues hors jeu : schéma, empreinte et identité des octets copie/natif/Python sont conformes.

L'ordre `attack` à l'instant 0 vise les deux acteurs sauvegardés suivants, dont les identités et positions initiales sont stables dans les trois répétitions :

- Attaquant `KenshiProbeFight_1_0` : `hand:1:254:2620117248:1:390136704`.
- Cible `KenshiProbeFight_1_1` : `hand:1:255:2565673728:1:1780517632`.

La tâche immédiate de l'attaquant est `equip_weapon` dans les captures initiales, puis `unprovoked_focused_melee_attack` visant le bon identifiant à 120 et 600. Tous deux ont sept parties à santé 100 et étourdissement 0 au départ et restent `alive` aux captures finales. Les effets diffèrent :

| Répétition | Santé de l'attaquant à 600 | État observé de la cible à 600 |
| --- | --- | --- |
| 1 | Toutes les parties à 100, aucun étourdissement | Tâche `run_away`, toutes les parties à 100 |
| 2 | `31-gamedata.quack:right` à 16,303886, étourdissement 6,437221 ; `32-gamedata.quack:neither` à 37,776840, étourdissement 11,375998 | Tâche `melee_attack` visant l'attaquant, santé 100 |
| 3 | `100-gamedata.quack:neither` à 85,754456, étourdissement 1,175521 | Tâche `melee_attack` visant l'attaquant, santé 100 |

Cela prouve un ordre d'attaque appliqué et des blessures dans deux répétitions, sans prétendre que les trois affrontements produisent des dégâts identiques ni attribuer individuellement chaque coup. Le champ `subject` des autres tâches n'a pas nécessairement le sens d'une cible de combat : la première cible expose à 120 un `move_on_free_will` vers `[0,0,0]` avec `target_id:hand:0:1487:11111:38923:355957024`, puis un `run_away` avec son propre identifiant. Le type 0 est `BUILDING` dans l'énumération publique, pas une poignée nulle ; cela peut désigner un bâtiment absent des collections de ce schéma. L'objet n'a pas été résolu et le sens du `[0,0,0]` demeure ouvert. Ces observations ne prouvent pas des données corrompues et ne justifient pas d'effacer le sujet brut.

| Checkpoint | Personnages, répétitions 1 / 2 / 3 | Escouades, répétitions 1 / 2 / 3 | Champs stables | Champs variables |
| --- | --- | --- | ---: | ---: |
| initial, 0 s | 173 / 168 / 151 | 30 / 30 / 30 | 39 752 | 16 510 |
| engagement, 120 s | 173 / 168 / 151 | 30 / 30 / 30 | 39 698 | 17 739 |
| fin, 600 s | 303 / 280 / 330 | 46 / 42 / 45 | 39 787 | 34 683 |

Seulement 21 identifiants de personnages sont communs aux trois captures initiales, sur une union de 450 ; les 30 identifiants d'escouade sont communs. À la fin, 23 identifiants de personnages sont communs, sur une union de 867. Les factions et leurs relations ne varient pas entre répétitions dans ce rapport. Les dépassements à 120 sont respectivement 0,053100, 0,231628 et 0,108032 seconde du calendrier ; à 600, 0,148773, 0,135040 et 0,196838 seconde. Le maximum est inférieur à **0,231629 seconde** dans cette campagne.

Le premier essai `runs/petite-bataille/20261028T233907.644180Z-afbe49f2` est **en échec**, malgré trois exécutions et neuf captures : `restoration_error` signale un écart du centre de caméra de 131 095,3671875 unités. Le pilote avait mémorisé une caméra de `KenshiProbe_test`, puis exécuté une sauvegarde d'une autre région. Le mécanisme moteur précis de ce déplacement est inconnu. La vérification stricte n'a pas été assouplie ; la garde `restore_required` est restée active. `runtime/oracle-phase1/cross-save-recovery-091.json` atteste une récupération explicite sur `KenshiProbe_test`, avec `verified:true`, avant libération de la garde. Ce premier essai ne compte pas comme validation complète du runner et ses captures ne sont pas mélangées aux 18 captures des campagnes réussies.

## Retour final à la vue antérieure à la phase

Après ces deux campagnes, une tentative distincte de retour à la pose antérieure à la phase a été relue dans `runtime/oracle-phase1/final-restoration-091.json`. Elle n'établit **pas** une restitution exacte : une première relecture renvoie `world not ready`, puis l'audit final donne `complete:false`, `original_pose_verified:false` et un écart du centre de caméra `[-0.9453125, -0.02117919921875, -0.2734375]`. L'écart de position est `[-0.9453125, -0.021240234375, -0.2734375]`. Cette tentative finale ne remplace pas les preuves de restitution propres aux deux scénarios.

Le pointeur normalisé est observé en `[1,1]` avec défilement latéral activé, contre `[0.5,0.5]` dans la référence. Un déplacement lié au bord de l'écran est plausible, sans cause moteur certifiée. L'état final conserve le mode libre désactivé, le défilement activé et la pause, avec `clock.speed:0`. La sélection devient **inconnue** (`selected_game_speed:null`, source `unknown`, `selected_speed_verified:false`) après la transition ; ni une sélection finale 1 ni la sélection cachée antérieure de 0.8.20 ne sont affirmées.

L'audit final indique `protected_state_verified:true`, `settings_equal_prephase:true` et les trois sauvegardes protégées inchangées. L'empreinte de la DLL est `b99a1190bae405bbed60fad8380d9a9a038bb2b46745100f25739bbc63f5b4d3`, identique au build déployé ; l'instance demeure `34736:1222705718`. Ces contrôles ne compensent pas l'échec de pose ni l'absence de sélection connue. Aucun nouvel essai ni nouvelle correction n'est entrepris après la demande d'arrêt du lot. Les limites sont conservées au lieu de relâcher le contrôle ou d'annoncer une restauration exacte.

## Vérifications hors jeu

La suite Python complète, après ajout de la sauvegarde explicite de récupération, se termine avec **1 289 tests réussis en 49,60 s**, avec la commande :

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/oracle-phase1/pytest-recovery-final-20261029
```

Elle a été exécutée hors sandbox pour permettre les sockets du faux jeu. Une garde `autouse` interdit aux tests le port réel 47800. Les tests couvrent notamment schémas, canonicalisation, faux jeu, runner, délais, annulation, garde de restauration, concurrence et protection des chemins ; ils ne remplacent pas les observations de Kenshi.

Les scripts `tests/test-oracle-format-v100.cmd` et `tests/test-statistics-detail-v100.cmd` rapportent **38 assertions** de format/contrôle de vitesse et **2 272 assertions sur 198 cas** de statistiques. La comparaison indépendante de **59 états synthétiques** donne des octets C++/Python identiques. Pour les 18 captures des deux campagnes réussies, une relecture hors jeu confirme le schéma, l'identité des octets natifs/copie/canonicalisation et chaque empreinte SHA-256 du rapport. Des sérialisations identiques pour un même état ne prouvent pas des simulations identiques.

## Limites restantes

Les identités de toute la population, leur persistance après relance, l'exhaustivité des objets en mémoire et l'atomicité vis-à-vis des workers internes restent partiellement ou entièrement inconnues. Le schéma capture les personnages chargés et leur tâche immédiate, pas le monde déchargé ni la file entière des ordres. La cohérence du contrat et ses sources sont détaillées dans [la couverture de l'état](state-coverage.md).

Au terme de ce premier lot, `ville-calme` n'avait pas été exécuté. La sauvegarde a depuis été fournie et son [complément de validation](oracle-ville-calme-validation.md) consigne trois répétitions réussies. Les variations observées doivent rester dans les rapports et ne doivent pas être filtrées pour produire artificiellement un état identique.

Les deux TODO du premier lot, `ORACLE-ORDER-ENUM` et `ORACLE-CAMERA-NONCHARACTER`, restent ouverts. L'audit ultérieur ajoute `ORACLE-IDENTITY-REMAP` pour l'origine stable des poignées de PNJ dont le conteneur change. Voir les [questions ouvertes](open-questions.md) et l'[audit des identités](npc-identities-phase1.md).
