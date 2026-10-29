# Sauvegardes de scénario et reprise en pause

Pour réduire les différences de génération entre essais, `save_scene_snapshot` utilise la méthode publique **SaveManager::save(const std::string&, bool)**, déclarée dans SaveManager.h, liée par v100 x64 et observée nativement. Le nom doit commencer par `KenshiProbe_test_scene_`, suivi de 1..40 caractères ASCII parmi lettres, chiffres, tiret et souligné. Le plugin exige une bataille de test en pause, refuse tout fichier ou dossier cible existant et limite à huit les snapshots gérés pendant sa session. Aucun écrasement n'est proposé.

Le nom et le préfixe des PNJ sont mémorisés sans pointeur de jeu. `load_save` restaure ce suivi uniquement pour un snapshot créé par la **même session du plugin**. Après redémarrage du jeu, les dossiers restent disponibles, mais cette association n'est pas recréée automatiquement. Le chemin de sauvegarde doit être ASCII dans cette première implémentation ; le plugin vérifie le répertoire et l'absence de cible avec l'API Win32 avant de demander l'écriture au moteur.

La réponse `accepted` signifie « écriture demandée », pas « fichiers complets ». Le test attend `ping.save_signal=0`, quick.save et deux manifestes SHA-256 consécutifs identiques avant de recharger. Il vérifie aussi le refus d'un second enregistrement au même nom et l'absence de changement des fichiers lors des chargements.

## Première observation — 0.7.4

`runtime/scenarios/snapshot-20261028T021855834633Z.json` décrit un nouveau snapshot de deux PNJ hostiles à Mongrel, 739 fichiers. Deux rechargements par les vrais outils MCP stdio retrouvent exactement les mêmes valeurs médicales et positions ; les fichiers du snapshot restent identiques et l'écrasement est refusé. Toutefois, les premiers ping prêts indiquent **paused=false**, et les heures de jeu diffèrent : 404,369667 puis 404,368881. Le client remet alors la partie en pause, mais ce délai empêche de présenter la disponibilité initiale comme une reprise figée.

## Pause avant publication — 0.7.5

Les callbacks GameWorld/Renderer existants appliquent désormais `userPause(true)` dès qu'un snapshot géré est prêt et que SaveManager n'a plus de signal. Le battement garde loading=true jusqu'à cette pause. Aucun nouveau hook n'est ajouté. Le chargement ordinaire de KenshiProbe_test conserve son parcours existant ; ce comportement concerne les snapshots reconnus dans la session.

`snapshot-20261028T022539600581Z.json`, 738 fichiers, confirme **paused=true au premier ping prêt dans les deux chargements** et une horloge identique, 404,3666667938232 heures. Santé et sang sont identiques. Le garde de comparaison signale néanmoins une différence verticale maximale de **1,897339 unité**, au-delà de son seuil d'une unité ; il garde `matches=false`. Les X/Z sont identiques. Ce résultat n'est pas reclassé artificiellement comme une comparaison complètement contrôlée.

Une observation ciblée supplémentaire recharge le même snapshot sans en créer un autre : `snapshot-paused-settling-075.json`. Deux chargements sont suivis à environ 0, 1, 3 et 5 secondes en pause. Horloge, santé et positions restent fixes à chaque série ; les deux séries correspondent exactement, sans modification des fichiers. Cette observation ne démontre pas qu'attendre cinq secondes résout la variation verticale : l'écart précédent n'a simplement pas été reproduit dans ces deux séries. Toute future comparaison doit vérifier son état initial et conserver les rejets, plutôt que relâcher le seuil.

`set_camera_free(enabled, lock_edge=true)` peut protéger le défilement au bord après le chargement d'un snapshot géré. Une valeur enabled déjà appliquée ne rappelle pas le changement de mode, afin de préserver la pose. lock_edge=false ne demande pas ce verrouillage ; la propriété temporaire existante reste libérée au prochain chargement. Avant une écriture de snapshot, le plugin restitue le réglage Edge scrolling initial, car le moteur peut lui-même enregistrer ses préférences.

Le test sauvegarde aussi les octets de settings.cfg et les restaure à la fin, puis recharge la copie initiale et contrôle caméra, mode et pause. Les 702 fichiers de KenshiProbe_validation et les 702 de KenshiProbe_test restent conformes au manifeste témoin. Les gardes `runtime/scene-snapshot-state.json` et `runtime/snapshot-settle-state.json` portent restore_required=false. Un essai interrompu avec restore_required=true doit d'abord récupérer son backup enregistré, avant toute nouvelle exécution ; le test refuse de l'écraser.

Le script `tests/live_scene_snapshot.py` s'exécute par MCP stdio réel. Les tests hors jeu vérifient les noms protégés et le comparateur visible : santé, position, acteur absent, lecture incomplète et état d'inconscience. Cette étape fixe une partie importante de l'état visible ; elle ne prouve pas la déterminisation de tous les états IA, équipements et renforts.
