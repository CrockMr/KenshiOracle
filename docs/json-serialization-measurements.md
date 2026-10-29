# Sérialisation JSON synthétique et version 0.8.12

**Le nouveau sérialiseur écrit les mêmes octets avec moins de travail intermédiaire.** Sur deux arbres synthétiques propres de20,8 et25,9 Kio, le rapport médian apparié ancien/nouveau est **3,350763 et3,542731**. C’est une amélioration locale de sérialisation, mesurée hors jeu ; aucun gain de FPS ni de CPU exclusif du moteur n’est démontré.

## Mesure reproductible

`tests/benchmark_json.cpp` n’inclut que Windows et notre bibliothèque JSON, sans SDK ni données du jeu. Trois fixtures déterministes : petit objet de80 octets,40 acteurs **synthétiques** avec sept parties et100 lignes **synthétiques** avec trois parties. Elles ne reproduisent pas tout le schéma de scène ou de statistiques du jeu ; le nombre40 n’en fait pas une mesure du coût réel d’un PNJ.

Compilation **MSVC2010/v100 x64**, flags **/O2 /EHsc /MD /W3**. Chaque acquisition lance trois processus ; chacun mesure sept répétitions en ordre tournant de cinq opérations,60 itérations par cellule : construction avec ses copies internes et destruction, copie/destruction d’un arbre préconstruit, enveloppe avec copie/destruction, sérialisation de référence et sérialisation courante. Chaque cellule est chronométrée par QPC et son temps divisé par60. Les premières répétitions sont conservées. Un checksum consommé empêche de ne mesurer qu’une boucle vide ; aucun compteur d’allocations n’est collecté.

Les temps sont muraux inclusifs, avec charge système ambiante, allocations, caches et effets d’ordonnancement non isolés. Le jeu demeure en pause pendant ces acquisitions, mais il n’est pas suspendu ; les valeurs ne sont pas du CPU exclusif. Le benchmark n’utilise pas les mêmes optimisations de liaison que la DLL et n’est pas une mesure directe de son débit réseau.

`tests/json_legacy_serializer.h` conserve **notre** sérialiseur0.8.11 comme oracle de compatibilité. Seule la qualification récursive du namespace et un alias de type diffèrent pour éviter ADL ; ce n’est ni du code du jeu ni une décompilation. Dans le premier binaire, ce code et le sérialiseur courant0.8.11 donnent les mêmes octets et des rapports médians appariés0,997585/0,998404/1,011076, proches de1. Dans le second binaire, seul **plugin/json.h** diffère dans l’inventaire des sources du benchmark ; les compilateurs, flags, fixtures et code de mesure restent les mêmes.

## Résultats du binaire candidat

Temps moyens par opération en millisecondes sur21 cellules, chacune de60 itérations. « Copie » inclut la destruction ; « construction » inclut les copies internes de la fixture. Les rapports sont appariés par processus/répétition, pas calculés entre deux jeux ou deux mondes différents.

| Fixture | Octets | Construction | Copie | Enveloppe + copie | Sérialisation ancienne | Nouvelle | Rapport médian ancien/nouveau |
|---|---:|---:|---:|---:|---:|---:|---:|
| Petit objet |80|0,002014|0,000512|0,001127|0,007267|0,001726|4,409412|
|40 acteurs synthétiques |20806|1,891860|0,174992|0,173433|2,973062|0,883630|3,350763|
|100 lignes synthétiques |25928|2,345826|0,225878|0,225815|3,715743|1,037406|3,542731|

Rapports appariés min..max :2,917605..6,238757 pour le petit objet,**3,201990..3,575176** pour20,8 Kio,**3,306065..4,009083** pour25,9 Kio. Les valeurs minuscules du petit objet sont plus sensibles au bruit ; les21 durées brutes sont conservées pour chaque opération et fixture. Les coûts de copie/construction ne changent pas dans cette version ; les différences de moyennes entre captures séparées restent descriptives.

## Changement et compatibilité

Sous0.8.12, `json::dump` utilise `appendQuoted` et `appendSerialized` pour écrire récursivement dans un seul buffer. Il évite un ostringstream par clé, chaîne, booléen ou conteneur, ainsi que les chaînes temporaires des sous-arbres. **Les nombres gardent exactement le formatage v100, locale classic et précision16 de0.8.11** ; aucun algorithme numérique nouveau. L’ordre des clés map, l’échappement des contrôles/quotes/backslash, les octets UTF8, les valeurs non finies rendues null et l’absence d’espaces sont conservés.

`tests/test_json.cpp` compare les sorties octet par octet à l’oracle : octets0..255 dans chaînes/clefs,12 valeurs numériques spéciales (dont−0,extrêmes,subnormal,Inf/NaN),10000 nombres déterministes sous locale C++ à virgule,1000 arbres imbriqués déterministes et quatre tailles autour64 Kio. Les tests existants de parseur/Unicode/surrogates/erreurs/profondeur restent passants. La comparaison couvre ces cas ; elle n’est pas une preuve formelle pour tout arbre arbitraire.

La production ne change que **plugin/json.h** et le numéro de version dans Probe.cpp. Les copies de Value, la file, les hooks, l’accès Game, les types/layout SDK et les algorithmes moteur ne changent pas. Toujours17 outils et trois sondes charsUpdate/findPath/Havok. La limite de ligne/réponse64 Kio et le contrat d’erreur restent identiques ; les tests de grandes chaînes natifs vérifient les octets produits, pas à eux seuls la totalité du comportement TCP aux limites.

## Provenance et rejeu

- Baseline : **runtime/json-benchmark/legacy-0811/controller.json**, SHA **acf74c6642e9a72e7c80ca161e86f68d6c9efd6b808d1e2683304ea0411b93b1**.
- Candidat : **runtime/json-benchmark/append-candidate-0812/controller.json**, SHA **b1b7d86fe7dede32ee6471900463a6ff23d7c221b50d618517c1a81f714fdc24**.
- Rapport : **runtime/json-benchmark-analysis-0812.json**. Chaque répertoire contient les sorties stdout brutes et leur empreinte, le binaire propre exact et les empreintes des cinq sources utiles.

```powershell
& .\.venv\Scripts\python.exe mcp-server\analyze_json_benchmark.py runtime\json-benchmark\legacy-0811\controller.json runtime\json-benchmark\append-candidate-0812\controller.json --baseline-sha256 acf74c6642e9a72e7c80ca161e86f68d6c9efd6b808d1e2683304ea0411b93b1 --candidate-sha256 b1b7d86fe7dede32ee6471900463a6ff23d7c221b50d618517c1a81f714fdc24 --output runtime\nouveau-rapport-json.json
```

L’analyse vérifie plan compilateur/architecture/ordre/comptes, durées finies/positives et unités cohérentes, fingerprints de fixture stables, checksum consommé, sources de mesure inchangées horsjson.h, empreintes des stdout et binaires propres. Les empreintes FNV des fixtures servent de contrôle rapide en complément de la comparaison native exacte, pas de preuve cryptographique de contenu. Les captures sont conservées, pas écrasées par un nouveau lancement.

## Déploiement local et validation

**624 tests Python passent en23,48 s**, dont15 nouveaux contrôles d’analyse/rejeu ; tests natifs JSON v100 passent. DLL0.8.12 **280064 octets/SHA8077d19487888e152cca41e14058400f1e9414cbac6b16b1cde35ce669ae78ed**, PDB propre **10341376 octets/SHA c363dbd5abf66e46a37eed1fc909ab1307e50fe6b6ca194f3503375f539314cd** sous runtime/symbols/0.8.12. Déploiement archivé **crashes/20261028T153641982090Z-deployment-0812**, preuve runtime/deploy-0812.json. Les anciens processus sont vérifiés par exe/commande/création avant arrêt et l’ancienne DLL0.8.11 est préservée.

Le smoke **runtime/json-serializer-0812-smoke.json** valide le vrai MCP,17 outils,trois sondes,Havok active,identités SDK,pause et métadonnées de service. Un contrôle réseau ultérieur vérifie JSON tronqué,clé dupliquée,UTF8 invalide et commande inconnue avec identifiant Unicode/quote/backslash/newline, puis ping et copie toujours en pause. Le premier contrôleur de wire attendait à tort une erreur chaîne au lieu de l’objet code/message documenté ; son échec **runtime/json-serializer-0812-wire.json** est conservé, sans mutation du jeu. Attendu corrigé après relecture de error() et du protocole, nouvelle capture distincte **runtime/json-serializer-0812-wire-1793201950211417600.json**,completed=true/quatre cas. Il ne s’agissait pas d’une régression native.

L’audit indépendant **runtime/json-serializer-0812-final.json** recalcule les sauvegardes/snapshot/settings : **702/702/738 fichiers identiques**, settings byte-identique au préalable de déploiement et gardes false. Jeu **24320/création Unix1793201827.3623693**, pause/multiplicateur0 à **404,3333339691162 h**, caméra normale/contrôle temporaire relâché/Edge=true,bataille inactive,watchdog frais/zéro erreur,WPR inactif et aucun contrôleur restant. Helpers **13424/création1793201826.9521272** et **33328/création1793201826.9085033**, à revérifier fraîchement avant arrêt. Statistiques finales n3600 admises en48986 octets compacts réencodés. La capture réseau admise a SHA **6e8bb38717746197b9ccf97ba5cc86923334d71549f429e41f229ad62183ddbf**, l’essai rejeté SHA **bca9f202ff0f49ed179538fcfc14af9942a03ed2e51625e0ef3596ca2e15415a**. Cette étape ne réexécute pas le combat40 : le changement porte sur notre sérialiseur réseau et a déjà sa validation ciblée.

Prochaine mesure utile : vérifier une courte fenêtre active avec la télémétrie existante si la question est le coût d’observation en combat. Une optimisation des copies Value exige une mesure séparée et une vérification d’ownership/événement réseau ; elle n’est pas intégrée ici. Ne pas convertir le facteur de sérialisation en gain global. Aucune intervention utilisateur/administrateur attendue ; échéance autonome22 h15 UTC/23 h15 Paris inchangée.
