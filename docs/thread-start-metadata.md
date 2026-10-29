# Métadonnées de démarrage des threads Windows

Une capture Windows limitée aux métadonnées de threads fonctionne sur le jeu en pause avec **PROCESS_QUERY_INFORMATION**, sans session administrateur. Elle retrouve **126 threads** et leurs procédures de démarrage. Les workers prioritaires **37324 et 39984** ont la même adresse dans **MSVCR100.dll + 0x21dbc**, également utilisée par le worker précédemment observé en navigation 37196. Cette adresse partagée ne distingue pas leurs fonctions. Aucune pile CPU ni attribution exclusive de système n'est obtenue.

Plugin **0.7.5, v100 x64, 17 outils et trois hooks inchangés**. Le code nouveau est un lecteur Windows Python, séparé du plugin. Aucun enregistrement de sauvegarde, déploiement, changement de vitesse ou de réglage du jeu pendant cette étape.

## Méthode vérifiée

Les déclarations sont lues dans les en-têtes installés Windows SDK **10.0.26100.0**, ProcessSnapshot.h et TlHelp32.h. Le helper x64 vérifie notamment PSS_THREAD_ENTRY de 120 octets, Win32StartAddress à l'offset 88 et MODULEENTRY32W de 1080 octets. Il utilise uniquement **PSS_CAPTURE_THREADS=0x80**, avec indicateurs de contexte à zéro ; aucun clone, contexte, espace mémoire ou contenu de pages n'est demandé. Microsoft distingue ces options dans [PSS_CAPTURE_FLAGS](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags).

La capture est parcourue avec [PssWalkSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalksnapshot). Le PID de chaque entrée est vérifié ; un contexte non nul serait refusé sans être déréférencé. Les champs réservés ne sont pas exploités. Les captures sont bornées à 4096 threads et 4096 modules. L'inventaire de modules utilise Toolhelp, en lecture seule ; les adresses sont rapprochées de plages demi-ouvertes, sans lecture de code ou attribution par proximité. Voir [CreateToolhelp32Snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot) et [MODULEENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-moduleentry32w).

Le marqueur, le snapshot local et le handle de requête sont libérés dans finally, avec codes de retour conservés. Le descripteur PSS vit dans le helper : sa libération utilise **GetCurrentProcess**, même si la cible est distante, comme précisé par [PssFreeSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot). Aucun appel SuspendThread ou écriture dans le processus n'est effectué. Cela ne prétend pas décrire tous les mécanismes internes de synchronisation de Windows.

## Validation progressive

1. `runtime/thread-metadata-self.json` : helper local avec un thread connu. Sa création correspond exactement à GetThreadTimes ; nombre de handles avant/après **198/198**. Capture et libérations réussies.
2. `runtime/thread-metadata-remote-helper.json` : second helper du projet, chemin/commande/parenté/création vérifiés. Thread connu retrouvé ; libérations réussies. Identité relue avant demande d'arrêt normal par entrée standard, sortie **0**, expiration de sécurité de trente secondes. Aucun processus extérieur arrêté.
3. `runtime/thread-metadata-game.json` : lecture unique du jeu identifié et en pause, capture et libérations réussies. La lecture du jeton de la session confirme **administrateur=false**. L'horloge et la caméra sont inchangées avant/après.

Les retours de libération du marqueur et du snapshot sont **0**, la fermeture du handle de processus vaut **true**, dans les trois preuves. Cette collecte de métadonnées ne lance pas ETW et ne modifie pas la politique qui a refusé son pilote.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
# Requiert la preuve locale déjà enregistrée, puis valide un helper distant.
& ./.venv/Scripts/python.exe tests/live_thread_metadata.py
# Refuse sans validation distante réussie ; exige la copie restaurée en pause.
& ./.venv/Scripts/python.exe tests/live_thread_metadata.py --game
& ./.venv/Scripts/python.exe mcp-server/analyze_thread_metadata.py runtime/thread-metadata-game.json runtime/scenarios/pause-cpu-20261028T041739Z.json
```

Les chemins de preuves sont locaux et explicites. Le premier test local a été réalisé avant ces commandes et ses réponses complètes sont conservées ; les wrappers refusent de supposer sa réussite si le fichier manque ou est invalide.

## Jointure avec le CPU déjà mesuré

Capture de métadonnées : SHA-256 **f48063ab218367c504eb93d9f37f510f5a2dfa1e448c48b6e4f0b7cabb69b868**. Source CPU : pause-cpu-20261028T041739Z.json, SHA-256 **200b5b7da382777c5b50cfc8c175c4df079300c5ee0e041baf9ab85a32a5ad40**. Le rapport `runtime/thread-metadata-analysis.json` conserve les deux empreintes.

La jointure exige PID, exécutable et création du processus cohérents, puis **TID et création FILETIME exactement identiques** pour chaque thread. Sur les 120 threads des intervalles CPU, 119 sont retrouvés dans les métadonnées plus tardives. Le TID 34868 reste sans correspondance ; son delta CPU mesuré était zéro dans les trois intervalles, sans en déduire une absence définitive d'exécution. Les autres entrées plus tardives ne reçoivent aucun CPU rétroactif inventé.

CPU entier des threads retrouvés, **groupés par module de leur procédure de démarrage** :

| Module de démarrage | Threads joints | Pause avant | x1 | Pause après |
| --- | ---: | ---: | ---: | ---: |
| Kenshi_x64.exe | 5 | 0,825062 | 0,842938 | 0,822489 |
| OgreMain_x64.dll | 16 | 0,750960 | 0,662089 | 0,717670 |
| nvwgf2umx.dll | 55 | 0,179527 | 0,154794 | 0,175209 |
| MSVCR100.dll | 25 | 0,076395 | 0,676649 | 0,072685 |

Les nombres sont des processeurs logiques moyens sur les anciens intervalles CPU. **Ce n'est pas une mesure du CPU exécuté à l'intérieur de chaque module.** Une routine de démarrage peut appeler d'autres bibliothèques ou être une entrée d'exécution partagée. Le module de démarrage n'est pas la pile active, comme le distingue la définition de [Win32StartAddress dans PSS_THREAD_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_thread_entry).

Les deux workers qui augmentent à x1 restent donc non attribués malgré leur origine MSVCR100 commune. Le TID 32072 a une procédure dans nvwgf2umx.dll ; cela situe son origine sans établir tous ses travaux. Les groupes et leurs résidus ne sont pas renormalisés. Les limites du contraste temporel et des populations restent celles de pause-cpu-measurements.md.

## État et suite

**193 tests Python passent en 4,07 s.** Ils couvrent bornes de modules, plages ambiguës, identités de threads réutilisées, identité de processus contradictoire et résidus signés. Les captures locales/distantes réelles valident séparément l'ABI et les libérations.

Le jeu reste dans le PID 19892 avec même chemin/création, disponible en pause et à la même heure de jeu ; vue normale, Edge scrolling=true, aucun combat suivi actif. Preuve fraîche `runtime/thread-metadata-final.json`. Aucun helper de test ne reste actif. Aucun fichier du jeu n'est écrit par ces outils ; le dernier contrôle complet des **702/702 fichiers source/copie et 738 du snapshot** reste `runtime/scenarios/pause-cpu-075-final.json`, relié par empreinte, sans nouvelle validation identique inutile. L'échéance de supervision reste **28 octobre 22 h 15 UTC**.

Le pilote ETW administrateur est toujours en attente ; ces métadonnées ne le remplacent pas. Les deux workers MSVCR100 exigent des piles ou une autre preuve de fonction avant un choix d'optimisation. Une éventuelle recherche de symboles de routines de démarrage devra conserver la distinction entre adresse exacte, wrapper et code actif ; aucun désassemblage ni nouvelle interception n'a été effectué ici.
