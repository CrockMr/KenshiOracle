# Ville calme : validation complémentaire du 29 octobre 2026

> Rapport historique. Le [bilan de livraison 0.9.5](oracle-phase1-delivery.md) et la [grille d’acceptation](phase1-acceptance.md) décrivent les sources, tests et validations finales ; les résultats ci-dessous gardent leur version et leur portée initiales.

La sauvegarde utilisateur `ville-calme` a été rejouée **trois fois**, avec neuf captures conformes au schéma 0.1 et une restitution vérifiée des contrôles, y compris le suivi du personnage Imai. La DLL reste **0.9.1** ; la correction concerne le serveur Python. La suite complète termine avec **1 310 tests réussis en 65,16 s**. Les agents de ce lot utilisent GPT-6.1 Sol, effort ultra.

Les trois exemples ont désormais chacun une série de trois répétitions réussies : trajet, bataille et ville, soit 27 captures pour ces séries. Les anciens essais ne sont pas rétroactivement validés avec le nouveau contrôle de stabilité. Aucune campagne de performance n'a été lancée.

## Preuves locales

Les fichiers volumineux et les données du jeu restent hors Git. Les preuves de ce lot sont :

- `runtime/oracle-phase1/city-preflight-091.json` : état initial et empreintes des quatre sauvegardes protégées, dont les 54 fichiers de `ville-calme`.
- `runtime/oracle-phase1/live-ville-calme-stable-091.json` : validation via MCP stdio, neuf empreintes, identité de processus inchangée, réglages et sauvegardes contrôlés.
- `runs/ville-calme/20261029T001325.437085Z-06ebaeea/report.json` et `report.md` : trois exécutions, neuf captures et comparaison des champs.
- `runtime/oracle-phase1/city-final-audit-091.json` : contrôles revérifiés après l'essai, pause active, aucune restitution en attente, réglages exacts et quatre sauvegardes inchangées.

Les neuf captures ont été validées contre le schéma et leurs octets comparés aux sources natives et à la canonicalisation Python. Le jeu est Kenshi 1.0.65 Steam, instance `34736:1222705718`, plugin 0.9.1. Chaque répétition recharge la sauvegarde ; aucune action n'est envoyée aux personnages. Les checkpoints sont à 0, 120 et 600 secondes **calendaires du jeu**, et non des secondes réelles.

## Résultats et variabilité

| Checkpoint | Personnages, répétitions 1 / 2 / 3 | Escouades, répétitions 1 / 2 / 3 | Champs stables | Champs variables |
| --- | --- | --- | ---: | ---: |
| Initial | 101 / 103 / 110 | 22 / 22 / 22 | 42 029 | 2 945 |
| 120 s | 101 / 103 / 110 | 22 / 22 / 22 | 41 802 | 3 436 |
| 600 s | 123 / 125 / 131 | 26 / 25 / 26 | 42 241 | 4 707 |

Chaque capture contient 114 factions et 12 882 paires directionnelles. Les nombres de champs variables incluent les présences et absences : ce ne sont pas des probabilités ni des nombres d'entités indépendantes.

Imai conserve son identité `hand:1:1:751953152:1:3279785216`, son escouade et le même état entre les répétitions à chaque checkpoint. Il reste vivant avec une tâche courante nulle. Ses coordonnées x/z restent `-50978.796875, 2932.476563` ; y passe de `1531.995850` au checkpoint initial à `1533.468262` aux deux suivants. Cela ne prouve pas une immobilité complète en trois dimensions ni un déterminisme du monde.

| Répétition | Dépassement à 120 s | Dépassement à 600 s |
| --- | ---: | ---: |
| 1 | 0,145797 s | 0,227737 s |
| 2 | 0,296859 s | 0,073242 s |
| 3 | 0,166397 s | 0,368499 s |

Le plugin met en pause au premier franchissement observé. Ces dépassements restent dans les rapports ; ils ne sont pas masqués en remplaçant l'instant réel par la consigne.

## Correction de la vérification caméra

La première tentative, `20261029T000108.688978Z-ed2aa999`, a produit ses trois répétitions et neuf captures, mais le runner l'a correctement laissée **en échec** : le centre caméra différait de `0.17248535156295475`, au-delà du seuil de 0,05. Cette tentative et son rapport sont conservés.

Le code ne vérifiait auparavant qu'une seule lecture après restitution. Désormais `wait_stable_controls` observe des frames distinctes pendant au moins 0,5 seconde, avec au moins trois frames et une échéance de dix secondes. Il encadre les lectures par des contrôles d'identité et de disponibilité, exige une horloge immobile et conserve les observations. La référence est capturée en pause avant l'armement du journal, puis reste fixe. Une pose stable mais différente de cette référence échoue ; aucune mutation incertaine n'est réessayée.

Les seuils restent : 0,05 pour centre, position et zoom, 0,0001 pour quaternion, 0,000001 pour sélection de vitesse. Une sélection inconnue n'est pas assimilée à zéro. La vérification s'effectue après la libération native du verrou caméra ; elle ne neutralise pas les entrées de l'utilisateur et ne garantit pas l'immobilité future.

Le diagnostic avait relevé un pointeur SDK au bord et des changements d'orientation. Des interactions Windows sur la bannière de pause ont ensuite placé l'entrée à l'intérieur de la fenêtre ; les mouvements ont cessé lors des lectures suivantes. Ce constat ne prouve pas à lui seul la cause de l'écart initial. Aucun ordre de déplacement ou d'attaque n'a été envoyé par ces interactions.

La récupération explicite de la première tentative a réussi sans modifier sa référence, preuve `runtime/oracle-phase1/city-recovery-stable-091.json`. La série suivante utilise le nouveau contrôle dès le départ. Sa fenêtre initiale valide six frames sur 0,625 seconde ; sa restitution cinq frames sur environ 0,531 seconde. Les écarts de centre, position et quaternion sont **nuls dans la lecture finale du rapport**. Le suivi d'Imai, le zoom signé `-1181.855224609375`, le mode stratégique, le défilement activé, la pause et la sélection préparée 1 sont vérifiés. Cela valide ce cas de suivi, sans couvrir tous les modes et offsets possibles.

L'audit final confirme les mêmes contrôles sur une nouvelle fenêtre après validation des fichiers. Il laisse la sauvegarde `ville-calme` rechargée en pause ; il ne prétend pas reconstituer une vue transitoire ou une partie non sauvegardée antérieure à la préparation.

## PNJ générés ou identité déplacée

L'[audit des identités](npc-identities-phase1.md) distingue deux cohortes. Dans cette ville, les 80 identités communes initiales correspondent exactement à des personnages sauvegardés. Les membres variables initiaux appartiennent à trois escouades enregistrées comme jamais activées, sans états individuels sauvegardés : leur génération à l'activation est fortement étayée. À 600 secondes, les 92 personnages individuellement sauvegardés sont présents dans chaque répétition.

Pour les anciens Ando, Hisako et Ishida, des états individuels concordants existent déjà dans la sauvegarde. Leurs composantes de conteneur changent dans les captures. Ils ne constituent donc pas une preuve de création complète au chargement. La résolution moteur des alias et une identité d'origine canonique restent à implémenter et vérifier ; aucun rapprochement par nom ou par le seul couple index/serial n'est utilisé dans l'état exporté.

## Vérifications et limites

La suite complète a été exécutée avec les sockets des faux serveurs, sous protection interdisant le port réel du jeu :

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/oracle-phase1/pytest-city-full-20261029
```

Résultat : **1 310 réussites, 65,16 s**. Le sous-ensemble MCP, runner et exemples avait auparavant donné 64 réussites. Aucun nouveau build natif n'était nécessaire pour cette correction Python ; seul un commentaire TODO a été ajouté à l'adaptateur d'identités.

Restent non validés ici : les autres modes/offsets de suivi, la persistance générale des identités après redémarrage, l'exhaustivité de toute la mémoire moteur, l'atomicité des workers et de nouveaux crashs/gels réels. Les tests du watchdog hors jeu et son historique sont conservés. L'adaptateur MeitouClient et le comparateur entre moteurs restent hors phase 1.

Les trois TODO du code natif sont `ORACLE-IDENTITY-REMAP` (origine stable et alias), `ORACLE-ORDER-ENUM` (futurs types de tâches inconnus du SDK) et `ORACLE-CAMERA-NONCHARACTER` (suivi d'un objet autre qu'un personnage chargé). Voir les [questions ouvertes](open-questions.md).
