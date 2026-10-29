# Identité de thread sans CPU par appel — 0.8.3

La jointure des appels IA avec les compteurs CPU Windows fonctionne désormais lorsque les deux lectures CPU par appel sont désactivées. La validation réelle à Heng conserve 30 450 appels attribués par TID/création. Elle ne mesure pas un gain de performances du jeu.

## Changement

ThreadIdentity.h contient un état POD initialisé à zéro, détenu en TLS par chaque thread natif. La création FILETIME est lue une seule fois lors du premier appel extérieur ; aucun handle ou pointeur de jeu n’est conservé. Un échec ou une création nulle reste inconnu pour cette durée de vie. Les nouveaux threads ont un nouveau TLS, même si Windows réutilise un TID. Les buckets gardent le couple TID/création ; une identité inconnue est sérialisée null et n’est jamais jointe par TID seul.

KENSHI_PROBE_AI_THREAD_CPU=1 conserve les deux relevés CPU par appel. Avec 0 ou omission, cpu_user_total_ms/cpu_kernel_total_ms sont null, cpu_available_calls=0 et les appels sont indisponibles pour le CPU par appel. L’identité et le temps mural continuent d’être collectés. ping.ai_thread_identity_mode et systems.ai_profiled_function.thread_identity_mode valent tls_creation_once ; ping.ai_thread_identity_independent_of_cpu vaut true. La sonde reste AI::update4Frame, aux côtés de charsUpdate et findPath ; 17 outils MCP, trois sondes et v100 x64.

L’omission de lock_edge dans la commande native set_camera_free utilise maintenant optionalFlag, comme le chemin MCP. L’omission et le rejet d’une chaîne ont aussi été vérifiés directement par le protocole natif.

## Preuve réelle

Brut : runtime/scenarios/ai-identity-20261028T085329926232Z.json. SHA-256 **d608b29f4288317b611640def64461b1bcd7fb84de47a3720c98bf6dbc60ef21**. completed=true, transport MCP stdio, PID33512/création1793177385.19762.

- Fenêtre finale : frames18396..18995, 600 frames, 30 450 appels extérieurs, aucune entrée imbriquée ni troncature de threads.
- Temps mural inclusif : 17,974197 ms cumulées, 0,029957 ms/frame ; maximum d’un appel0,045300 ms.
- TID37396/création134376509972635536, identité exacte dans les buckets, les deux relevés SDK world_ai_non_render et les compteurs OS. CPU d’appels null, aucun appel déclaré mesuré en CPU.
- Fenêtre OS englobante10,546 s : processus24,265625 s CPU, thread entier3,125 s CPU, soit0,296321 processeur logique avec ce dénominateur. Le relevé de threads a sa propre durée10,532 s ; ses valeurs normalisées ne sont donc pas numériquement identiques. Résidu CPU signé+0,0625 s, aucune omission aux bornes.
- Horloge entre scènes : +0,0965366 h sur10,533826 s, x1 observé à chaque lecture, caméra stable sous verrou.

Ces bornes diffèrent de la fenêtre finale des 600 frames. Aucun ratio de couverture exclusive ni coût de la fonction seule n’est calculé à partir du CPU du thread entier. Les chronométrages instrumentés et la charge extérieure ne sont pas étalonnés ; ces nombres ne démontrent aucun gain face à0.8.1/0.8.2. Le worker39360/création134376509972634106 représente aussi2,90625 s CPU dans cet intervalle, mais sa fonction n’est pas identifiée par cette sonde. Le thread17004 est plus consommateur ; aucun rôle exclusif n’est déduit de ce seul classement.

Le premier scénario runtime/scenarios/ai-identity-20261028T085158063881Z.json est conservé completed=false : sa requête de statistiques arrivait après la borne de scène, avec last_frame8567 contre scene_after8558. La restauration et les fichiers étaient conformes. Le contrôleur collecte désormais les statistiques avant la borne de scène et avant la fermeture du relevé OS ; le second essai valide cette correction. Aucun seuil n’a été relâché.

## Validation et état laissé

**291 pytest passent en4,44 s**, dont CPU désactivé avec identité connue/inconnue et refus d’un mode d’identité inconnu. Le test natif tests/test-thread-identity-v100.cmd passe avec huit threads Windows en deux générations, cache lu une seule fois, états TLS isolés et échecs explicitement inconnus. Compilation/liaison v100 x64 réussies. La première compilation dans le sandbox échouait C1902 ; la compilation hors sandbox autorisée a réussi. Un pytest bloqué dans le sandbox a été arrêté après vérification stricte du chemin/commande/création/dossier du processus9804 ; son wrapper était déjà sorti. La suite hors sandbox a ensuite terminé normalement.

Archive crashes/20261028T084930198333Z-deployment-083 : ancienne DLL0.8.2, journal, config et settings. WPR inactif et identités vérifiées avant arrêt des seuls processus du projet. Symboles propres0.8.2 et0.8.3 conservés dans runtime/symbols avec empreintes. Aucun fichier du jeu ou SDK ajouté à Git.

Le chargement automatique initial avait rendu la copie sans pause ; le premier précontrôle l’a refusée avant mutation. runtime/identity-083-startup.json conserve cette observation et la pause explicite immédiate suivante. La pause automatique avant disponibilité concerne encore les snapshots possédés, pas KenshiProbe_test : **à corriger lors de la prochaine modification native**, en conservant cette limite de la reprise automatique. Ne pas supposer que l’autoload laisse la copie en pause.

runtime/identity-083-final.json vérifie PID33512, copie en pause/mode normal, contrôle caméra relâché et Edge=true, 702/702/738 fichiers source/copie/snapshot conformes, settings identique au préalable de ce déploiement, gardes false, 17 outils, sept rôles SDK, watchdog sans erreur et WPR inactif. Helpers au dernier contrôle28140/33880 : revérifier leurs identités avant arrêt. Échéance/activation1793225700 inchangées.

La capture ETW à Heng reste différée, sans demande manuelle supplémentaire ni nouveau dialogue UAC. Le prochain point d’entrée possible pour le worker restant est GameWorld::charsUpdateUT(), déclaré par le SDK, avec son vrai prototype GameWorld* sans float, en remplacement de la seule sonde IA. Jamais de quatrième sonde ni de fonction supposée pour RenderTimeBackthread.
