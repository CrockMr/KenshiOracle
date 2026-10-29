# Objet BirdManager vérifié — plugin 0.8.7 inchangé

Le thread 18796 de cette campagne porte bien un objet **BirdManager** : son contexte de pile, le préfixe SDK de l’objet, l’identifiant du thread, la table virtuelle et le nom RTTI concordent dans le même minidump. Cela complète le [rapprochement statique précédent](worker-stack-static-085.md), qui ne disposait pas du vptr dynamique.

Le relevé CPU antérieur à la capture attribue **2,828125 s CPU sur 8,110 s**, soit environ **0,349 processeur logique**, à ce thread entier. Ce résultat ne mesure pas le coût exclusif d’une fonction BirdManager, ne sépare pas calcul et synchronisation et ne démontre aucun gain de performances.

## Source et conditions

Contrôleur : `runtime/worker-objects/20261028T111210121084Z/controller.json`, completed=true, admin=false, SHA-256 **546d1bb32add420fe5b3dbc4efcfb5e725834c64df27b4838c70103adfd7d33c**. Jeu PID **28920**, création native FILETIME **134376583442008762** ; EXE SHA-256 **504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e**. Les adresses et identités ci-dessous concernent uniquement cette durée de vie.

La copie KenshiProbe_test a été rechargée avec le verrou de caméra, préparée à Heng, puis laissée avancer à x1 après échauffement. Le CPU est mesuré avant toute capture ou analyse DbgEng. Les quatre threads avec les plus grands deltas CPU sont ensuite sélectionnés par TID **et création FILETIME**. Le jeu est mis en pause avant les deux minidumps et leur déroulement. Aucun pytest ou compilation pendant la fenêtre CPU.

Le plugin installé reste 0.8.7, DLL SHA **eb6760d01e382efaddb0b3274349f6a30d506ee80a2fbc79e10a7f8c778abdba** : toujours 17 outils MCP et trois sondes système. Aucun nouveau hook ni appel d’une API BirdManager reconstruite. Les adresses de métadonnées RTTI sont des observations du binaire identifié ; elles ne constituent pas une nouvelle interface du SDK.

## Chaîne de preuve

1. Le nouveau lecteur `tests/dump_contexts.cpp`, compilé v100 x64, utilise [GetContextStackTrace de DbgEng](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol4-getcontextstacktrace) uniquement sur les fichiers enregistrés. Il conserve les contextes par frame et omet les registres volatils, dont la restauration n’est pas garantie par cette API.
2. La preuve statique `runtime/re-worker-087-static/threadproc-this-proof.json` vérifie que **RBP contient this** au frame exact ThreadWannabe::threadProc dont le PC est RVA 0x25fd3a ou 0x25fe08. La copie RCX→RBP domine ces chemins ; RBP n’y est pas réaffecté avant l’épilogue. Il ne s’agit pas du RBP sauvegardé sur la pile, qui appartient à l’appelant. Les offsets du préfixe viennent de ThreadClass.h : vptr +0, handle +8, TID +0x10, running +0x14. Aucun layout de la classe dérivée n’est inventé.
3. Le dump de découverte contient les contextes des quatre threads et la table SDK vérifiée. Le frame déroulé du thread **18796 / création 134376583564582384** donne un this candidat à **0xc229fb70**. Une lecture externe limitée à 24 octets vérifie le TID du préfixe, la stabilité de son identité et les durées de vie OS. Le handle stocké dans l’objet reste une simple valeur numérique, jamais une preuve indépendante de durée de vie.
4. Un second dump contient les contextes, la table SDK, les deux préfixes candidats de 24 octets et trois plages RTTI/table virtuelle connues. Dans **ce fichier de confirmation**, le même frame donne le même RBP, le préfixe porte TID 18796 et son vptr vaut **0x7ff6e999ad48**, soit EXEBase+0x16aad48. Le préambule de table, ses quatre slots, le Complete Object Locator et le nom `.?AVBirdManager@@` correspondent aux métadonnées du fichier source, avec relocalisation vérifiée. Les 7622 pointeurs SDK correspondent aussi à cette base EXE dans chacun des deux dumps.
5. L’autre objet ThreadWannabe du relevé porte TID **38140 / création 134376583564583798**, à 0x5cfe1e0, avec un autre vptr. Le rôle SDK world_ai_non_render lui est joint séparément. Un frame dans ThreadWannabe n’est donc pas assimilé par défaut à BirdManager.

Le dump de découverte fait **155884 octets**, celui de confirmation **157118 octets**. Leurs temps de capture helper sont 0,299612 et 0,237697 s ; ce ne sont pas des mesures de durée de suspension du jeu. Le second ajoute seulement six plages explicites, soit **61122 octets** : table SDK 60976, table virtuelle 40, locator 24, descripteur de type 34 et deux préfixes de 24. Aucun dump complet ni scan du tas.

Le lecteur final a aussi redéroulé le minidump historique actif 0.8.5 : les **24/7/9 frames PC/SP** restent identiques au lecteur d’origine. Preuve : `runtime/contexts-087-reader-validation.json`, lecteur SHA **16682a8cbc0fc4574ed4f329b75b47db9ad13550d008901c160a2601aa83db86**. Aucun processus vivant n’a été attaché par DbgEng ; aucun provider Ghidra ouvert.

Les deux nouveaux fichiers ont également été redéroulés hors ligne avec le lecteur de même empreinte qu’à l’acquisition : les PC/SP/RBP des **22/9/8/8 frames** de découverte et **26/9/8/8 frames** de confirmation sont identiques aux observations conservées. Preuve séparée : `runtime/worker-objects/20261028T111210121084Z/offline-replay-validation.json`.

## CPU et limites d’attribution

| Thread / création FILETIME | CPU entier | Processeurs logiques moyens sur 8,110 s |
|---|---:|---:|
| 19312 /134376583442008777 |6,187500 s|0,762947|
| Rôle SDK non rendu 38140 /134376583564583798 |2,921875 s|0,360281|
| Objet BirdManager 18796 /134376583564582384 |2,828125 s|0,348721|
| 34312 /134376583466414538 |0,890625 s|0,109818|

Le processus totalise **18,9375 s CPU sur 8,125 s**, soit 2,330769 processeurs logiques. Les bornes des compteurs de processus et de threads sont séquentielles : les durées diffèrent et le résidu signé vaut **−0,25 s**, conservé sans clamp. Aucune identité n’est omise aux deux bornes. Les mesures de scène englobent 8,117921 s et +0,0743103 h simulée, avec une population de 418 à 450 personnages ; le streaming et la population évoluent donc dans cette fenêtre.

Les deux captures sont **postérieures à la fenêtre CPU et prises en pause**. Elles attestent l’objet lié à ce thread à cet instant, sans attribuer chacun de ses quanta CPU précédents au code des oiseaux. Une fraction du thread peut provenir d’attentes, de synchronisation ou d’autres appels. Aucun pourcentage CPU n’est déduit du nombre de piles ; aucun contraste causal avec une autre version ou ville. La charge des autres applications n’est pas fixée ni quantifiée.

## Reproduction hors jeu et restitution

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_worker_object.py runtime\worker-objects\20261028T111210121084Z\controller.json --expected-sha256 546d1bb32add420fe5b3dbc4efcfb5e725834c64df27b4838c70103adfd7d33c --output runtime\worker-object-087-analysis-recheck.json
```

L’analyseur vérifie les fichiers et jointures hors jeu ; les contextes DbgEng conservés sont des observations, pas des registres qu’il redéroule lui-même. Les binaires source avec leurs empreintes exactes sont nécessaires à la correspondance statique. Les minidumps et sorties brutes restent dans runtime, ignoré Git ; aucun binaire du jeu ni désassemblage dans ce rapport.

Choisir un nouveau chemin de sortie à chaque recalcul : l’analyseur refuse l’écrasement. La revalidation finale est `runtime/worker-object-087-analysis-v2.json`, verified=true. Elle contrôle aussi les octets de contexte initial du dump, le PID et sa création à la seconde dans MiscInfo, la chronologie des scènes x1/pause et la progression recalculée. Le FILETIME précis du processus reste une preuve externe issue des handles et bindings enregistrés ; il n’est pas présenté comme un champ du dump. Les domaines QPC et monotonic ne sont pas supposés identiques. Les tests ciblés comprennent des corruptions d’octets de table SDK, TID, vftable, locator et nom RTTI, qui sont rejetées même après mise à jour de leur SHA déclarée.

**442 tests passent en 21,13 s** dans la suite finale. Les nouveaux cas vérifient aussi les plages de métadonnées, les identités réutilisées ou contradictoires, les scènes incohérentes et le rejet d’un écart de création de processus de +0,5 s. Le lecteur distinct est compilé v100 x64 ; aucune recompilation ou installation du plugin n’a été nécessaire pour cette campagne.

Après la capture, l’heure de simulation en pause est restée exactement **404,4983215332031 h** pendant la vérification des objets. La copie a ensuite été rechargée à **404,3333339691162 h**, identique à sa référence initiale, puis la caméra libérée. `runtime/worker-object-087-final.json` confirme pause, caméra normale, Edge=true/propriété false, 17 outils/sept rôles SDK/trois sondes, watchdog frais sans erreur et WPR inactif. Les **702/702/738 fichiers** source/copie/snapshot sont conformes, settings.cfg est identique au préalable du déploiement et aucun contrôleur de campagne ne reste actif.
