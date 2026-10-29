# Sélection de sonde IA et AI::update4Frame — 0.8.1

**AI::update4Frame est lui aussi observé sur le rôle SDK world_ai_non_render, et ne précise pas le worker restant dans cet essai.** Les 31 010 appels de la fenêtre finale x1 représentent **0,032379 ms inclusif cumulé par frame de service**, soit 19,427675 ms sur les 600 frames. Leur très faible durée motive un profilage moins intrusif ; aucune optimisation du moteur n'est annoncée.

La version **0.8.1**, compilée/liée v100 x64 et validée par MCP réel, conserve **17 outils et trois sondes de systèmes**. La cible IA est maintenant sélectionnable **au démarrage du jeu**, sans reconstruction pour passer entre deux fonctions.

## Sélection et contrat explicite

KENSHI_PROBE_AI_TARGET accepte exactement periodicUpdate (défaut si absent) ou update4Frame. La variable doit être présente dans l'environnement du **watchdog qui lance le jeu** ; la modifier dans un serveur MCP déjà connecté ne change pas la DLL en cours. Un choix inconnu ou trop long désactive la seule sonde IA et signale ai_probe_target_valid=false, sans installer une autre cible à sa place. Aucun changement de cible pendant une mesure.

AI/AI.h déclare void AI::_NV_periodicUpdate(float) et void AI::_NV_update4Frame(float). Le code résout le wrapper non virtuel sélectionné, et exécute **un seul AddHook IA** ; charsUpdate et findPath restent les deux autres sondes. L'original conserve son type AI*,float et ses arguments. La sonde physique et charsUpdateUT restent absentes. Les compteurs, garde d'imbrication TLS et bucket d'excédents de 0.8.0 sont conservés.

- ping.ai_profiled_function : nom sélectionné, AI::periodicUpdate ou AI::update4Frame ; nom nul si sélection invalide. Consulter ai_profiling pour l'installation effective.
- ai_periodic_update_profiling et ai_update4_frame_profiling distinguent l'unique sonde active ; ai_probe_target_valid distingue validation du choix et réussite du hook.
- get_frame_stats.systems.ai_profiled_function : objet de métriques générique avec function et scope explicites.
- L'ancien systems.ai_periodicUpdate est un alias identique **uniquement lorsque periodicUpdate est la cible active** ; il vaut null pour update4Frame. Ne jamais sommer l'alias et l'objet générique.
- Les séries ai_function_ms/calls/nested_entries_skipped décrivent la cible sélectionnée. Les anciennes séries ai_periodicUpdate_* valent null pour update4Frame ; les anciennes séries physiques restent null.

Les analyseurs refusent un alias contradictoire, une fonction inconnue, une fonction différente selon les phases ou une sélection initiale incompatible. analyze_ai_function.py est l'entrée canonique ; analyze_ai_periodic.py reste un import/CLI compatible. Sans --output, le nouveau CLI crée un fichier .ai-analysis.json dérivé du nom brut, sans écraser par défaut le rapport historique 0.8.0.

La sélection native périodique/défaut et les valeurs invalides sont testées nativement, avec l'historique réel 0.8.0 réanalysé sous le nouveau validateur. Le lancement 0.8.1 réel de cette campagne utilise **update4Frame** ; le mode périodique 0.8.1 n'a pas fait l'objet d'un nouveau scénario complet, déjà testé comme corps sous 0.8.0.

## Preuves

- Archive crashes/20261028T063509742045Z-deployment-081, motif deployment_0.8.1, ancienne DLL 0.8.0/config/préférences/journal ; runtime/deploy-081.json. Jeu 19296 et watchdogs 14244/20820 vérifiés avant arrêt, seuls processus du projet touchés.
- Nouveau jeu **37552**, smoke runtime/ai-081-smoke.json : fonction explicite, flags corrects, ancien objet et séries périodiques null, trois sondes et sept rôles SDK.
- Brut : **runtime/scenarios/pause-cpu-20261028T063714Z.json**, SHA-256 **2659b952175e624ffdf4458924ea735424fba26e53e458ab5129dd0ea00ff87b**.
- Analyse canonique : **runtime/ai-081-analysis.json** ; ancienne fonction périodique réanalysée dans runtime/ai-080-compatibility-081.json sans modifier ses chiffres.
- État final : **runtime/ai-081-final.json**.

## Relevé pause/x1/pause à Heng

Le contrôleur restaure KenshiProbe_test, prépare Heng et stabilise le streaming ; trois secondes de stabilisation et vingt secondes OS demandées par phase. Caméra/vitesse/horloge/PID contrôlés pendant la mesure, inventaires aux bornes et identités SDK en pause encadrant l'ensemble. Aucun pytest pendant l'intervalle.

| Phase | CPU processus / temps réel | Processeurs logiques moyens | Population | Appels de la cible dans les 600 frames finales |
| --- | --- | ---: | --- | ---: |
| Pause avant | 37,562500 s / 20,297 s | 1,850643 | 393 stable | 0 |
| x1 | 49,531250 s / 20,344 s | 2,434686 | 407..446 | 31 010 |
| Pause après | 36,093750 s / 20,297 s | 1,778280 | 446 stable | 0 |

Horloge +0,186497 h à x1, immobile dans les pauses. Résidus CPU signés +0,078125 / +0,437500 / +0,031250 s conservés ; phase finale : un thread absent à chaque borne, explicitement exclu. Aucun gain comparé aux versions précédentes : population, processus, caches et conditions diffèrent.

La fenêtre x1 finale, frames **13166..13765**, contient uniquement le thread **37692 / création FILETIME 134376429227663373**, identité du rôle world_ai_non_render et des compteurs OS. **19,427675 ms murales inclusives**, moyenne **0,032379 ms/frame**, maximum d'appel **0,034000 ms** ; aucun débordement ni entrée imbriquée observés. Moyenne arithmétique par appel environ **0,6265 µs** ; ce n'est pas un quantile de latence.

CPU d'appels disponible pour tous : **31,250 ms user, 0 ms noyau**, cumul supérieur aux 19,428 ms murales. Courtes durées et CPU quantifié : valeurs conservées sans clamp ni couverture exclusive. Deux lectures CPU par appel sont d'un ordre de grandeur comparable à cette moyenne d'appel (lecture startup ~0,2335 µs), mais cette calibration ne mesure pas le coût complet du hook. Le résultat justifie de réduire les lectures de profilage ; il ne donne pas un pourcentage précis de perturbation.

Le **thread entier**, sur l'intervalle OS x1 de 20,344 s, consomme **6,390625 s CPU = 0,314128 processeur logique**. Les fenêtres OS et fonction (~4,517 s) sont distinctes ; aucun ratio de couverture n'est calculé. Le thread passe par 0,046189 / 0,314128 / 0,053117 logique entre phases.

Le worker **26476 / création 134376429227661575** reste sans fonction attribuée : **0,002309 / 0,322577 / 0,000770 logique**. Il n'est pas retrouvé parmi les lignes de cette cible capturées. Le service principal 37156 reste à ~0,737486 / 0,741926 / 0,761350 logique. Un nom de méthode ne permet pas de déduire sa cadence par acteur ; aucun pointeur AI ni identité d'acteur n'est enregistré.

## Validation et état laissé

**251 pytest passent en 4,00 s**, avec sélection/générique/historique, alias unique, libellés contradictoires et phases mélangées. Tests natifs v100 x64 du sélecteur, compteur borné, TID réutilisé et restauration de profondeur après exception réussis. Getters SDK et cible non virtuelle liés et observés en jeu. Le serveur MCP reste à 17 outils.

Jeu **37552**, watchdog wrapper **2012**/enfant **1484** au contrôle final : revérifier chemin/commande/création avant action. Copie rechargée en pause, vue normale de référence, Edge scrolling=true, combat suivi inactif et contrôle temporaire relâché. **702/702/738 fichiers** source/copie/ancien snapshot conformes ; settings.cfg byte-identique au préalable, gardes false. Watchdog frais sans erreur, autoload réussi, échéance/activation **1793225700** inchangées, contrôleur terminé. Panneau RE_Kenshi non vérifié visuellement, charge externe non quantifiée.

## Suite fondée sur ces mesures

Le mode CPU désactivé existe déjà, mais sous 0.8.1 il prive aussi les appels de leur création FILETIME (la requête d'identité dépend des lectures CPU). L'amélioration prioritaire est de **séparer identité et mesure CPU** : lire/cache par TLS la création du thread une seule fois, puis permettre les durées murales et la jointure OS sans deux GetThreadTimes par petit appel. TLS lie le cache à la durée de vie réelle du thread ; un échec doit rester explicitement inconnu, sans inventer un TID/création valide. CPU désactivé reste null/indisponible, jamais zéro mesuré. Ne pas annoncer de gain sans comparaison contrôlée.

Le worker restant demande ensuite un autre point d'entrée. **GameWorld::charsUpdateUT()** est déclaré dans GameWorld.h et avait déjà été accroché dans les anciennes versions, avec une moyenne agrégée mais sans identité de thread. Une reprise de ce point d'entrée **en remplacement** de la cible IA, avec métadonnées génériques exactes et signature GameWorld* sans float, pourrait tester ce worker. Ne pas réutiliser le prototype AI*,float ni ajouter un quatrième hook ; ne pas publier ces mesures sous un nom de méthode IA. Aucun cast vers RenderTimeBackthread dont la définition manque. ETW administrateur reste en attente : aucune nouvelle tentative ou question sans changement utilisateur.
