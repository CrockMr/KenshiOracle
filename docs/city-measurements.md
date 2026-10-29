# Première campagne près de Heng — 28 octobre 2026

Plugin 0.6.0, Kenshi 1.0.65 Steam, v100 x64. Deux paires ont été exécutées dans le même processus de test : ordre 1 puis 5, puis 5 puis 1. Les moyennes de frame se chevauchent ; aucun gain d'optimisation ni goulot CPU exclusif n'est démontré.

## Scène et protocole

Chaque condition recharge KenshiProbe_test puis déplace les deux personnages joueur groupés à la position x/z de Heng issue de TownList, via le contrôleur de mouvement public. Dix secondes de streaming à x1, attente d'un monde prêt, puis cinq secondes à la vitesse cible. Trois fenêtres distinctes de 300 frames, identifiants vérifiés. Résolution 1280×720, VSync activée dans les réglages de départ. Les intervalles de cette boucle ne constituent pas une mesure du rythme de présentation GPU.

La caméra reste près de la ville, décalée d'environ 2240 unités du centre ; les positions effectives sont conservées dans chaque JSON. Le nombre de personnages à moins de 2000 unités du centre varie de 157 à 163 avant/après les mesures, contre deux joueurs déplacés. La liste complète de mise à jour varie de 406 à 458 aux relevés des conditions. Il ne s'agit ni d'une bataille ni d'une population identique à chaque instant.

Raw local : runtime/measurements/city-paired-20261027T235740Z et city-paired-20261027T235907Z. Les sauvegardes, mesures brutes et fichiers du jeu restent hors Git. Les manifests confirment la restauration de la vue initiale, mode libre false et pause true ; quick.save source inchangé au SHA-256 de référence. PID 9772 stable pendant les deux paires.

## Ordre 1 puis 5

| Vitesse | Frames | Moyenne frame ms | p99 frame ms | Appels findPath | findPath moyen par frame ms | Plus long appel ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 17551–17850 | 8,007 | 12,042 | 134 | 0,3063 | 4,632 |
| 1 | 17859–18158 | 8,377 | 19,611 | 128 | 0,2206 | 5,516 |
| 1 | 18172–18471 | 7,385 | 10,603 | 121 | 0,1616 | 1,574 |
| 5 | 19770–20069 | 7,628 | 9,841 | 61 | 1,1259 | 162,153 |
| 5 | 20083–20382 | 7,719 | 19,386 | 91 | 1,1641 | 166,927 |
| 5 | 20387–20686 | 7,586 | 9,480 | 67 | 0,0352 | 1,102 |

## Ordre 5 puis 1

| Vitesse | Frames | Moyenne frame ms | p99 frame ms | Appels findPath | findPath moyen par frame ms | Plus long appel ms |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 25529–25828 | 7,591 | 10,327 | 109 | 0,1147 | 2,391 |
| 5 | 25839–26138 | 7,428 | 9,713 | 97 | 0,0901 | 2,287 |
| 5 | 26146–26445 | 8,215 | 14,340 | 134 | 0,0710 | 1,319 |
| 1 | 27732–28031 | 7,460 | 14,834 | 142 | 0,3290 | 2,673 |
| 1 | 28040–28339 | 7,838 | 21,517 | 33 | 0,0413 | 4,072 |
| 1 | 28350–28649 | 8,094 | 17,384 | 49 | 0,0714 | 3,160 |

## Ce que ces résultats justifient

Les pointes de 162..167 ms ne réapparaissent pas dans l'ordre inverse. Les appels et leurs coûts diffèrent, même pour une vitesse identique. Les caches ne sont pas purgés, le streaming et la simulation continuent, le même échauffement réel représente des durées simulées différentes à la vitesse cible, et la charge des autres applications n'est pas quantifiée. Ne pas conclure que x5 accélère ou ralentit le pathfinding, ni comparer les FPS à la scène Gut dont la caméra diffère.

Les hooks mesurent des durées murales inclusives, avec attribution à la frame de fin de l'appel. Dans les deux premières fenêtres x5, le plus long appel dépasse largement le maximum d'intervalle de frame de la fenêtre (14,810 et 26,178 ms). Cela justifie une classification par thread et l'examen des appels traversant les frontières de fenêtre ; cela ne prouve pas encore un coût CPU de 167 ms bloquant le thread principal.

Prochaine instrumentation utile : distinguer le thread GameWorld des autres threads dans le hook findPath existant, conserver quelques appels lents avec leurs paramètres publics et résultat, et relever la consommation CPU du processus sur les mêmes intervalles. Garder le plafond de trois hooks. Préparer ensuite une bataille conservable et reproductible sur la copie avant tout remplacement de système.

Cette instrumentation a depuis été réalisée sous 0.6.1 puis étendue sous 0.6.2 : voir [le diagnostic par thread](navigation-diagnosis.md). Les appels lents capturés s'exécutent sur un thread distinct de GameWorld ; quatre nouveaux échantillons ont aussi un coût CPU du même ordre que leur temps mural. Une garde de caméra exclut désormais les conditions où la vue dérive.
