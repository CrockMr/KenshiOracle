# ETW et restauration de caméra — 0.8.2

**Le pilote WPR administrateur est valide : trace de 30 932 992 octets, zéro événement et zéro buffer perdus.** La première capture à Heng a été refusée avant toute mutation ou trace parce que la caméra avait dérivé entre les essais. Le chargement protégé de 0.8.2 corrige ce passage ; la capture x1 ciblée reste à relancer dans le contexte administrateur.

## Pilote réellement enregistré

- Dossier runtime/etw/KenshiProbePilot_fd5e0c834b34 ; controller.json et validation.json vérifiés.
- SHA-256 ETL **3e875f46bf7ec889b6b1a39e50addde5d1e3f0cc003ab2d6de9582b6e7b64511**, profil WPR identique au fichier source.
- PID **37552**, chemin et création correspondant à la preuve 0.8.1 ; pause avant/après, WPR start/stop0 et cleanup_required=false.
- Intervalle ETL **07:00:41.3974028..07:00:44.4739986 UTC**, soit 3,0765958 s réelles de trace pour deux secondes demandées, avec bornes WPR supplémentaires.
- xperf -a tracestats -timespan actual : **0 lost events, 0 lost buffers**. Profil global : 13 890 événements Sampled Profile, dont 10 731 avec pile associée dans le rapport ; ceci ne prouve pas que chaque pile est complète.
- Rapport de piles filtré sur le jeu : **4 510 observations**. Les noms de fonctions ne sont pas résolus dans ce premier export, produit sans activation de symboles. Les racines ntdll ne doivent pas être confondues avec les feuilles consommant le CPU.

Les feuilles de module les plus observées incluent ntkrnlmp.exe (1 365), OgreMain_x64.dll (1 072), nvwgf2um.dll (497), D3D11.dll (282) et RenderSystem_Direct3D11_x64.dll (242). Ces nombres portent sur les observations de piles disponibles de ce pilote **en pause** ; aucun coût exclusif de toute la physique/IA/du rendu, aucune comparaison de gain et aucune attribution du worker actif inconnu n'en découlent.

Les fichiers xperf trace-stats.txt, processes.txt, trace-span.txt et kenshi-stacks.txt sont conservés localement. Le dernier est du HTML malgré son suffixe. Les métadonnées système restent dans runtime/etw, ignoré par Git ; les rapports publics de projet n'énumèrent pas les autres processus.

## Capture Heng et incident de caméra

Le lancement manuel runtime/etw/KenshiProbeHeng_8e95c2f721f3 s'est arrêté sur Camera moved during measurement lors de la précondition initiale : **aucune mutation du monde, aucun start WPR**, source/copie/snapshot/préférences conformes. Ce n'était pas un refus de privilège.

Les lectures SDK donnaient mPos=[1,1], mPosAbs=[1280,720], Edge scrolling=true ; la caméra pouvait bouger même en pause. Elles ne déterminent pas à elles seules la position physique du pointeur. La vue avait dérivé de la référence historique vers environ [48352,930,-14493]. Un clic de recentrage via Computer Use et une restauration ordinaire n'ont pas corrigé le résultat lu après chargement. Le panneau RE_Kenshi General était visible lors de la capture de la fenêtre de ce PID ; il a été laissé ouvert. Aucun terminal ni dialogue UAC n'a été piloté par l'UI.

Le verrou existant se libérait au début de load_save ; les frames du chargement pouvaient donc de nouveau lire le bord. **0.8.2 ajoute load_save(name,lock_edge=true)** pour KenshiProbe_test ou un snapshot effectivement possédé par le plugin. La préférence d'origine est conservée et le défilement désactivé avant la demande de chargement, à travers celui-ci. **set_camera_free(...,release_edge=true)** restitue explicitement la valeur capturée sans imposer un nouveau chargement ; lock et release simultanés sont refusés. Les valeurs par défaut anciennes conservent leur comportement, les sauvegardes non jetables ne peuvent pas demander ce verrou. L'implémentation réutilise OptionsHolder du SDK, sans nouvel offset ni hook.

La DLL reste **v100 x64, 17 outils et trois sondes**, cible AI::update4Frame inchangée. Il s'agit d'une correction de contrôle des essais, sans optimisation du moteur. Le cache TLS séparant identité et CPU par appel reste une amélioration à faire.

## Validation effective

**289 pytest passent en 4,51 s**, avec sessions WPR nommées, refus d'une session étrangère, annulation de secours après échec, démarrage ambigu et paramètres caméra protégés. Compilation/liaison v100 x64 réussies.

runtime/camera-082-smoke.json confirme réellement un chargement protégé, la vue canonique **[50759.15625,997.840759,-14012.985352]**, deux lectures espacées de deux secondes stables, pause et horloge identiques, puis libération ramenant Edge scrolling=true et ownership=false. La caméra peut de nouveau répondre aux entrées au bord après restitution de la préférence ; la stabilité doit être vérifiée dans la fenêtre de mesure, pas présumée indéfiniment après release.

Archive de déploiement **crashes/20261028T073800679070Z-deployment-082**, ancienne DLL0.8.1/config/préférences/journal. WPR global idle vérifié, jeu37552 et watchdogs1484/2012 relus avant arrêt, seuls processus du projet touchés. Jeu actuel **31368**, watchdog wrapper **17928**/enfant **1060** lors de runtime/camera-082-final.json, identités à relire avant action. Copie en pause, mode normal, contrôle temporaire relâché, watchdog frais sans erreur, échéance/activation **1793225700** inchangées. **702/702/738 fichiers** source/copie/ancien snapshot conformes.

Les préférences de settings.cfg sont conformes au préalable, mais **les octets du fichier ne sont pas identiques** : autosaveindex et continue ont avancé de 0/autosave0 à 1/autosave1, cohérent avec une sauvegarde automatique du moteur. Les différences brutes sont conservées dans le contrôle final ; aucun autre champ n'est écarté de la comparaison, aucune sauvegarde automatique n'est supprimée et le fichier n'a pas été écrasé pour masquer cet écart. Ne pas annoncer « préférences et métadonnées byte-identiques » pour ce contrôle.

## Scénario prêt et action restante

Le script tests/live_etw_heng.py est autonome : chemins résolus depuis son emplacement, aucun PYTHONPATH ou Set-Location requis. Il vérifie l'absence de session WPR étrangère, le PID/chemin/création et les sauvegardes protégées, charge la copie avec verrou pour définir une **référence canonique fraîche**, prépare Heng, stabilise x1, capture dix secondes, vérifie caméra/vitesse/PID, arrête sa seule instance, relit les rôles et restaure la copie sous verrou puis libère celui-ci. La fenêtre OS englobe démarrage/arrêt WPR et requêtes ; elle n'est pas identique aux bornes ETL. Les journaux gardent erreurs et cleanup_required, jamais un succès supposé.

Un lancement automatique via Start-Process -VerbRunAs a renvoyé **« L'opération a été annulée par l'utilisateur »**. Aucun processus de capture n'a démarré ; runtime/etw-admin-launch.json porte launched=false. Le message PowerShell « launched » avec PID vide provenait d'une erreur non terminante et ne prouve rien. Aucun nouveau prompt UAC ne sera relancé automatiquement sans nouvelle autorisation. Mes processus restent sans privilège de profilage système ; la réussite du pilote utilisateur ne leur confère pas de jeton administrateur.

Commande demandée dans **PowerShell administrateur**, sans autre préparation :

```powershell
& 'E:\ChatGPT_Project\Kenshi_Catlon\.venv\Scripts\python.exe' 'E:\ChatGPT_Project\Kenshi_Catlon\tests\live_etw_heng.py'
```

Les résultats du nouveau job devront être vérifiés avant de considérer la capture réussie. Symboles propres de la DLL0.8.2 préservés sous runtime/symbols/0.8.2 pour l'analyse future, avec empreintes ; aucun binaire du jeu ou source SDK n'est copié dans Git.

## Réanalyse hors jeu reproductible

Les modules etw_analysis.py et export_etw.py valident le contrôleur et l’empreinte de la trace avant export. Ils conservent les commandes, leurs résultats, les empreintes des sorties et de xperf dans un nouveau dossier analysis horodaté, puis vérifient à nouveau la trace. Ils refusent les pertes, un PID ambigu ou qui ne couvre pas toute la trace, ainsi qu’une attribution par TID ambiguë ou de durée de vie partielle. Une analyse explicitement partielle conserve son statut incomplet ; elle ne valide pas le scénario x1. Les symboles restent désactivés.

Depuis la racine du projet, pour le pilote déjà disponible :

```powershell
& .\.venv\Scripts\python.exe mcp-server\export_etw.py runtime\etw\KenshiProbePilot_fd5e0c834b34\controller.json --top-threads 0
```

Ce parcours ne lance ni n’arrête une session WPR. Son exécution réelle sous Python -I, avec chemins absolus, a réussi : runtime/etw/KenshiProbePilot_fd5e0c834b34/analysis-20261028T083738995195Z/analysis.json, completed=true, 4 510 observations. Les exports PID/processus et les compteurs de pertes concordent avec le relevé initial. Les 27 nouveaux tests couvrent aussi les changements de trace en cours de traitement et les erreurs d’export ; ils ne remplacent pas une capture réelle à Heng.

L’utilisateur a indiqué ne pas pouvoir intervenir si une fenêtre apparaît. La capture administrateur est donc différée ; aucune action manuelle n’est attendue maintenant et aucun nouveau lancement UAC n’est tenté. Le travail hors jeu continue. Le battement watchdog lu vers08:41UTC est frais pour le PID31368, sans erreur de publication. L’inventaire des processus accessible depuis le sandbox est partiel ; il ne constitue pas une preuve d’absence globale de sessions Windows.
