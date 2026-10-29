# Reprise de la copie en pause — 0.8.4

La copie KenshiProbe_test est maintenant mise en pause par le plugin avant que world_ready devienne vrai. Un démarrage après déploiement et un redémarrage MCP réel ont confirmé le premier état prêt observé en pause, sans commande de pause envoyée par le contrôleur.

## Correction

L’ancienne pause avant disponibilité concernait uniquement les snapshots possédés en mémoire. Le précontrôle0.8.3 avait donc trouvé la copie chargée automatiquement sans pause ; cette observation est conservée dans runtime/identity-083-startup.json.

load_save programme désormais la pause pour le nom exact KenshiProbe_test ou un snapshot possédé. Les callbacks existants GameWorld/Renderer attendent monde initialisé, absence de reset/chargement et signal du gestionnaire de sauvegarde nul, puis appellent GameWorld::userPause(true). world_ready reste faux tant que cette pause est attendue. Les noms des autres sauvegardes n’activent pas cette nouvelle règle ; aucun essai ne charge la sauvegarde protégée de validation.

Les déclarations userPause(bool), isPaused(), isLoadingFromASaveGame(), initialized/gameResetting et SaveManager::load/signal ont été relues dans les en-têtes du SDK. Aucun nouvel offset, hook ou algorithme du moteur. Toujours v100 x64, trois sondes de systèmes et17 outils MCP. Le cache TLS0.8.3 et le mode AI_THREAD_CPU=0 sont conservés.

ping.test_save_pause_on_ready_available annonce la capacité ; ping.load_pause_pending décrit l’attente. load_save(...).pause_on_ready vaut désormais aussi true pour KenshiProbe_test. Le watchdog peut publier loading=true encore brièvement après le premier ping prêt, car son fichier est mis à jour séparément ; le contrôle final vérifie son retour à false.

## Observations réelles

Le script tests/live_autoload_pause.py utilise MCP stdio. Son chemin normal n’envoie aucune commande de pause, ne change pas la vitesse, ne prépare pas de scène et n’écrit aucune sauvegarde. Le premier observateur a été lancé avant le watchdog. Le second vérifie fraîchement chemin, commande et création du jeu avant une seule demande restart_game.

| Essai | PID | Premier ping prêt observé | Scènes suivantes |
|---|---:|---|---|
| Démarrage après déploiement |33948|frame544, pause=true, vitesse0, attente=false|frames545..970, 3,041826 s|
| Redémarrage demandé |35336|frame418, pause=true, vitesse0, attente=false|frames419..825, 3,050325 s|

Les quatre scènes de chaque essai ont exactement404,3333339691162 heures de jeu. Pendant l’attente,65 puis50 observations portent load_pause_pending=true et world_ready=false. Le relevé compte74 puis59 pings au total. Aucun fallback_pause ni erreur n’est présent. Les observations ne couvrent pas chaque frame du moteur et ne prouvent pas une déterminisation de tout l’état des personnages.

Preuves :

- runtime/scenarios/autoload-pause-20261028T090504090106Z.json, completed=true, SHA-256 **54c958e1f7ef8a4527b1dc42395f8063ab2f0157b3ce6747b4645aa3ee175687**.
- runtime/scenarios/autoload-pause-20261028T090725294145Z.json, completed=true, SHA-256 **90954d4f15b508f6461abafba2a62911b414cc5d9d773b83a0f5da115952e208**.
- runtime/autoload-084-validation.json recalcule les invariants des deux bruts. Le second possède un acquittement et l’archive **crashes/20261028T090726.287883Z**, motif requested avec journal conservé. PID/création réellement changés de33948/1793178313.279526 à35336/1793178451.3026247.

## État laissé et limites

**291 pytest passent en4,53 s**, compilation et liaison v100 x64 réussies. La nouvelle politique native est vérifiée par les deux essais réels ; les tests factices ne constituent pas cette preuve.

Archive du déploiement : crashes/20261028T090445969777Z-deployment-084, ancienne DLL0.8.3/journal/config/settings. WPR inactif et identités jeu33512/watchdogs28140/33880 vérifiés avant arrêt des seuls processus du projet. Les symboles propres0.8.4 sont préservés dans runtime/symbols/0.8.4, sans binaire de jeu ajouté à Git.

runtime/autoload-084-final.json vérifie jeu35336 en pause/mode normal, contrôle de caméra relâché et Edge=true, watchdog frais sans erreur/autoload réussi, sept rôles SDK et17 outils. Les **702/702/738 fichiers** source/copie/ancien snapshot et les octets settings.cfg correspondent au préalable de ce déploiement. Les deux gardes de préférences sont false, WPR est inactif et aucun contrôleur d’essai ne reste actif. Helpers27108/38500 au dernier relevé, identités à relire avant toute action. Borne config/activation1793225700 inchangée.

La caméra peut encore répondre au défilement de bord lorsque sa préférence est restituée ; cette validation porte sur la pause et l’horloge, pas sur une immobilité permanente de la caméra. current_save conserve un nom interne collant et ne prouve toujours pas le dossier chargé. La propriété des anciens snapshots n’est pas reconstruite après redémarrage.

La capture administrateur Heng reste différée sans intervention demandée maintenant. Le diagnostic de performances suivant doit viser le worker restant, par exemple GameWorld::charsUpdateUT avec son vrai prototype en remplacement de la sonde IA ; aucun gain d’optimisation du moteur n’est établi ici.
