# Premières mesures de validation

Mesure locale du 27 octobre 2026 : plugin 0.3.0, jeu 1.0.65 Steam via RE_Kenshi, sauvegarde de test KenshiProbe_test copiée depuis KenshiProbe_validation. Scène extérieure Gut, deux personnages joueur, caméra de chargement inchangée, vitesse effective 1, partie non en pause. Résolution 1280x720 choisie par l'utilisateur. VSync activée dans la configuration.

Trois fenêtres distinctes de 300 frames, après cinq secondes d'échauffement. Réponses brutes dans runtime/measurements/gut-x1-validation.json (fichier local ignoré par Git), avec horodatages, versions, hash de mods.cfg et états encadrant les fenêtres.

| Fenêtre | Moyenne ms | Médiane ms | p95 ms | p99 ms | Maximum ms | charsUpdate moyen ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 10,390 | 10,136 | 12,144 | 15,697 | 17,834 | 0,213 |
| 2 | 10,986 | 10,512 | 13,762 | 16,864 | 19,798 | 0,233 |
| 3 | 10,699 | 10,333 | 12,608 | 16,382 | 18,369 | 0,228 |

charsUpdateUT moyen : 0,00385 à 0,00409 ms par fenêtre. Ces deux hooks ne couvrent pas toute l'IA et peuvent se chevaucher. La scène n'est pas une grosse bataille et aucune ville peuplée n'a été préparée.

Codex, Firefox, Steam et Discord étaient ouverts ; leur charge CPU n'a pas été quantifiée. La simulation avance pendant les fenêtres. Ces résultats valident la collecte et donnent sa variation dans cette scène ; ils ne démontrent pas de gain d'optimisation, ne permettent pas de comparaison avec les mesures antérieures à une autre résolution et n'identifient pas le pathfinding comme goulot.

Le scénario à vitesse 5, les répétitions après rechargement identique et les scénarios ville/bataille restent à mesurer suivant benchmark-protocol.md.

## Série appariée 0.3.2

Une seconde série a rechargé KenshiProbe_test avant chacune des deux conditions, gardé la caméra de chargement et appliqué cinq secondes d'échauffement réel. Même résolution 1280x720 et trois fenêtres distinctes de 300 frames par vitesse. Données locales : runtime/measurements/paired-20261027T225206Z/x1.json et x5.json. Le processus est resté identique pendant toute la paire ; la vitesse a été relue et restaurée à 1 après l'essai.

| Vitesse | Fenêtre | Moyenne ms | p95 ms | p99 ms | Maximum ms | charsUpdate moyen ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 12,538 | 18,234 | 37,964 | 54,617 | 0,354 |
| 1 | 2 | 11,218 | 13,109 | 16,563 | 18,693 | 0,242 |
| 1 | 3 | 11,500 | 14,680 | 18,588 | 20,158 | 0,256 |
| 5 | 1 | 12,254 | 14,743 | 17,544 | 19,452 | 0,291 |
| 5 | 2 | 12,013 | 14,411 | 17,638 | 20,221 | 0,268 |
| 5 | 3 | 12,045 | 15,304 | 19,679 | 21,485 | 0,276 |

La première fenêtre à vitesse 1 contient un pic de 54,617 ms ; il est conservé. Les durées moyennes des deux conditions se chevauchent et l'ordre est fixe (1 puis 5). Une seule paire, une charge concurrente non quantifiée et une couverture partielle des systèmes ne permettent pas de conclure sur le goulot ou sur une différence statistique robuste. Aucun remplacement de système ou gain de performances n'a été réalisé.

La suite utile est une répétition en ordre alterné, puis une instrumentation ciblée de la navigation et des scènes ville/bataille conservées. Le plafond demandé de trois hooks de profilage laisse un emplacement pour un candidat ciblé.

## Navigation observée en 0.4.0, ordre 5 puis 1

Le troisième hook est NavMesh::findPath. La version 0.4.0 a été compilée en v100, chargée par la reprise automatique et confirmée par ping.navmesh_profiling=true. Les fenêtres identifiées ont été vérifiées sans chevauchement. Données locales : runtime/measurements/paired-20261027T230735Z/ (28 octobre, vers 00 h 07 Europe/Paris).

| Vitesse | Frames | Moyenne frame ms | Appels findPath | Temps findPath moyen par frame ms | Plus long appel ms |
| --- | --- | --- | --- | --- | --- |
| 5 | 6068–6367 | 12,419 | 39 | 0,00658 | 0,11970 |
| 5 | 6373–6672 | 11,509 | 41 | 0,00750 | 0,18940 |
| 5 | 6677–6976 | 11,994 | 30 | 0,00579 | 0,11180 |
| 1 | 7497–7796 | 12,155 | 75 | 0,25440 | 2,01300 |
| 1 | 7807–8106 | 12,014 | 67 | 0,25103 | 1,89980 |
| 1 | 8114–8413 | 11,726 | 68 | 0,25423 | 1,99180 |

Le hook observe de vrais appels ; leur coût varie nettement entre les deux conditions de cette paire. Le nombre et la nature des requêtes ne sont pas identiques, la simulation évolue différemment selon la vitesse et les caches ne sont pas remis à zéro par le protocole. Ces chiffres ne démontrent donc pas une loi de coût selon la vitesse ni une amélioration par rapport aux versions précédentes. Le temps est mural et inclusif, avec attribution des appels à leur frame de fin ; il ne mesure pas le CPU exclusif et ne couvre pas les autres chemins de navigation comme directPath.

Le plafond est maintenant atteint : trois hooks de systèmes. La prochaine étape porte sur les scénarios lourds et les requêtes représentatives, en conservant les limites de couverture et les conditions de cache explicites.
