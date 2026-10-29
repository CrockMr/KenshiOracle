# Restauration sans reprise intermédiaire — 0.8.7

La restauration de KenshiProbe_test règle maintenant x1 en conservant la pause dans la même commande native. Le contrôle réel retrouve exactement **404,3333339691162 heures de jeu**, comme après le chargement initial, après deux rechargements de validation puis un troisième de nettoyage. La copie reste en pause, les sauvegardes et les préférences sont intactes. Aucun gain de performances ni déterminisme de tout l’état PNJ n’est établi.

## Changement

L’ancien helper enchaînait trois requêtes distinctes : retirer la pause, régler x1, puis remettre la pause. La boucle du jeu pouvait avancer entre ces requêtes ; l’horloge finale de la campagne de piles 0.8.5 était ainsi légèrement différente de celle de l’autoload.

`set_game_speed(speed, preserve_pause=True)` utilise les méthodes déclarées dans GameWorld.h : `isPaused()`, `setGameSpeed(float,bool)` et `userPause(bool)`. Les deux mutations se terminent sur le thread principal dans un même traitement de commande, avant le retour à originalLoop. Le paramètre booléen est vérifié avant mutation ; aucun accès direct à un champ privé du moteur ni nouvelle API n’est introduit.

Le défaut reste `False` et conserve le protocole existant. La réponse ajoute `paused_before` et `preserve_pause` ; `ping.set_game_speed_preserve_pause_available` annonce la capacité. `restore_test` exige cette capacité et la pause après chargement, règle x1 en la conservant, puis compare **game_total_hours** avant/après. Il ne possède plus de requête de reprise entre ces étapes.

Le mode de conservation exige **0 < speed <= 5**. La combinaison vitesse nulle/conservation de pause est rejetée avant mutation par MCP et par le plugin. Utiliser la commande pause pour arrêter la simulation. Le nombre d’outils reste 17 ; les trois sondes système et leur sélection charsUpdateUT restent inchangées.

## Validation réelle

Source : `runtime/scenarios/restore-pause-20261028T105200176995Z.json`, completed=true, SHA-256 **da3d1dc9eae9bfa55e7e68a7ade9c57f5c62be715721effdc6790c975f89253d**. Transport MCP stdio ; les requêtes mal formées sont aussi essayées directement sur le protocole natif, afin de vérifier le garde du plugin.

Jeu PID **28920**, création Unix **1793184744.2008762**, exécutable vérifié `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe --norestart`. Ces identités ne valent que pour cette session.

| Cas | Résultat observé |
|---|---|
| Chargement initial | Première disponibilité observée en pause ; heure 404,3333339691162, inchangée aux trois lectures suivantes. |
| Réglages x2, x5 et x1 en pause | Réponse paused_before=true, paused=true, multiplicateur effectif 0 ; les neuf lectures suivantes gardent exactement la même heure de jeu. |
| Reprise explicite après sélection x2 en pause | Multiplicateur effectif 2, paused=false ; le choix de vitesse est conservé pour la reprise. |
| Réglages x2, x5 et x1 en cours de simulation | paused_before=false et paused=false, multiplicateur effectif égal à la demande. |
| Vitesse positive sans le nouveau paramètre | Reprend la simulation, comme auparavant. |
| Booléen natif mal formé | Rejet avant mutation ; pause et heure de jeu conservées. |
| Vitesse nulle avec conservation | Rejet MCP et natif ; rejet natif également vérifié pendant la simulation, qui reste à x1. |
| Deux rechargements puis nettoyage | Pause et heure initiale exactement retrouvées ; caméra normale puis contrôle temporaire libéré. |

Le contrôle indépendant `runtime/restore-087-final.json` confirme : pause, multiplicateur 0, heure initiale, Edge=true, propriété de caméra false, 17 outils, sept rôles SDK, trois sondes, watchdog frais sans erreur et WPR inactif. Les **702/702/738 fichiers** source/copie/snapshot correspondent aux manifests protégés ; settings.cfg est identique octet pour octet à l’état précédant le déploiement. Aucun contrôleur de test ne reste actif. Les deux helpers du watchdog restent bornés à l’échéance existante.

Compilation **v100 x64** réussie ; **367 tests passent en 5,24 s**. Les tests de contrat vérifient notamment que le défaut garde l’ancienne requête et que les paramètres invalides ne sont pas transmis. La validation dans le moteur ci-dessus vérifie le comportement des appels SDK ; le fixture Python ne prétend pas les émuler.

## Tentatives conservées et limites

Le premier contrôleur 0.8.6 avait ajouté à tort une stabilité de game_time_stamp. La tentative `restore-pause-20261028T104258395419Z.json` reste completed=false, avec ses sources conservées sous runtime. Ce compteur brut continue en pause, comme déjà documenté dans [les mesures d’horloge](simulation-clock-measurements.md). Le contrôle indépendant `runtime/pause-stamp-086.json` confirme une progression de 2,4452879 s pour 2,4452880 s QPC, sur 339 frames, avec **zéro progression d’heure de jeu**. Le garde a été corrigé pour utiliser l’horloge de simulation ; aucun écart de celle-ci n’a été toléré. La caméra a été libérée après l’échec du nettoyage initial.

La validation intermédiaire 0.8.6 `restore-pause-20261028T104713355682Z.json` a ensuite réussi. Un contrôle des bornes encore non observées a révélé dans `runtime/speed-boundaries-086.json` que zéro avec conservation d’un état non pausé gardait la vitesse précédente x5. Cette observation est conservée ; 0.8.7 remplace ce comportement ambigu par un refus explicite dans les deux interfaces.

Une commande composée ne constitue pas une transaction atomique de tous les workers. Les observations prouvent la pause aux bornes et l’absence de progression de l’heure simulée dans ces scénarios ; elles ne prouvent pas l’absence de toute activité asynchrone entre les deux appels SDK, ni une identité mémoire complète des PNJ. La caméra peut de nouveau défiler après restitution de sa préférence de bord. Aucun paramètre système de sécurité, privilège administrateur ou nouvelle capture ETW n’a été nécessaire.

Déploiement final : `crashes/20261028T105221075324Z-deployment-087`, preuve `runtime/deploy-087.json`. Les identités du jeu et des helpers 0.8.6 ont été revérifiées avant arrêt. Symboles propres conservés sous `runtime/symbols/0.8.7` : DLL SHA-256 **eb6760d01e382efaddb0b3274349f6a30d506ee80a2fbc79e10a7f8c778abdba**, PDB **ff179bd209359ddc04d4d271e3b245e305328897e4c3e1a8fb2e883e6238e2ea**. Aucun binaire du jeu ou code décompilé ajouté au dépôt.
