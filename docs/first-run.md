# Première exécution

Cette procédure prépare l'oracle du Kenshi original 0.9.5, schéma 0.1, en conservant l'installation KenshiProbe existante. Les preuves de la version livrée et la portée de chaque série réelle figurent dans [le bilan de livraison](oracle-phase1-delivery.md). Les rapports précédents restent historiques. Reproduire les vérifications sur sa propre installation et ses sauvegardes. Le comparateur MeitouClient ne fait pas partie de cette installation.

1. Installer Visual Studio 2019 ou plus récent **et** les compilateurs Visual C++ 2010 x64. Le toolset moderne seul ne suffit pas. Obtenir les dépendances de https://github.com/BFrizzleFoShizzle/KenshiLib_Examples_deps ; suivre son Setup.bat et son README. Définir KENSHILIB_DIR vers son KenshiLib et BOOST_INCLUDE_PATH vers boost_1_60_0. Conserver les en-têtes, DLL et bibliothèques d'une version cohérente.
2. Ouvrir plugin/KenshiProbe.vcxproj directement dans Visual Studio. Refuser le changement du toolset v100. Choisir Release|x64, compiler. La variante Debug est proposée par le projet mais le README des exemples la signale comme cassée. DLL attendue : plugin/build/Release/KenshiProbe.dll.

   Sur cette machine, `cmd /d /c plugin\build-v100.cmd` configure v100, les dépendances locales dans references/ et MSBuild de Visual Studio 18. Le chemin Boost stage/lib est inclus dans le projet. Pour les essais natifs du parseur : `cmd /d /c tests\test-json-v100.cmd`. Ces deux scripts utilisent les chemins d'installation locaux de Visual Studio.

   Depuis 0.4.0, build-v100.cmd appelle aussi prepare_deps.py : il corrige quatre typename et le tag struct EdgePathNode dans le header NavMesh du checkout officiel connu. Il protège aussi les deux déclarations identiques de `BuildingDesignation` dans `Platoon.h` et `Building/Building.h` par une garde commune ; les noms et valeurs sont conservés, sans changement d'ABI. Une divergence entre les déclarations arrête le script. Pour un build direct dans Visual Studio, exécuter d'abord `.venv/Scripts/python.exe plugin/prepare_deps.py`. Ne pas modifier manuellement les adresses ou les structures ; le script vérifie la forme attendue des déclarations.
3. Installer RE_Kenshi à partir de sa distribution officielle et confirmer sa compatibilité avec la version locale. Vérifier sa présence au menu et employer une DLL KenshiLib cohérente avec ses en-têtes. L'installation locale a été validée avec RE_Kenshi 0.3.5, KenshiLib 0.5.0 et l'exécutable de compatibilité Kenshi 1.0.65 Steam ; voir validation.md pour les essais réels.
4. Pour l'archive précompilée, suivre sa notice : elle fournit les deux DLL, le manifeste et un descripteur `.mod` original vide ; extraire dans le dossier Kenshi puis activer KenshiProbe au lanceur. Pour une installation depuis les sources, créer un mod KenshiProbe avec le FCS ou générer ce descripteur avec `release/prepare_release.py` après compilation. Placer les deux DLL et `plugin/RE_Kenshi.json` dans `Kenshi/mods/KenshiProbe/`. Le manifeste nomme le bootstrap dans `PreloadPlugins` et la sonde dans `Plugins` ; le bootstrap est inactif sans son fichier d'activation. Aucun descripteur ni donnée du jeu existant n'est copié dans la release. Voir [préparation de la release](../release/README.md).

   Installation locale réalisée : Re_Kenshi/mods/KenshiProbe/ contient la DLL, le manifeste et le .mod vide du modèle officiel HelloWorld, renommé. `KenshiProbe.mod` a été ajouté à Re_Kenshi/data/mods.cfg ; copie préalable : mods.cfg.before-kenshi-probe. Aucun manifeste d'un autre mod n'a été modifié. L'installation complète est ignorée par Git.
5. Copier config.example.json vers config.json si nécessaire. Vérifier executable, arguments, log, dump_directory, runtime, oracle_output et runs. Pointer vers le processus qui reste actif pendant le jeu. Les dossiers runtime, crashes et runs sont locaux et ignorés par Git. `oracle_output` est le dossier des captures natives ; `runs` reçoit les copies validées et les rapports. Les chemins relatifs sont résolus par rapport au fichier de configuration.

   Pour cette installation, config.json pointe vers Re_Kenshi/RE_Kenshi/kenshi_x64.exe avec `--norestart` et `working_directory` égal à Re_Kenshi/. Cela évite de surveiller uniquement le processus intermédiaire qui s'arrête après avoir lancé la compatibilité. Le watchdog peut être borné par une échéance ou rester actif sans échéance ; le bootstrap optionnel et son activation explicite sont décrits plus bas.
6. Installer les dépendances Python 3.11+ et lancer un seul watchdog depuis la racine. Dans PowerShell :

   ```powershell
   python -m venv .venv
   & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   $env:PYTHONPATH = (Join-Path (Get-Location) 'mcp-server')
   $env:KENSHI_PROBE_CONFIG = (Resolve-Path 'config.json').Path
   & .\.venv\Scripts\python.exe launcher/watchdog.py --config config.json
   ```

   Le watchdog transmet `port` et le chemin `oracle_output` au nouveau processus par `KENSHI_PROBE_PORT` et `KENSHI_ORACLE_OUTPUT`. Pour un lancement manuel, fournir ces variables avant le lancement et conserver la même valeur de sortie côté serveur. Modifier la configuration d'un watchdog existant ne modifie pas l'environnement d'un jeu déjà lancé. Ne pas lancer un deuxième watchdog pour contourner cette limite.
7. Ajouter au client MCP un serveur stdio : commande chemin absolu de `.venv/Scripts/python.exe`, argument chemin absolu de `mcp-server/server.py`, variable `KENSHI_PROBE_CONFIG` égale au chemin absolu de `config.json`. `ping` doit annoncer `plugin_version:"0.9.5"`, `schema_version:"0.1"`, une `instance_id` et les versions du jeu. Vérifier le préfixe `[KenshiOracle]` dans le journal et l'écoute sur **127.0.0.1 uniquement**. La télémétrie 0.8.20 est conservée ; aucune nouvelle campagne de performance n'est à lancer.
8. Choisir une sauvegarde locale de test déjà copiée et conservée hors du dépôt. Appeler l'outil MCP `load_save(name="nom-de-la-copie")`. Par défaut il lit d'abord les origines FCS type 15 de `quick.save` et de ses fichiers platoon indexés, charge, attend la disponibilité en pause puis prépare les liaisons d'identité dans la sonde. Les hashes des sources sont vérifiés après chargement ; aucune sauvegarde n'est modifiée. L'ensemble est borné par `load_timeout` (120 s). `save_root:null` utilise la racine SDK annoncée par `ping` ; un chemin explicitement configuré doit correspondre. Un format non pris en charge échoue explicitement. `wait=False` ne renverrait que l'acceptation et ne préparerait pas ce contexte. Relire `ping` puis `get_clock` ; `world_ready`, `paused`, `saved_origins_prepared` doivent être vrais et `saved_origins.save_name` doit correspondre. `current_save` est un nom interne et ne prouve pas le nom du dossier chargé. Le chargement automatique initial du watchdog ne remplace pas cet appel MCP complet.
9. Appeler `dump_state()` sans paramètre. Il renvoie le chemin d'une photo validée dans `runs/dumps/`, son `sha256`, sa taille, l'horloge et les comptes de collections. Le serveur refuse une photo invalide ou un chemin hors de `oracle_output`. Pour revérifier le fichier hors du jeu, remplacer la valeur de chemin ci-dessous :

   ```powershell
   $env:PYTHONPATH = (Join-Path (Get-Location) 'mcp-server')
   & .\.venv\Scripts\python.exe -c "from oracle_schema import load_state; import sys; s=load_state(sys.argv[1]); print(s['schema_version'], len(s['characters']))" 'chemin-absolu-vers-la-photo.json'
   ```

   Conserver cette preuve et ses versions. Un état valide ne prouve pas encore l'exhaustivité des chargés ni la persistance de leurs identités ; voir [couverture de l'état](state-coverage.md).
10. Copier un exemple de `scenarios/` dans un fichier local, renseigner `save` et, pour les ordres, les identifiants du dump. Avant chaque essai, charger **la sauvegarde de ce scénario** avec `load_save(name="valeur-exacte-du-champ-save")` et attendre le retour prêt en pause. La pause initiale est exigée. Établir une sélection de vitesse positive connue avec `set_game_speed(speed=1, preserve_pause=True)` et vérifier `get_scene_state().selected_game_speed == 1` ; `get_clock().speed` reste zéro en pause. Cette préparation est requise après chaque chargement manuel : aucun getter public n'expose la sélection antérieure. Lancer ensuite `run_scenario(path="chemin-absolu-vers-le-scenario.json", repeat=3)`. Chaque répétition recharge cette sauvegarde et règle sa vitesse ; ne pas intervenir dans l'interface pendant l'exécution. Le résultat indique le dossier et `report.json`/`report.md`, avec heures demandées/réelles, champs stables/variables et vérification de restitution. Les états se trouvent dans `runs/<scénario>/<horodatage>/<exécution>/`.

   Avant d'armer le journal de restitution ou de modifier le jeu, le runner Python appelle `wait_stable_controls` : au moins trois lectures sur des frames distinctes doivent couvrir une fenêtre continue d'au moins **0,5 seconde d'horloge monotone**, en pause et sans changement de l'horloge du jeu, dans un délai maximal de **10 secondes**. Chaque lecture est encadrée par deux `ping` qui vérifient la même instance et la disponibilité du monde. La dernière pose de la fenêtre devient la référence ; les contrôles complets et la sélection connue sont exigés dès la capture. Après armement du journal, cette référence est figée : un déplacement ultérieur ne la remplace pas.

   Le runner termine sur la sauvegarde **du scénario**, puis restitue caméra, vitesse et pause capturées avant l'essai ; il ne recharge pas automatiquement une autre sauvegarde initiale et ne reconstruit pas une partie non sauvegardée. Une caméra capturée dans une autre région peut être limitée par le monde chargé et faire échouer la restitution : charger le bon scénario avant sa capture est un prérequis. La caméra utilise `camera_zoom` **signé**, égal au Z local du nœud caméra : il doit être strictement négatif en mode stratégique ; zéro et les valeurs positives sont admis en mode libre. Conserver la valeur capturée. `camera_node_position` sert au diagnostic de cette position locale.

   La restitution 0.9.5 prépare les contrôles en pause et maintient le défilement verrouillé. Une fenêtre stable de trois frames distinctes couvrant 0,5 seconde, au plus 10 secondes, mesure le centre suivi réel ; un commit unique corrige son décalage supplémentaire puis libère le verrou. Cela tient compte d'une hauteur d'acteur légèrement différente après chargement sans supposer une constante de caméra. Python vérifie ensuite la référence figée après libération pendant une seconde fenêtre de mêmes bornes. Tolérances : centre/position/zoom 0,05, quaternion 0,0001 et sélection de vitesse 0,000001. Une pose stable mais incorrecte échoue à l'échéance. Aucune mutation n'est réessayée. Ce contrôle ne garantit pas l'immobilité face à une entrée ultérieure. `restore_required` ne devient faux qu'après vérification réussie.

   Les lectures initiales figurent dans `report.json.control_capture_observations`, la base de calibration dans `report.json.restoration.baseline_observations`, et les lectures après commit dans `report.json.restoration.observations`, avec `restoration.verified`. Les anciens rapports conservent leur protocole et leur portée d'origine.

   En cas d'interruption, consulter `runtime/oracle-restoration.json` et appeler `restore_scenario()` pour récupérer la scène sans reprendre les répétitions. Cet outil utilise par défaut la sauvegarde du journal. Uniquement si les contrôles capturés appartiennent à une autre sauvegarde connue, appeler `restore_scenario(save="copie-originale-connue")` ; aucune sauvegarde n'est déduite automatiquement. Le nom est validé, la sauvegarde employée est tracée dans `recovery_save` et renvoyée, puis la même fenêtre de vérification s'applique à la référence enregistrée. Lorsque la vérification a été atteinte, le journal conserve ses observations dans `recovery_attempt` et l'erreur éventuelle ; en échec, les contrôles enregistrés et `restore_required:true` restent conservés. Un journal avec `restore_required:true` bloque un nouvel essai jusqu'à récupération vérifiée. Ne pas simplement effacer ce journal.

`get_frame_stats(n=100)` utilise désormais `aggregates` ; préciser `detail="full"` pour un diagnostic détaillé. `game_status` décrit le watchdog, `read_log` lit son journal configuré et `restart_game` demande une relance. Son acquittement ne signifie pas que la sauvegarde est prête. Les essais de crash/gel restent séparés du premier dump ; leur historique est dans [validation.md](validation.md). Ctrl+C sur le watchdog ferme le jeu qu'il possède.

Sans jeu, exécuter `.venv/Scripts/python.exe -m pytest -q`. En environnement Codex restreint, ces tests requièrent l'accès aux sockets loopback et au sous-processus stdio.

Les tests de l'oracle sont `tests/test_oracle_schema.py`, `tests/test_fake_probe.py` et les tests d'orchestration/serveur associés. `tests/fake_probe.py` n'utilise que ses propres données synthétiques ; il ne contient aucune sauvegarde. Les rapports de [phase 1](oracle-phase1-validation.md) et du [complément ville](oracle-ville-calme-validation.md) conservent commandes, résultats, essais non réalisés et TODO. L'exemple ville utilise maintenant la copie locale `ville-calme` fournie pour cette validation ; adapter le nom à sa propre copie. La présence du JSON seul ne prouve pas qu'une autre installation réussira l'expérience.

## Scénarios sans client MCP ni agent

Depuis la racine, après installation des dépendances et démarrage du jeu avec la sonde, charger une copie de test et attendre la fin du chargement initial. Puis :

```powershell
& .\.venv\Scripts\python.exe -m launcher run-scenario scenarios/ville-calme.json --repeat 3 --config config.json --prepare
```

Adapter d'abord le scénario à une copie de sauvegarde locale. `--prepare` recharge explicitement sa sauvegarde, attend le monde prêt en pause, prépare les identités sauvegardées et sélectionne x1 en conservant la pause. Le scénario capture ensuite cette référence. La restitution revient à cette sauvegarde préparée et à ses contrôles ; elle ne reconstruit pas une partie non sauvegardée antérieure. Le jeu doit déjà être lancé ; cette commande n'ouvre ni client MCP ni agent et ne démarre pas de watchdog.

La sortie JSON indique `output` (dossier de résultats), `report` (`report.json`), `summary` (`report.md`), le nombre d'exécutions et `restored`. Chaque photo est validée, canonicalisée et hashée par le runner existant. Un échec renvoie un code de sortie non nul et, si le runner a démarré, le chemin de son rapport. `--repeat` accepte 1 à 100 ; sans cette option, le nombre vient du scénario.

Pour préparer puis vérifier la scène séparément, utiliser `python -m launcher prepare-scenario scenarios/ville-calme.json --config config.json`. On peut ensuite omettre `--prepare` de `run-scenario` ; les préconditions de l'étape 10 restent applicables. La préparation refuse un journal de restitution en attente.

Après interruption, récupérer la scène avec la même configuration :

```powershell
& .\.venv\Scripts\python.exe -m launcher restore-scenario --config config.json
```

Le paramètre optionnel `--save nom-connu` correspond à l'override de récupération documenté à l'étape 10. Les résultats et journaux restent dans les dossiers locaux ignorés par Git.

## Campagne autonome optionnelle

Le build produit aussi KenshiProbeBootstrap.dll en v100 x64, avec MFC dynamique et WholeProgramOptimization (requis pour la résolution de ses stubs KenshiLib). Installer les deux DLL et le manifeste de plugin/ : PreloadPlugins charge le bootstrap et Plugins charge le plugin principal.

Par défaut, le bootstrap ne fait rien. Le fichier `mods/KenshiProbe/auto_launch.enabled`, lu au chargement du bootstrap, accepte deux modes :

- Un entier décimal positif en secondes Unix UTC : activation seulement tant que cette échéance est future, y compris lors du callback OnPaint.
- Le mot exact `unlimited` : activation sans échéance, lorsque cette durée a été explicitement autorisée. Un fichier absent, vide, malformé ou dépassant 64 octets désactive le bootstrap. Les espaces ASCII périphériques sont admis ; les signes, suffixes, tokens multiples, dépassements d’entier64 et variantes de casse sont rejetés.

Au premier OnPaint autorisé du lanceur, il appelle une seule fois la méthode publique OnBnClickedLauncherOk après la peinture originale. Ces deux méthodes viennent de kenshi/GameLauncher.h ; le hook et les API restent les mêmes. La lecture du fichier est unique au chargement : retirer ou modifier le fichier agit sur les prochains lancements, sans modifier un bootstrap déjà chargé.

Après compilation et installation du bootstrap mis à jour, activer explicitement le mode sans échéance depuis la racine du projet :

```powershell
Set-Content -LiteralPath '.\Re_Kenshi\mods\KenshiProbe\auto_launch.enabled' -Value 'unlimited' -Encoding ascii
```

L’ancienne DLL reconnaît uniquement les dates numériques : elle laisse le lanceur interactif si elle lit `unlimited`. Il faut donc installer la version mise à jour avant d’employer ce token. Validation native du parseur et des limites : `cmd /d /c tests\test-bootstrap-activation-v100.cmd`.

L’échéance initiale de cette session était 1793225700, soit le 28 octobre 2026 à 23 h 15 Europe/Paris. L’utilisateur a ensuite autorisé la continuation sans date de fin ; l'ancien fichier d'activation et les DLL ont été archivés. Le déploiement0.8.20 a validé le nouveau bootstrap avec `unlimited` et le watchdog avec `session_until: null` : chargement automatique de KenshiProbe_test, retour en pause et audit des sauvegardes réussis. Preuves : `runtime/deploy-0820.json` et `runtime/direct-0820-final.json`.

`startup_save=KenshiProbe_test` permet au watchdog de demander ce chargement une seule fois par lancement ; une mutation dont la réponse est incertaine n’est pas réessayée. `autoload_error` expose l’échec éventuel. Depuis le plugin0.8.4, KenshiProbe_test est mis en pause avant world_ready=true ; vérifier test_save_pause_on_ready_available et paused=true après chargement. Voir [validation de la reprise en pause](autoload-pause-validation.md).

Retirer le fichier d’activation et remettre `startup_save` à null pour retrouver les prochains lancements interactifs. `session_until`, optionnel, borne le watchdog en secondes Unix : à l’échéance il arrête son processus de test et ne relance plus. Avec null ou sans cette clé, la supervision dure jusqu’à son arrêt explicite. Le mode `unlimited` du bootstrap ne change pas cette configuration indépendante. Le watchdog lit sa configuration au démarrage et ne peut pas adopter un jeu existant ; son arrêt gracieux ferme aussi le jeu qu’il supervise. Ne pas lancer un second watchdog pour appliquer une nouvelle configuration alors que le jeu actuel reste ouvert.

Les scripts tests/live_*.py sont des essais manuels, exclus de pytest. live_restart.py, live_freeze.py et les simulations de sortie arrêtent ou suspendent le processus supervisé : les réserver au processus de copie identifié. live_freeze.py vérifie son chemin et sa date de création, puis reprend le processus dans finally si la récupération n'a pas eu lieu. Il nécessite les dépendances de requirements-dev.txt.
