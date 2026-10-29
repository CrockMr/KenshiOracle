# Environnement visible après rechargement du snapshot

Deux rechargements du même snapshot de combat, **maintenus en pause**, donnent une liste de mise à jour de **172 puis 147 personnages**. Les deux acteurs suivis ont pourtant exactement les mêmes positions, valeurs médicales et heure de jeu. Le nouvel audit montre que l'environnement visible diffère déjà avant toute activation de vitesse ; la stabilité de la seule cohorte ne suffit donc pas à qualifier une comparaison de coût de combat.

Le plugin reste **0.7.5, v100 x64, 17 outils MCP et trois hooks de systèmes**. Le collecteur Python réutilise get_scene_state et list_characters existants via une vraie session MCP stdio. Aucun nouveau hook, déploiement, création de PNJ ou enregistrement de sauvegarde.

## Preuves

- Brut : `runtime/scenarios/environment-preflight-20261028T034733Z.json`, SHA-256 **ba8afb2e688d7bb9b61f15f4041e0673fdd0e0975ac39caab24e1955a40dcd1c**.
- Analyse recalculée depuis les réponses brutes : `runtime/environment-analysis.json`.
- État final frais : `runtime/scenarios/environment-preflight-075-final.json`, relié par empreinte à la preuve des manifestes complets.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_environment_preflight.py
& ./.venv/Scripts/python.exe mcp-server/analyze_environment.py runtime/scenarios/environment-preflight-20261028T034733Z.json
```

La première commande nécessite encore la propriété du snapshot `KenshiProbe_test_scene_20261028T022539600581Z` dans la même session du plugin. Elle n'active pas la simulation du combat et recharge la copie initiale en pause à la fin. Les paramètres de sauvegarde de ce pilote sont explicites dans le script ; il ne crée pas de snapshot de remplacement. La seconde commande travaille hors jeu et refuse un résumé enregistré qui ne correspond plus au brut.

## Observation

Chaque rechargement est observé deux fois, environ 0,3–0,4 seconde puis 2,0 secondes après disponibilité. Chaque capture encadre l'inventaire par deux lectures de scène, séparées ici de deux frames. Les quatre captures sont complètes pour la liste de mise à jour demandée, en pause, avec heure, caméra et effectif concordants aux bornes. **Ce ne sont pas des captures atomiques de tout le monde du jeu.**

| Faction | Rechargement 1, deux captures | Rechargement 2, deux captures |
| --- | ---: | ---: |
| Bloodraiders | 1 | 1 |
| Drifters | 1 | 1 |
| Fogmen | 74 | 48 |
| Mercenary Guild | 7 | 7 |
| Mongrel | 85 | 86 |
| Nameless | 2 | 2 |
| Skeletons | 1 | 1 |
| Tech Hunters | 1 | 1 |
| **Total** | **172** | **147** |

Dans un même rechargement, les deux inventaires ont exactement les mêmes multiplicités de noms/factions et les mêmes positions. Entre les deux rechargements, les différences de libellés sont : 26 occurrences de Fogman/Fogmen et une d'Ex-Servant/Mongrel en moins ; une d'Outlaw/Mongrel et une de Shinobi Citizen/Mongrel en plus. Ces différences sont celles de la liste observée ; elles ne prouvent ni apparition, ni décès, ni déplacement d'acteurs identifiés. La cause de la variation n'est pas établie par ce relevé.

Dix groupes de libellés se répètent dans chaque inventaire. Les noms et factions ne sont donc pas des identifiants individuels. L'analyse conserve les multiplicités, trie les lignes avant empreinte et distingue l'empreinte des libellés de celle des positions ; un simple réordonnancement ne produit pas un changement artificiel. Les anciennes observations snapshot-paused-settling-075 avaient déjà des effectifs stables sur cinq secondes, mais différents entre rechargements (172 puis 162). Attendre sans nouvelle preuve n'est pas présenté comme un remède.

Les quatre captures retrouvent les deux acteurs de référence avec différence médicale, spatiale et d'horloge nulle, à **404,3666667938232 heures**. La différence d'environnement est donc visible alors que le précédent garde de cohorte accepte les départs. Cela renforce les limites déjà observées dans le quartet x1/x5, sans expliquer causalement ses dommages ou ses temps CPU.

## Garde ajouté aux futurs essais

`live_snapshot_horizon.py` collecte désormais cet environnement **avant toute commande de vitesse**. Le premier environnement admis sert de référence ; une capture incomplète, changeante, hors pause ou différente en libellés/positions est conservée avec un motif d'exclusion, puis la campagne s'arrête et restaure la copie. Aucune nouvelle boucle de rechargement ne cherche opportunément un état qui passe le garde.

La limite de requête de ce pilote est **250 lignes**. Une réponse plus courte que total_update_list n'est pas considérée comme exhaustive, y compris si la cause est autre que cette limite. Les erreurs de protocole ou de taille de réponse remontent ; le collecteur n'annonce pas une liste complète après erreur. Les champs de scène encadrent les lectures, sans donner une identité persistante ni tous les états d'IA ou d'équipement. Le suivi heavy-inventory-measurements.md valide ensuite 412 lignes avec le plafond existant de 500, désormais utilisé par défaut dans le contrôleur d'horizon ; le plafond réseau de 64 Kio reste indépendant.

Le garde est testé hors jeu et rejoué sur les quatre captures natives existantes : **accepté, accepté, rejeté, rejeté** par rapport à la première. Ce rejeu est explicite dans le rapport. Aucun nouveau quartet de combat n'a été lancé pour répéter l'échec de comparabilité déjà établi ; l'intégration du garde dans un futur parcours natif de combat reste à observer. Même un état visible égal ne suffira pas à prouver la déterminisation complète.

## Validation et état laissé

**165 tests Python passent en 4,01 s.** Les nouveaux cas couvrent noms répétés, ordre des lignes, variation de libellés à effectif égal, positions distinctes, données incomplètes/non finies, horloge/pause/caméra changeantes, identité du processus et désaccord résumé/brut.

Les manifestes complets restent conformes : **702 fichiers pour KenshiProbe_validation, 702 pour KenshiProbe_test, 738 pour le snapshot**. settings.cfg est identique après le pilote et les gardes de récupération restent false. Le PID 19892, son chemin et sa date de création sont vérifiés ; partie prête en pause, caméra source normale, Edge scrolling=true, aucun combat suivi actif ni contrôle temporaire restant. Watchdog frais, zéro erreur de publication, échéance config/activation inchangée **28 octobre 22 h 15 UTC**. Aucun helper de campagne ne reste actif.

La capture de piles CPU administrateur est toujours en attente, sans nouvelle trace. Le travail suivant doit établir un environnement et un critère de tâche comparables, ou attribuer les autres threads par piles si le pilote devient disponible. Ni la raison de la variation d'inventaire ni un gain d'optimisation ne sont annoncés.
