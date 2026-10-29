# Horloge de jeu et retours de navigation — 0.6.3

La campagne près de Heng observe une progression de l'horloge de jeu à x5 égale à **4,999 fois** celle à x1. Ce résultat concerne l'horloge ; il ne démontre pas que chaque tâche IA ou recherche de chemin termine sans retard. Aucun système du moteur n'a été optimisé ou remplacé.

## Horloges vérifiées

Les méthodes GameWorld::getTimeStamp_inGameHours(), TimeOfDay::getTotalHours(), GameWorld::getTimeStamp() et getLengthOfHourInRealSeconds() viennent de GameWorld.h et util/TimeOfDay.h ; la liaison v100 puis leurs lectures natives ont réussi. Le champ game_total_hours est resté à 404,334487915 pendant un peu plus d'une seconde de pause. Le chronomètre brut getTimeStamp a avancé de 104,432 à 105,448 pendant cette même pause : il n'est pas utilisé comme temps simulé. Preuve locale runtime/clock-pause-validation.json.

## Campagne en ville

Données : runtime/measurements/city-paired-20261028T004449Z, ordre 1 puis 5, trois fenêtres de 600 frames par condition. Rechargement et préparation de la copie avant chaque condition, contrôles de caméra à chaque fenêtre, mêmes constantes de streaming/échauffement que benchmark-protocol.md. Les intervalles d'horloge englobent les requêtes et les écarts entre fenêtres ; ils ne sont pas exactement les intervalles des statistiques de frame.

| Condition | Secondes réelles entre relevés | Heures de jeu avancées | Heures de jeu / seconde réelle |
| --- | --- | --- | --- |
| x1 | 14,911 | 0,136705 | 0,009167878 |
| x5 | 16,951 | 0,776884 | 0,045832215 |

Rapport pondéré des débits : 4,999217. getLengthOfHourInRealSeconds a renvoyé 109,090912 dans les deux conditions. Les moyennes de frame sont 7,908..8,244 ms à x1 et 9,051..9,323 ms à x5. Cette différence de frame ne se traduit pas ici par une progression de l'horloge inférieure au facteur demandé. Cela reste une scène de ville, sans bataille, avec caches/évolution de simulation et charge extérieure imparfaitement contrôlés.

## Retours de tous les appels terminés

Les nouveaux compteurs couvrent tous les appels findPath terminés dans les fenêtres, au-delà des seuls appels lents retenus.

| Condition | Retour true | Retour false | Part des retours false | Somme murale true ms | Somme murale false ms |
| --- | --- | --- | --- | --- | --- |
| x1 | 121 | 41 | 25,31 % | 41,530 | 2,530 |
| x5 | 492 | 43 | 8,04 % | 140,001 | 3,827 |

Ces proportions décrivent les appels observés de chaque condition. Elles ne prouvent pas une loi selon la vitesse : le temps simulé, les requêtes, les caches et les durées réelles diffèrent. Les retours false sont ici majoritairement très courts, sans appel ≥10 ms dans les fenêtres stabilisées. Optimiser indistinctement tous les retours false ne découle donc pas des mesures. Les sommes sont murales inclusives ; elles ne sont pas des secondes CPU exclusives ni le temps total de navigation de tous les chemins du moteur.

Le hook observe les appels globaux de NavMesh pendant cette scène. Les enregistrements ne sont pas encore associés à un personnage ni à une ville précise ; la présence d'habitants près de Heng ne suffit pas à leur attribuer chaque appel.

Un appel de 180,318 ms est présent dans le contexte x5, mais il termine à la frame 14475, **avant la préparation de ville à la frame 14517**. Il est exclu des fenêtres de ville stabilisées. Il consomme 171,875 ms CPU utilisateur, retourne false et laisse le tableau de sortie vide (0 avant/après), avec radius≈1,028 et water=6. Ce n'est pas la même configuration que les quatre appels lents précédents radius≈0,4/water=10. Le motif précis de son retour n'est pas exposé par la signature. Quatre retours true de transition ont produit 34..80 éléments de sortie, sans interprétation de longueur physique.

## État et suite

Même PID 37836 pendant les mesures, aucune relance ; le watchdog corrigé est resté sain. La vue de référence, le mode caméra normal et la pause ont été restaurés. Les deux quick.save restent identiques au SHA-256 de référence. L'audit hors jeu conserve les provenances et évite d'attribuer à une nouvelle scène les appels de contexte qui la précèdent.

La prochaine étape utile porte sur une bataille reproductible et sur la latence des tâches réellement terminées, plutôt que sur une répétition identique de cette ville. Avant de changer un algorithme ou d'ajouter un cache d'échecs, établir les invariants de maillage/portes/streaming et le lien entre les appels coûteux et le comportement des personnages. Le plafond de trois hooks reste respecté ; une nouvelle cible devra en remplacer une si elle nécessite un hook.
