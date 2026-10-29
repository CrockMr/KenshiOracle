# Livraison phase 1 — KenshiProbe 0.9.5

La phase 1 est **livrée et validée le 29 octobre 2026** : oracle du **Kenshi original**, état commun 0.1, captures canoniques, identités sauvegardées prouvées, scénarios répétés par MCP et supervision. Elle conserve les fonctions 0.8.20 et l'arborescence existante. Le comparateur et l'adaptateur MeitouClient appartiennent à la phase 2. Aucune nouvelle campagne de performance n'a été réalisée.

Les preuves ci-dessous sont locales, ignorées par Git ; elles ne distribuent aucune sauvegarde ni donnée du jeu. La [grille d'acceptation](phase1-acceptance.md) rapproche les huit critères du prompt des fichiers et validations.

## Version et installation

- DLL finale **0.9.5**, build **Visual C++ 2010 x64/v100** réussi : `plugin/build/Release/KenshiProbe.dll`, **523 264 octets**, SHA-256 `75739c8e64e17f3a78f482132c9be659aac7d55db7b3151b907b51944af5b580`.
- PDB : **11 447 296 octets**, SHA-256 `51fa54bc8c0e96daa80b7dc3d6bb831d126a419d89f050899bbf0286af4aadfe`.
- Environnement réel : Kenshi **1.0.65 Steam**, RE_Kenshi **0.3.5**, KenshiLib **0.5.0**. Déploiement vérifié : [deployment-095.json](../runtime/oracle-phase1/deployment-095.json).
- Le schéma reste **0.1**, sans pointeurs, PID, tokens, empreintes de source ni types C++. La provenance des identités reste une métadonnée de protocole.

La correction 0.9.5 porte sur la calibration/restitution caméra. Les algorithmes d'état, de canonicalisation et de résolution d'identités des captures finales 0.9.3 restent inchangés. Les preuves de ces deux DLL sont distinguées ci-dessous.

## Vérifications hors jeu

Commande finale depuis la racine, avec les dépendances de `requirements-dev.txt` :

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=runtime/oracle-phase1/pytest-delivery-095-final-20261029 -p no:cacheprovider
```

**1 602 tests réussis, 1 sauté, 96,51 secondes**. [Log intégral](../runtime/oracle-phase1/pytest-delivery-095-final.txt). Le seul saut concerne la création d'un vrai lien symbolique, refusée sans privilège Windows/Developer Mode ; le refus des attributs reparse simulés est testé. Les tests isolent les sockets et refusent le port réel 47800. Sous le bac à sable Windows, les sockets et le sous-processus stdio nécessitent l'exécution autorisée hors bac à sable ; le résultat n'est pas celui d'un test sans réseau local.

La suite couvre schémas, parseur/protocole défensif, MCP stdio, validation de chaque photo, faux jeu, scénarios, délais, erreurs et interruptions, verrou de récupération, watchdog, archives défaillantes et requêtes de redémarrage. Le faux jeu produit des octets identiques pour un même état. L'intégration d'origines renouvelle les HAND bruts à chaque chargement et conserve les mêmes photos canoniques sur trois répétitions.

Tests natifs v100 : **74 vérifications caméra**, **107 origines** sur 0.9.5 ; les contrôles précédents inchangés comprennent **52 identifiants**, **38 format**, parseur JSON, propriété des commandes et statistiques. **59 états synthétiques C++/Python** ont des octets canoniques identiques. Les compilateurs modernes ne remplacent pas v100.

Les nouveaux tests de caméra couvrent des pivots de suivi de hauteurs 0, 9,8 et 17,125, un acteur déplacé sur trois axes après rechargement, une interpolation avant stabilisation, les tokens périmés, les dérives de réglages, le suivi et l'absence de suivi, le mode libre et la reprise après vérification en pause. Ces simulations ne remplacent pas les essais Kenshi ci-dessous.

## Trois exemples réels, chacun répété trois fois

La DLL finale **0.9.3**, SHA-256 `ebce02cd618675e88d1cadf7a239b964b3a4347825ecae5e63c7da87c2d52f91`, a exécuté les trois exemples via **MCP stdio**, avec rechargement avant chaque répétition : **9 répétitions, 27 photos**. [Lot complet](../runtime/oracle-phase1/delivery-live-batch-093.json). Les trois cas sont terminés, leur restitution est vérifiée ; les quatre sauvegardes protégées et les octets de `settings.cfg` sont inchangés.

| Exemple et rapport | Champs stables / variables au premier checkpoint | Champs stables / variables au dernier checkpoint | Personnages au dernier checkpoint, répétitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| [Trajet](../runs/trajet-escouade/20261029T010924.945400Z-d9022f41/report.md) | 43 050 / 170 | 45 105 / 2 006 | 190 / 180 / 180 |
| [Petite bataille](../runs/petite-bataille/20261029T011252.350028Z-e79d6134/report.md) | 39 771 / 16 373 | 39 776 / 32 435 | 253 / 323 / 284 |
| [Ville calme](../runs/ville-calme/20261029T011719.115118Z-408fb1ae/report.md) | 42 042 / 3 165 | 42 253 / 5 636 | 130 / 132 / 140 |

Un champ variable peut changer de valeur ou être absent d'une répétition. Les rapports conservent ces observations et les dépassements temporels effectifs : maxima **0,320435**, **0,320893** et **0,310593 seconde calendaire** respectivement. Ce sont des comparaisons entre répétitions de Kenshi, pas entre moteurs. Populations, positions, santé et tâches peuvent diverger malgré un rechargement identique.

L'[audit indépendant des 27 fichiers](../runtime/oracle-phase1/delivery-evidence-audit-093.json) valide schéma, comptes, hashes, provenance et identité des octets **natifs = copie MCP = canonicalisation Python**. Un second audit de livraison les a revérifiés. Le premier checkpoint du trajet contient **106 personnages, 35 escouades, 114 factions, 12 882 relations**.

Ando, Hisako et Ishida ont un état individuel dans la sauvegarde ; leurs HAND courants changent de conteneur au chargement. La résolution SDK complète permet de publier leur HAND sauvegardé dans **les neuf photos du trajet**. Ni nom, ni adresse, ni simple paire I/S ne sert de clé. En ville, **80** identités de personnages sauvegardés sont communes initialement et **92** à 600 secondes. Les membres variables des trois escouades sauvegardées sans fichier de personnages étayent une génération à l'activation pour cette cohorte. Une origine non résolue ne prouve pas à elle seule une génération : son HAND courant est conservé. [Audit détaillé](npc-identities-phase1.md).

## Validation réelle de la restitution 0.9.5

Le [test de récupération 0.9.5](../runtime/oracle-phase1/recovery-camera-095.json) est **réussi**. Il vérifie d'abord un décalage volontaire `[2,1,-3]`, observé comme décalage supplémentaire `[2,1,-3]`, puis recharge et restitue exactement les contrôles du journal original. Les contrôles enregistrés restent inchangés et `restore_required` passe à faux uniquement après vérification.

La référence retrouvée inclut centre `[-50978.796875,1541.7958984375,2932.4765625]`, position `[-51489.6640625,2067.15087890625,2005.222900390625]`, zoom signé `-1181.855224609375`, quaternion, suivi canonique d'Imai, mode stratégique, défilement actif, pause et sélection préparée 1.

Cette réparation répond à un échec réel après relance : la hauteur de l'acteur avait changé de **0,936035** et une pose stable restait incorrecte. Le candidat 0.9.4 avait ensuite traité à tort le décalage supplémentaire comme la distance complète centre−acteur ; sa restitution a échoué. [Preuve de cet échec](../runtime/oracle-phase1/recovery-camera-094.json). Ces échecs restent conservés ; la référence et les tolérances n'ont pas été relâchées.

Le protocole 0.9.5 prépare et observe une caméra stable sous verrou, puis applique `offset actuel + centre demandé − centre observé`. Aucun biais de hauteur constant ni déplacement d'acteur. Après libération, une seconde fenêtre compare à la référence fixe : **trois frames distinctes sur au moins 0,5 seconde**, délai **10 secondes** ; tolérances centre/position/zoom **0,05**, quaternion **0,0001**, vitesse sélectionnée **0,000001**. [Contrat détaillé](protocol.md).

## Rejeu ville sur la DLL livrée 0.9.5

La [série finale MCP](../runtime/oracle-phase1/delivery-ville-calme-095.json) est **terminée** : **trois répétitions, neuf captures**, chacune valide contre le schéma et identique octet pour octet au fichier natif et à sa canonicalisation Python. Un audit indépendant a revérifié ces neuf fichiers, leurs hashes et la provenance constante `ville-calme`, fingerprint `sha256:1a7624e7e712526e03b37a3ee8d78bcd5499a0780b8eac5a1e7b0ddaf5c678c5`. Les **32 outils MCP** sont présents. [Rapport stable/variable](../runs/ville-calme/20261029T021907.110703Z-839230f0/report.md).

| Checkpoint | Champs stables | Champs variables | Personnages, répétitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| Initial | 42 029 | 3 748 | 111 / 106 / 118 |
| Deux minutes | 41 792 | 4 294 | 111 / 106 / 118 |
| Dix minutes | 42 243 | 6 124 | 138 / 137 / 139 |

Le dépassement temporel maximal est **0,121766 seconde calendaire**. La restitution en deux phases est vérifiée, avec **8 observations de base et 8 après commit**. Les quatre sauvegardes et les réglages sont inchangés. Les séries nommées dans ce bilan représentent **36 captures et 12 répétitions réussies**, dont neuf captures/trois répétitions directement sur la DLL livrée.

## Watchdog et état final

Le [test réel du watchdog 0.9.5](../runtime/oracle-phase1/watchdog-runtime-095.json) est **réussi**. Il vérifie chemin, PID, date de création et ligne de commande du processus possédé avant sa sortie contrôlée : **45812 → 16548**. La supervision archive le journal dans `crashes/20261029T022312.138729Z`, motif `process_exit`, aucune erreur d'archive ; SHA-256 du journal archivé `076366d35c5a3edbc28869a7e0120332da93b06cc63ec83e04248d598705f9fc`. Le nouveau jeu démarre avec une autre instance ; la récupération recharge `ville-calme`, prépare les origines et restitue la référence caméra/temps vérifiée.

L'[audit final en lecture seule](../runtime/oracle-phase1/final-audit-095.json) confirme : DLL construite et installée au hash annoncé, écoute **127.0.0.1:47800**, watchdog actif, cinq hooks historiques et trois systèmes conservés, monde prêt **en pause**, sélection préparée **1**, suivi d'Imai et pose conformes, verrou caméra libéré, aucun token en attente et `restore_required:false`. Les **quatre sauvegardes protégées** et le SHA-256 de `settings.cfg` correspondent au manifeste de départ. Aucun exécutable, donnée ou sauvegarde du jeu ne figure dans les fichiers publiables par Git.

Les échecs antérieurs, dont [le test watchdog 0.9.3](../runtime/oracle-phase1/watchdog-runtime-093.json) ayant réussi archive/relance puis échoué en restitution, restent archivés. Leur statut n'est pas réécrit. Le présent lot s'arrête après ce contrôle ; aucune phase 2 ni campagne supplémentaire n'est lancée.

## Non testé ou non démontré universellement

- Adaptateur MeitouClient et comparateur entre moteurs : hors phase 1.
- Exhaustivité de tous les objets en mémoire, état des régions déchargées et atomicité face à tous les workers internes.
- Déterminisme du moteur, stabilité de toute identité à travers toutes sauvegardes, mods et redémarrages. Les références sans liaison prouvée restent courantes ; le remappage réel d'une escouade avec alias différent n'est pas démontré dans ces scènes.
- Tous les offsets/modes de caméra dans toutes régions ; suivi d'objets autres que personnages, entrées manuelles concurrentes et immobilité après la fenêtre de vérification.
- Chargements déclenchés manuellement dans l'interface pendant un scénario ; restauration d'une partie non sauvegardée ou d'une sauvegarde différente de celle explicitement choisie.
- Fabrication d'un vrai minidump de crash moteur : la sortie contrôlée prouve l'archive du journal et la relance ; les dumps facultatifs et pannes de copie sont couverts par les tests synthétiques. Le seuil de heartbeat figé est testé hors jeu et possède des preuves historiques séparées ; aucun nouveau gel réel n'est provoqué pour ce lot.
- Installation sur une autre machine, une autre version du jeu/SDK et configuration Debug. Un test de lien symbolique réel reste sauté pour privilège Windows.

## TODO du code de production

Deux marqueurs subsistent, recensés indépendamment dans `plugin/`, `mcp-server/` et `launcher/` :

1. **`ORACLE-ORDER-ENUM`**, `plugin/OracleState.h` : ajouter un nom symbolique vérifié si un SDK futur expose une tâche absente de la table auditée. En attendant, `order:null` ; aucun type inventé.
2. **`ORACLE-CAMERA-NONCHARACTER`**, même fichier : le suivi restaurable concerne les personnages chargés. Un autre type de cible exige un recensement public vérifié et reste refusé explicitement.

L'ancien TODO de canonicalisation des identités est implémenté. Le [tableau champ par champ](state-coverage.md) distingue **Vérifié**, **Observé** et **Inconnu** ; les [questions ouvertes](open-questions.md) conservent les limites et les découvertes. L'[installation](first-run.md) permet de reproduire le premier dump et les scénarios avec ses propres sauvegardes locales.
