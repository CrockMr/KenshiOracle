# Coût mural des lectures MCP en pause — 28 octobre 2026

**96 lectures via le vrai MCP terminées dans deux scènes en pause.** Pour la scène de40 PNJ, `get_scene_state` sans détails de threads prend en moyenne **3,036792 ms dans le bloc de service natif**, avec **4,205825 ms d’attente dans la file** et **16,029792 ms pour l’appel MCP complet**. Ces horloges décrivent des périmètres différents. Aucun CPU exclusif, gain moteur ou cause du p99 du combat précédent n’est établi.

## Instrumentation et protocole

Plugin **0.8.11/v100 x64**, toujours17 outils et trois sondes système charsUpdate/findPath/Havok. `KENSHI_PROBE_COMMAND_TIMING=1` active les métadonnées optionnelles dans les callbacks de service existants ; désactivées par défaut. Les autres choix restent FUNCTION_TARGET=havokCharacterUpdate,FUNCTION_THREAD_CPU=0,AI_THREAD_CPU=0,NAV_THREAD_CPU=1. Aucun nouvel appel Game/SDK, quatrième hook ni changement d’algorithme moteur.

Le bloc mesuré comprend execute, l’affectation du résultat et le journal DebugLog. Il exclut ses propres métadonnées, le signal d’événement, la sérialisation JSON réseau, l’envoi et les clients Python/MCP. L’attente commence sous le verrou juste avant insertion en file ; parsing/réception/acquisition initiale du verrou sont exclus. La durée MCP est mesurée autour de l’appel public. Ne pas convertir la différence entre ces durées en CPU ou en attribution exclusive du transport. Le coût de la télémétrie elle-même n’est pas isolé.

`tests/live_command_service.py` recharge KenshiProbe_test avec protection de pause et verrou Edge. Première phase : copie sans bataille suivie. Seconde : préparation Mongrel, dix secondes à x1 et disponibilité stable, pause, focus puis création unique de20 paires/40 PNJ. Modèles16863-gamedata.base/Bloodraiders et1227-gamedata.base/Mercenary Guild ; hostilité mutuelle vérifiée avant création, sans modifier de relation. La seconde phase reste **en pause**, aucun combat actif n’y est mesuré.

Chaque phase contient12 lectures de chacun des quatre groupes ci-dessous, ordre tournant et pause demandée de0,1 s entre appels. La première lecture est conservée, pas de warmup supprimé. Toutes les scènes sont en pause, horloge de jeu immobile, caméra stable et cohorte complètement retrouvée. Les phases diffèrent aussi par ville, caméra et état du monde : leur différence n’est pas un coût marginal causal par PNJ. La préparation est non ensemencée ; aucune comparaison causale avec l’ancien combat x5.

## Résultats retenus

Durées en millisecondes ; chaque ligne comprend12 requêtes. « Service » = bloc natif mural inclusif. « File » = attente avant ce bloc. « MCP » = appel complet côté contrôleur.

| Scène | Lecture | Service moyen | Service min..max | File moyenne | MCP moyen |
|---|---|---:|---:|---:|---:|
| Copie sans bataille | ping |0,226133|0,184300..0,303400|3,134567|7,944033|
| Copie sans bataille | scène |0,092708|0,068300..0,125000|11,185083|15,757383|
| Copie sans bataille | scène + rôles |0,255083|0,206700..0,347700|4,371133|9,360667|
| Copie sans bataille | statistiques n60 |2,169892|1,951600..2,717100|4,149000|14,040442|
| Mongrel40 en pause | ping |0,223400|0,186300..0,285100|5,307075|10,157258|
| Mongrel40 en pause | scène |3,036792|2,862200..3,330000|4,205825|16,029792|
| Mongrel40 en pause | scène + rôles |3,169233|2,996300..3,388800|3,131433|15,143408|
| Mongrel40 en pause | statistiques n60 |2,202092|1,951900..2,561700|2,485217|12,603625|

La première lecture de scène de la copie a **69,785200 ms d’attente**, **0,125000 ms de service** et **75,563500 ms d’appel MCP**. Cette forte attente ne démontre pas une longue exécution du getter. Le streaming, l’ordonnancement, le callback précédent et les autres causes possibles ne sont pas séparés ici.

Tailles des résultats JSON compacts réencodés : scène sans bataille1287..1302 octets, scène40 PNJ21594..21598, scène40 avec rôles22927..22929 ; statistiques n60 environ30254..30766 octets. La scène en pause n’a pas la même taille ni le même état clinique que les31 Kio du combat actif précédent. Aucune réduction de taille n’a été nécessaire pendant ces96 lectures ; l’audit final a aussi admis n3600 en49293 octets.

Tous les services rejoignent **T13900/création FILETIME134376742378013332**. Le propriétaire et la création sont vérifiés indépendamment par Windows avant/après chacune des phases, dans le jeu **PID34260/création Unix1793200637.801332**. Aucun TID d’un ancien processus n’est réutilisé comme identité stable. `menu_service=true` signifie service par le callback Renderer restreint, **pas affichage du menu** :2 puis3 ping sur12 empruntent ce chemin alors que le monde est prêt. Les autres lectures passent toutes par GameWorld.

## Échec conservé, preuves et restauration

Le premier essai `runtime/scenarios/command-service-20261028T151852385261Z.json`, SHA **6ca18fe130af78a5cbca164011b4ed0faedf88763b3d2900b535c4ecac60b86e**, reste completed=false.48 lectures de copie puis rejet du premier ping de seconde phase par l’hypothèse incorrecte « service Renderer implique menu ». La réponse déclenchant ce rejet n’avait pas encore été ajoutée au brut ; le message correspond à ce garde du contrôleur, pas à une preuve détaillée de son contenu. Le contrôleur conserve désormais le résultat avant validation, accepte et compte les ping Renderer ; test de régression ajouté. Aucune modification native ni nouvelle DLL n’est nécessaire à cette correction. Restauration/sauvegardes/settings de l’essai rejeté conformes.

Essai admis : **`runtime/scenarios/command-service-20261028T152117109875Z.json`**, SHA **5f0bee2a0fc7d8d4971edbe0d8ad99ea6cb25b519d95a9a455cf8ee63fd1e6a2**. Rapport **runtime/command-service-0811-analysis.json**. Rejeu :

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_command_service.py runtime\scenarios\command-service-20261028T152117109875Z.json --expected-sha256 5f0bee2a0fc7d8d4971edbe0d8ad99ea6cb25b519d95a9a455cf8ee63fd1e6a2 --output runtime\nouveau-rapport-service.json
```

L’analyse vérifie plan et ordre exacts, clocks monotones/finies/réconciliées, frames propres aux phases, identité de thread aux deux bornes, tailles JSON compactes recalculées, cohorte en pause, résumé dérivé et restauration. Les octets compacts sont réencodés depuis le résultat, pas une mesure exacte du fil TCP/MCP. Les erreurs et heartbeat réseau direct n’ont pas ces métadonnées ; absence ne signifie jamais zéro.

Audit indépendant **runtime/command-service-0811-final.json** : même PID, pause/multiplicateur0, **404,3333339691162 h**, caméra normale/contrôle temporaire relâché/Edge=true, aucune bataille suivie ; **702/702 fichiers** des sauvegardes protégée/copie et **738 fichiers** du snapshot antérieur identiques. Settings byte-identique au préalable de déploiement, gardes false ; watchdog frais/zéro erreur, WPR inactif, aucun contrôleur de scénario restant. Helpers10192 et29024 à vérifier fraîchement avant arrêt.

Archive **crashes/20261028T151709989767Z-deployment-0811**, preuve runtime/deploy-0811.json ; ancien binaire propre0.8.10 conservé. DLL0.8.11 **281088 octets/SHA26452b71822a70e07c0c7cd4cade56c242884bebcef5d0d30e571c3a37d2a730**, PDB propre sous runtime/symbols/0.8.11. Première compilation C1902 sous bac à sable puis compilation locale autorisée réussie ; aucun privilège administrateur Windows ajouté. **609 tests Python passent en21,17 s**, tests natifs v100 réussis (mode désactivé, identité exacte, erreurs inchangées, clocks invalides et non finies rejetées), smoke vrai MCP et analyse stricte réussis.

## Prochaine amélioration à évaluer

Le coût du getter riche mérite de limiter les lectures détaillées pendant les acquisitions et de conserver les statistiques après les fenêtres. Avant de modifier le moteur, mesurer hors jeu construction/copies de l’arbre JSON et sérialisation avec des fixtures propres. Une optimisation de copie éventuellement démontrée devra préserver le contrat et être revalidée ; aucune n’est encore implémentée. Mesurer aussi les commandes pendant une phase active ciblée si la question exige ce régime. Ces mesures en pause ne suffisent pas à expliquer le p9966,3855 ms du combat précédent ni à calculer un coût CPU par acteur.

Échéance autonome inchangée :28 octobre22 h15 UTC/23 h15 Paris. Aucune intervention utilisateur/administrateur attendue.
