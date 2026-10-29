# Inventaire borné dans une ville chargée

Le plafond existant de **500 lignes** permet un relevé complet des **412 personnages** observés dans la liste de mise à jour près de Heng. Un relevé intermédiaire limité à 250 reste correctement exclu. Il n'a pas été nécessaire de reconstruire le plugin ou de perdre la propriété du snapshot de combat pour couvrir ce cas.

Plugin **0.7.5, v100 x64, 17 outils MCP et trois hooks de systèmes** inchangés. Le nouveau collecteur utilise seulement les commandes déjà présentes, via une vraie session MCP stdio. Ce pilote vérifie couverture et admission ; il ne compare aucune performance ni aucun coût de combat.

## Preuves et reproduction

- Brut : `runtime/scenarios/heavy-inventory-20261028T040208Z.json`, SHA-256 **00c964cc855ef5c77b432eaadc2b2bcc38c171a3faa9882b991d633a21f8ad39**.
- Analyse recomputée : `runtime/heavy-inventory-analysis.json`.
- État final et manifestes : `runtime/scenarios/heavy-inventory-075-final.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_heavy_inventory.py
& ./.venv/Scripts/python.exe mcp-server/analyze_environment.py runtime/scenarios/heavy-inventory-20261028T040208Z.json --output runtime/heavy-inventory-analysis.json
```

Le pilote recharge la copie initiale, prépare Heng, laisse dix secondes de streaming à x1 et attend trois secondes de disponibilité stable, puis met en pause. Il collecte les limites **500, 250, 500**, sans activer de combat, puis restaure la copie en pause dans finally. Il ne sauvegarde pas la scène reconstruite et ne réessaie pas jusqu'à obtenir un effectif souhaité.

## Résultat

| Relevé | Limite demandée | Lignes reçues | Total de la liste de mise à jour | Couverture complète | Admission |
| --- | ---: | ---: | ---: | --- | --- |
| Premier | 500 | 412 | 412 | oui | acceptée |
| Intermédiaire | 250 | 250 | 412 | non | refusée |
| Dernier | 500 | 412 | 412 | oui | acceptée |

Les deux listes complètes ont exactement les mêmes libellés/multiplicités et positions. Les trois captures sont en pause, à **404,4196109771729 heures de jeu**, avec population et caméra concordantes aux lectures de scène qui les encadrent. Chaque inventaire est encadré sur deux ou trois frames ; il ne constitue pas une capture atomique de tout le monde du jeu. Trente-sept groupes de noms/factions se répètent dans les relevés complets : ces libellés ne sont toujours pas des identifiants persistants.

Le résultat JSON **resérialisé après lecture** représente 44 112 octets pour chaque liste complète, contre 27 042 pour la partielle. Ce ne sont pas les tailles originales exactes sur le réseau : le formatage des nombres et l'enveloppe diffèrent. Le code réseau natif vérifié impose de son côté 65 536 octets, LF inclus ; au-delà, il renvoie une erreur explicite au lieu de la grande réponse. Les réponses natives de ce pilote ont réussi. Cela ne garantit pas qu'une autre liste de 500 lignes, avec des noms plus longs, tienne dans cette limite.

Le rapport recalcule les résumés depuis les réponses brutes. Son rejeu du garde donne **accepté/refusé/accepté**, sans inférer de différence exhaustive depuis les 250 lignes intermédiaires. Les horodatages relatifs absents de ce format restent null ; les frames et horloges brutes sont conservées.

## Évolution du contrôleur et limites restantes

Le futur contrôleur `live_snapshot_horizon.py` demande désormais **500 lignes par défaut**, configurable par `--environment-limit` entre 1 et 500. Le précontrôle historique de Mongrel à 250 reste une preuve distincte. Un total supérieur au nombre de lignes reçues empêche l'admission ; une erreur de taille ou de protocole est propagée et conduit à la restauration, sans annoncer une collecte exhaustive.

Deux limites indépendantes restent donc en place : **500 lignes et 64 Kio de réponse native**. Une scène de plus de 500 entrées, ou une réponse trop grande sous ce plafond, nécessiterait une autre collecte bornée. Découper plusieurs lectures d'une liste non figée ne prouverait pas sa cohérence ; une éventuelle pagination devra copier les valeurs à un instant identifié, sans garder de pointeurs du jeu entre frames. Cette évolution native n'a pas été engagée sans preuve qu'elle soit nécessaire aux scènes actuellement observées.

Le garde d'environnement dans le parcours complet de combat n'a pas été rejoué nativement ; ses fonctions d'admission sont testées et les nouveaux relevés urbains réels sont traités par ces mêmes fonctions. Le quartet historique ne gagne pas rétroactivement ce garde.

## Validation et état laissé

**168 tests Python passent en 4,00 s.** Les nouveaux cas couvrent un inventaire complet de 450 lignes, une troncature de 501 à 500, ainsi que le format urbain avec inventaire partiel intermédiaire. Le plugin n'a pas été modifié et aucune fonction du moteur n'a été optimisée.

Les **702 fichiers de KenshiProbe_validation, les 702 de KenshiProbe_test et les 738 du snapshot géré** restent conformes aux manifestes témoins. settings.cfg est identique après le pilote, les gardes de récupération restent false, et la propriété du snapshot est préservée dans le même processus. PID 19892, chemin et création vérifiés ; copie initiale rechargée en pause, vue normale de référence, Edge scrolling=true, aucun combat suivi actif ni contrôle caméra temporaire. Watchdog frais, zéro erreur de publication, borne config/activation inchangée **28 octobre 22 h 15 UTC**.

La capture de piles CPU administrateur reste en attente. Un prochain diagnostic indépendant pourrait mesurer la répartition CPU en pause et en simulation dans une même ville, avec vue fixe et inventaires de contrôle, pour décrire le travail qui subsiste en pause. Ce serait une observation de périmètre, sans attribuer automatiquement le CPU restant au rendu ou un delta à une fonction précise.
