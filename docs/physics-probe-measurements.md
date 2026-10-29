# Sonde physique 0.7.6 — remplacement d'une sonde existante

La sonde **PhysicsActual::_NV_backThreadUpdate(float,bool)** est liée en v100 x64, installée et observée en jeu. Elle remplace charsUpdateUT : **trois sondes de systèmes restent actives**, avec charsUpdate et NavMesh::findPath. Le corps original et ses arguments sont inchangés. Il s'agit d'une mesure supplémentaire, sans optimisation du moteur.

À Heng, la fonction est observée sur le **thread 34744**, distinct du thread GameWorld/Renderer **8612**. Son identité de création correspond exactement au relevé CPU Windows du même processus. Le thread entier consomme environ **0,043 processeur logique à x1** dans cette capture ; cette cible est moins coûteuse ici que les principaux workers encore inconnus. Cela ne mesure pas toute la physique ni les tâches qu'elle pourrait déléguer.

## Déploiement et preuves

- Déclaration publique : `references/KenshiLib_Examples_deps/KenshiLib/Include/kenshi/PhysicsActual.h`, méthode non virtuelle ; mécanisme GetRealAddress/AddHook vérifié dans core/Functions.h. Aucun RVA n'est recopié dans le plugin.
- Compilation et liaison **Visual C++ 2010 x64/v100** réussies. Tests natifs PhysicsTelemetry en v100 réussis, dont cumul, disponibilité CPU partielle, débordement et TID réutilisé.
- Archive de déploiement : `crashes/20261028T045306717729Z-deployment-076`, ancien DLL 0.7.5, journal, configuration et préférences. Le motif est `deployment_0.7.6`, pas un crash du moteur.
- Identités relues avant arrêt : ancien jeu 19892, watchdogs 21824/10472, chemins/commandes/créations vérifiés. Seuls ces processus du projet ont été arrêtés. Nouveau jeu **19920**, watchdog wrapper **36144**/enfant **19296** au contrôle final ; bootstrap et chargement de la copie automatiques.
- `runtime/deploy-076.json` conserve les empreintes de DLL et identités ; `runtime/physics-076-smoke.json` confirme 0.7.6, trois sondes, charsUpdateUT absent et les premiers 300 appels physiques en pause.
- Brut de ville : `runtime/scenarios/pause-cpu-20261028T045548Z.json`, SHA-256 **2dad2c394101224206352c7195e3f15d39d51f04ee7292060ea2471fb3801617** ; synthèse `runtime/physics-076-analysis.json`.
- État final complet : `runtime/physics-076-final.json`.

Le redémarrage réinitialise l'association des anciens snapshots en mémoire. Les **738 fichiers de KenshiProbe_test_scene_20261028T022539600581Z sont préservés**, mais les anciens scripts exigeant battle_tracking_restored ne doivent pas supposer cette propriété encore disponible. Aucun ancien snapshot n'a été écrasé ou recréé sous le même nom.

## Mesure native

La recette pause/x1/pause de live_pause_cpu est reprise pour une **nouvelle hypothèse de profilage**, avec le nouveau hook : même vue et ville dans ce parcours, trois secondes de stabilisation avant chaque intervalle de vingt secondes demandé. Aucun pytest pendant les intervalles. Les fenêtres finales ci-dessous contiennent **600 frames et 600 appels physiques** chacune, sans débordement ni lecture CPU indisponible.

| Phase | Durée physique inclusive moyenne par frame | Maximum d'un appel | CPU utilisateur des appels retenus | CPU noyau des appels retenus | CPU du thread entier sur l'intervalle OS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pause avant | 0,088694 ms | 0,299900 ms | 0 ms | 0 ms | 0,009223 processeur logique |
| x1 | 0,560210 ms | 1,079000 ms | 62,5 ms | 62,5 ms | 0,042877 processeur logique |
| Pause après | 0,112456 ms | 1,115900 ms | 31,25 ms | 0 ms | 0,013027 processeur logique |

Les compteurs par appel GetThreadTimes sont quantifiés : **zéro ne prouve pas une absence de calcul**. Les sommes CPU du hook portent seulement sur les appels dont les lectures réussissent. Le CPU du thread entier porte sur l'intervalle OS d'environ vingt secondes ; les 600 frames sont une fenêtre finale plus courte, légèrement postérieure à sa borne heartbeat. Ces colonnes ne partagent pas exactement les mêmes bornes et ne doivent pas être divisées pour annoncer une couverture exclusive de la fonction.

Les identités physiques sont fournies sous forme TID et FILETIME de création décimale exacte (`134376368000459413` dans ce processus). Les trois jointures au thread CPU réussissent. Le temps inclusif est comptabilisé dans le bucket de fin de l'appel ; une exécution peut commencer avant la fenêtre. Ni le temps passé dans d'autres fonctions du thread ni celui de workers supplémentaires n'est attribué à cette seule méthode.

CPU global de ce parcours : **1,735513 / 2,153826 / 1,779278 processeur logique moyen** ; populations **396 stable / 419–442 / 442 stable**. Les principaux workers non attribués sont maintenant 33728 et 38832, avec créations propres à ce nouveau processus. Ils ne sont pas identifiés aux anciens TID 37324/39984 par leur seul comportement. Les nouveaux chiffres ne démontrent aucun gain par rapport à 0.7.5 : instrumentation, processus, population, streaming et caches diffèrent. Le panneau RE_Kenshi n'a pas été vérifié visuellement après ce démarrage ; aucune comparaison de performances entre versions n'est qualifiée par ce relevé.

## Contrat et validation

Les champs historiques charsUpdateUT_mean_ms et per_frame.charsUpdateUT_ms valent **null**. Ping expose les états de sondes et system_hook_count=3. La physique ajoute totaux, maximum, partition CPU disponible/indisponible et huit identités détaillées maximum ; `unlisted` conserve les totaux non détaillés. Les partitions sont validées avec physique + navigation. Voir protocol.md pour les unités, l'option KENSHI_PROBE_PHYSICS_THREAD_CPU et la sémantique des appels traversant plusieurs frames.

**207 tests Python passent en 4,00 s**, en plus des tests natifs v100. Ils vérifient notamment cohérence des partitions, compteurs non finis ou négatifs, dépassement d'identités, télémétrie retirée à null et jointure physique/CPU refusée sur une création différente. Les champs optionnels restent lisibles dans les anciens rapports dépourvus de sonde physique.

Le contrôle final vérifie les **702 fichiers de KenshiProbe_validation, 702 de KenshiProbe_test et 738 de l'ancien snapshot**, tous conformes aux témoins. settings.cfg est identique octet pour octet à son état avant déploiement. Copie initiale rechargée en pause, vue normale de référence, Edge scrolling=true, aucun combat suivi actif ou contrôle temporaire. Watchdog frais, zéro erreur de publication ; config et activation toujours bornées au **28 octobre 22 h 15 UTC**, sans prolongation.

Le pilote de piles CPU administrateur reste en attente. Une piste publique à examiner ensuite est ThreadClass.h : threadID, threadHandle et name sont déclarés, et GameWorld expose AINonRenderThread(). Une observation de ces rôles pourrait fournir des identités supplémentaires sans quatrième hook, après vérification des types, de la liaison et des conditions de lecture. Aucune attribution nouvelle de ces deux workers n'est présumée.
