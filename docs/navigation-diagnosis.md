# Navigation par thread — première observation 0.6.1

Le diagnostic situe les appels findPath lents observés sur un thread distinct de GameWorld. Leur temps mural ne mesure donc pas un blocage direct de même durée exécuté sur le thread principal. Un effet indirect sur la simulation reste possible et n'est pas encore quantifié. Aucune optimisation du moteur n'a été effectuée.

## Nouvelle observation en bataille — 0.7.3

`runtime/scenarios/battle-20261028T015352Z.json` mesure dix PNJ créés près de Mongrel, avec renforts et commandes via MCP stdio. La fenêtre finale de 600 frames contient 300 appels, tous sur un autre thread : 299 true et un false. Parmi onze appels ≥10 ms retenus sans troncature, dix true durent 10,210..11,632 ms et produisent 92..98 éléments ; le false dure **130,579 ms**, consomme **125 ms CPU** et laisse **six éléments de sortie**, contre zéro à l'entrée. Les compteurs CPU de ces appels courts sont quantifiés à zéro ou 15,625 ms ; zéro observé n'est pas assimilé à une absence de calcul.

Ce false avec sortie partielle empêche d'assimiler le booléen à « aucun chemin retourné ». La signature publique ne donne toujours pas de motif détaillé. Les appels restent globaux, sans attribution aux personnages qui se battent. Les variations de population, cohorte et état initial interdisent une comparaison causale avec les anciennes mesures de Heng. L'auditeur de navigation doit être étendu explicitement à ce format de capture avant d'intégrer ses événements aux campagnes précédentes ; ne pas forcer leur provenance dans le schéma des paires de ville. Voir battle-observations.md pour la recette, les contrôles et les limites.

## Preuve native

Campagne locale runtime/measurements/city-paired-20261028T000701Z, ordre 5 puis 1, cinq fenêtres de 600 frames par condition, même processus 13036. Scène près de Heng, reconstruite avant chaque condition selon benchmark-protocol.md. Source et copie quick.save au SHA-256 de référence après les essais ; vue initiale, mode normal et pause restaurés.

| Condition | Frames mesurées | Appels findPath | Sur GameWorld | Sur d'autres threads | Appels ≥10 ms retenus | Plage des appels lents ms |
| --- | --- | --- | --- | --- | --- | --- |
| x5 | 3000 | 977 | 0 | 977 | 13 | 154,488–165,824 |
| x1 | 3000 | 1006 | 0 | 1006 | 1 | 160,981 |

Les partitions de compteurs/durées/maxima ont passé les contrôles du collecteur. Aucun appel de ces fenêtres n'est resté non classifié, et aucun enregistrement lent n'a été perdu par saturation du tampon de 32. Tous les appels lents retenus ont thread_id=28440, contre game_thread_id_at_start=17356, hierarchical=true, radius≈0,4, water=10 et result=false. Ce retour ne précise pas la cause ni la permanence de l'échec ; ne pas l'assimiler automatiquement à une destination définitivement inaccessible.

À x5, ces treize appels représentent 1,33 % des appels observés et 84,44 % de la somme de leurs durées murales inclusives (2080,095 ms sur 2463,352 ms). Cela en fait une cible de diagnostic, pas encore une estimation de CPU économisable.

Exemple : appel de 161,349 ms commencé à la frame 2473 et comptabilisé à la frame 2492, pendant une fenêtre dont le maximum d'intervalle GameWorld est 14,058 ms. Il s'étend sur plusieurs frames d'un autre thread. Certains goal_key réapparaissent, mais les clés ne décrivent pas à elles seules une requête identique : positions, état du maillage et conditions de streaming restent à examiner avant toute proposition de cache.

## CPU du processus

| Condition | Intervalle englobant s | CPU utilisateur s | CPU système s | Processeurs logiques équivalents | Part de capacité sur 16 processeurs logiques |
| --- | --- | --- | --- | --- | --- |
| x5 | 23,516 | 32,094 | 19,250 | 2,183 | 13,646 % |
| x1 | 22,469 | 27,984 | 21,984 | 2,224 | 13,899 % |

Ces compteurs OS couvrent tout le processus, tous ses threads et modules, sur l'intervalle englobant la collecte ; ils ne sont pas attribuables à la navigation ni à une fenêtre précise. Une faible part de la capacité totale ne suffit pas à exclure un goulot sur un thread. Les durées CPU de chaque appel findPath n'ont pas été mesurées : 160 ms de temps mural peuvent inclure calcul, attente ou désordonnancement. La charge des applications extérieures reste non quantifiée.

## Qualité de mesure et suite justifiée

La version 0.6.1 transfère les compteurs du bucket précédent et publie la nouvelle frame sous un même verrou. Cela supprime l'ambiguïté d'étiquetage d'une fin d'appel concurrente à cette frontière. Le hook conserve les mêmes arguments, le même appel original et le même résultat ; le diagnostic ajoute néanmoins un verrou de lecture au départ et une écriture bornée pour les appels lents. Ne pas interpréter une différence entre versions comme une amélioration du moteur.

La prochaine observation utile est le CPU consommé par le thread appelant pendant les appels lents, par exemple via les compteurs Win32 publics, avec leur résolution et le coût de sonde documentés. Conserver aussi les positions publiques de départ/but permettrait de distinguer les requêtes réellement répétées des seules clés partagées. Examiner ensuite les causes de result=false et l'impact sur la simulation avant de modifier les algorithmes, les délais ou les caches. Le plafond reste de trois hooks de systèmes ; aucune raison d'en ajouter un quatrième.

## Extension 0.6.2 : CPU des appels

La sonde optionnelle GetThreadTimes a été compilée en v100 et activée pour cette campagne. Les quatre composantes des vecteurs Havok sont copiées avant l'appel depuis le membre public hkVector4f::m_quad ; aucun argument du moteur n'est modifié. Les vecteurs observés sont près de coordonnées locales 200,150,-30, alors que la ville a des coordonnées monde bien différentes : **ne pas les étiqueter comme positions monde**. NavMesh.h expose aussi worldShift/shiftWorld ; la transformation effective n'a pas été observée. La quatrième composante de départ varie de 914 à 1737 dans ces exemples, et n'est pas traitée comme coordonnée spatiale.

La première paire 0.6.2, city-paired-20261028T001447Z, a révélé une dérive de caméra de 1512,481 unités dans x1. Cette condition est exclue d'une comparaison à vue fixe ; quality.json conserve ce classement sans changer les réponses brutes. Les trois appels réussis de 10..16 ms dans son contexte de transition ont validé les champs CPU/vecteurs, mais ne décrivent pas les échecs longs visés. La cause de la dérive n'est pas démontrée. La fermeture d'un panneau RE_Kenshi et un nouveau chargement ont permis de retrouver la vue initiale. Le collecteur vérifie désormais le mode et les positions de caméra après chaque fenêtre, avec une tolérance de cinq unités ; les restaurations successives peuvent être comparées à une référence.

La reprise avec cette garde, city-paired-20261028T002159Z, a terminé ses deux fichiers de mesure x1 puis x5 : 5×600 frames par condition, 247 appels x1 et 803 appels x5. Les caméras ont passé les contrôles par fenêtre. Quatre appels lents x5, sur un thread distinct de GameWorld, ont renvoyé false :

| Temps mural ms | CPU utilisateur ms | CPU noyau ms | Total CPU ms |
| --- | --- | --- | --- |
| 167,619 | 171,875 | 0 | 171,875 |
| 163,888 | 125 | 15,625 | 140,625 |
| 164,592 | 125 | 31,250 | 156,250 |
| 161,599 | 156,250 | 15,625 | 171,875 |

Sur ces quatre observations, le CPU est du même ordre que le temps mural : l'hypothèse d'une simple attente ne décrit pas leur coût principal. Les compteurs sont quantifiés ; un échantillon CPU peut légèrement dépasser le temps mural et n'est pas artificiellement borné. Le bracket CPU inclut un peu de travail de sonde autour de l'appel. La moyenne de 200 lectures au démarrage était de 0,230 µs par lecture dans ce processus, ce qui n'est pas une garantie de coût sur l'autre thread. API et unités sont documentées dans [GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes).

Les buts et départs ne sont pas tous identiques. Deux appels partagent exactement le même départ capturé mais visent des buts différents. Ce constat ne justifie pas de réutiliser un échec entre requêtes ou entre états de maillage. La prochaine piste fondée sur les mesures est d'étudier les recherches coûteuses à retour false et leur couverture, puis leur effet sur le débit de simulation. Aucun cache, délai ni algorithme du moteur n'a été changé.

La restauration automatique de cette seconde paire a échoué **après l'écriture des deux mesures** : le watchdog est sorti sur un verrou Windows du fichier d'état, et son finally a fermé son jeu. Le manifest original garde restored=null. Incident archivé et watchdog corrigé ; une nouvelle instance a ensuite retrouvé la vue de référence et la pause. Les preuves sont séparées dans quality.json et runtime/scenarios/restored-camera-062-recovered.json ; ne pas présenter cette récupération comme l'achèvement sans incident du premier processus.
