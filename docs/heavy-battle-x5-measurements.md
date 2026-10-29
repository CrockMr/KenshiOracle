# Combat urbain de40 PNJ à x5 — 28 octobre 2026

Le scénario Mongrel a terminé quatre fenêtres de5/5/10/10 secondes demandées, avec **40 PNJ suivis dans108 observations**, environ32,078 secondes de parcours. **36 acteurs présentent un signal médical de blessure**, jusqu’à35 sont observés sous attaque et8 inconscients ; aucune mort n’est observée. Ce sont des états échantillonnés, pas un nombre de coups ni une attribution des blessures à un attaquant.

Le plugin reste **0.8.10/v100 x64**,17 outils/trois sondes charsUpdate/findPath/Havok. Aucun changement natif, nouvel algorithme moteur ou gain de performances annoncé. Les ajouts sont un contrôleur de test, une analyse hors jeu et un collecteur de statistiques à taille bornée. **575 tests passent en21,16 s**, avec refus des cohortes incomplètes, compteurs CPU contradictoires, mauvaise vitesse/caméra, fenêtres hors bornes et faux historiques de réduction de taille.

## Préparation et limite de transport réellement rencontrée

La limite native existante est20 paires. `tests/live_heavy_battle.py` charge seulement KenshiProbe_test, déplace les joueurs près de Mongrel, laisse dix secondes à x1 puis attend la disponibilité stable, passe en pause et focalise la caméra. Modèles **16863-gamedata.base/Bloodraiders** et **1227-gamedata.base/Mercenary Guild** ; les factions sont vérifiées mutuellement ennemies avant création, relations−100 dans les deux sens. Aucune relation n’est modifiée. La commande crée40 PNJ non joueurs, une seule fois ; une préparation partielle impose un rechargement, jamais une répétition de création dans la même scène.

Le premier essai `runtime/scenarios/heavy-battle-20261028T143434395827Z.json`, SHA **d7ccdf1ce9364072ee8c40318bd292961ce5ff3e4eae9775720065436fa490c0**, reste **completed=false**. Les deux premières fenêtres sont complètes ; la troisième a ses compteurs/statistiques mais échoue sur le contexte de3600 frames, réponse native trop grande. La copie est restaurée, sauvegardes et settings intacts. Il ne s’agit pas d’un crash moteur ni d’un essai complet à intégrer comme répétition.

`mcp-server/statistics_budget.py` réduit désormais **les seules lectures get_frame_stats** après l’erreur explicite `response too large; reduce n or limit`. Le compte est divisé par deux jusqu’au succès ou à1, au plus12 appels. Toutes les tentatives sont conservées, même en échec terminal ; les erreurs de transport/disponibilité ordinaires ne sont pas retentées. Les nombres réellement retenus restent bornés par la phase, puis l’analyse vérifie leur provenance, continuité et bornes. Aucune fenêtre plus courte n’est présentée comme couvrant tout l’intervalle CPU. Cette stratégie concerne le nouveau contrôleur de combat ; elle ne rend pas rétroactivement tous les anciens scripts adaptatifs.

Les40 acteurs gardent santé détaillée complète, noms uniques et suivi à chaque observation. Les inventaires de ville sont complets avant/après,179 puis395 lignes, mais la population et les renforts évoluent. Les limites500 lignes et65536 octets restent indépendantes. La plus grande scène réencodée en JSON compact dans cet essai fait31158 octets. Aucune sauvegarde de scénario n’est écrite et la génération aléatoire n’est pas ensemencée.

## Campagne admise et reproduction

Brut : `runtime/scenarios/heavy-battle-20261028T144427381931Z.json`, completed=true, SHA **8dcc9c57886b6789d7240740f44944a9e156db5ba90bfe237580e1a5a478a82c**. Analyse finale : `runtime/heavy-battle-0810-analysis.json`. Reproduction hors jeu :

`mcp-server/analyze_heavy_battle.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER`

L’analyse revalide cohorte, santé, vitesse/caméra, progression, fenêtres de statistiques, historiques de taille, compteurs CPU natifs aux bornes et identités SDK/Windows. Le fichier de sortie doit être nouveau. La préservation des fichiers est une attestation du contrôleur dans le brut ; l’audit final recalcule séparément leurs manifestes réels.

| Fenêtre demandée | CPU processus/durée englobante | Moyenne en processeurs logiques | Frames retenues | Intervalle moyen/p99 | Inconscients max |
|---|---|---:|---|---|---:|
|5 s initiales|12,187500 s/5,187 s|2,349624|316103..316496,394|12,991564/66,3855 ms|1|
|5 s suivantes|13,156250 s/5,172 s|2,543745|316528..317027,500|10,222859/19,3947 ms|3|
|10 s suivantes|24,156250 s/10,156 s|2,378520|317079..318148,1070|9,447618/15,2917 ms|7|
|10 s finales|22,781250 s/10,141 s|2,246450|318220..319247,1028|9,826232/17,3771 ms|8|

Les intervalles sont ceux des callbacks instrumentés, sans garantie de FPS affichés. Le p99 initial est plus élevé dans cette scène, mais population176→295 au même moment, création récente et streaming/renforts empêchent de l’attribuer aux seuls40 combattants. Les populations par fenêtre sont176..295/295..301/301..332/318..399. Les résidus CPU signés **+0,046875/−0,062500/−0,203125/−0,125000 s** sont conservés sans clamp ; aucune identité de thread omise. Horloge simulée+0,234432/+0,237024/+0,465406/+0,464598 h entre les scènes propres à chaque fenêtre. Les compteurs CPU, horloges et frames ont des bornes distinctes ; les espaces entre fenêtres ne constituent pas une couverture CPU continue des32 secondes.

Les fenêtres principales sont admises au premier appel :394/500/1070/1028 frames, réponses compactes56040/57555/55446/56806 octets. Les contextes diagnostiques montrent réellement la récupération de la limite :

| Fenêtre | Comptes tentés pour le contexte | Compte admis/octet compact |
|---|---|---|
|1|3600|3600/64005|
|2|3600 refusé,1800 refusé,900 admis|900/60322|
|3|3600 refusé,1800 admis|1800/60589|
|4|3600 refusé,1800 admis|1800/58445|

Ces contextes ont des bornes différentes et peuvent chevaucher une autre fenêtre ou la préparation. Ils servent notamment à identifier des threads de navigation parmi les appels lents retenus ; absence d’un appel dans un contexte raccourci ne signifie pas zéro CPU de navigation.

## Combat et profilage

**56 observations de cible extérieure à la cohorte** sont conservées ; cela ne signifie pas56 renforts distincts. Les PNJ peuvent aussi choisir un autre membre que leur partenaire. Les variations médicales servent uniquement de signal de combat effectif, sans attribution d’attaquant ni débit de tâches. Les36 acteurs avec signal ne prouvent pas que les quatre autres n’ont subi aucune attaque entre lectures.

HavokCharacter::update est joint au rôle non rendu **TID39604/création134376698083790089** :11424/17578/32947/40733 appels dans les fenêtres, moyennes inclusives0,037349/0,038842/0,043560/0,064338 ms par frame. Son CPU par appel reste désactivé, valeurs null/indisponibles ; aucune couverture exclusive calculée. Le thread entier consomme1,46875/1,90625/3,453125/3,09375 s CPU dans les intervalles OS respectifs. Principal/rendu34996/création134376697962686336 :3,921875/4,03125/7,71875/8,078125 s CPU. Les identités sont vérifiées par création et rôles SDK encadrants, sans transporter celles d’un autre processus.

FindPath compte410/305/1344/1208 appels dans les fenêtres retenues, globalement dans le monde, sans identité d’acteur. Les durées de ces fonctions ne sont pas des coûts exclusifs à additionner au CPU du processus. Les conditions, cohortes générées et populations diffèrent des anciennes batailles à2/10 PNJ et des villes Heng : aucun coût marginal par PNJ, comparaison causale x1/x5 ni gain moteur ne découle de leur rapprochement.

## Restitution et suite

`runtime/heavy-battle-0810-final.json` confirme même jeu19264/création1793196196.268632, copie en pause/multiplicateur0 à **404,3333339691162 h**, caméra normale et contrôle temporaire relâché/Edge=true, suivi de cohorte effacé. Les **702/702/738 fichiers** source/copie/snapshot sont conformes, settings byte-identique au préalable du déploiement0.8.10, gardes false. Watchdog frais sans erreur, WPR inactif, aucun contrôleur de scénario restant ;17 outils/sept rôles/trois sondes. DLL0.8.10 inchangée, échéance du28 octobre22 h15 UTC inchangée, aucune intervention administrateur attendue.

Le diagnostic suivant peut exploiter les variations temporelles et rôles SDK déjà conservés pour décrire le pic initial, en distinguant activité de cohorte, évolution de population et travail des ressources. Le coût propre des lectures MCP de cohorte n’est pas isolé ; le quantifier dans les callbacks de service déjà existants serait utile avant d’attribuer ce pic au moteur. Une autre collecte ne doit être lancée qu’avec une question nouvelle et ses bornes ; répéter le même combat non déterministe ne suffit pas à isoler sa cause.
