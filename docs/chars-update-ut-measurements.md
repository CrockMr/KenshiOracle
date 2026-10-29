# Attribution de charsUpdateUT — 0.8.5

GameWorld::charsUpdateUT est observée sur le thread principal partagé avec le service de rendu, pas sur le worker restant. Les 600 appels de la fenêtre finale x1 totalisent4,743702 ms murales inclusives. La fonction du worker restant n’est toujours pas identifiée ; cette mesure ne justifie pas une optimisation de charsUpdateUT.

## Une fonction sélectionnée, trois sondes maximum

La sonde sélectionnée remplace la fonction IA : charsUpdate, findPath et charsUpdateUT sont les trois sondes de systèmes. Les callbacks GameWorld/Renderer de service restent distincts. Le hook original de charsUpdateUT est typé void(GameWorld*), celui d’IA void(AI*,float) ; un foncteur partagé collecte les mesures sans détourner ces prototypes. La déclaration non virtuelle a été vérifiée dans GameWorld.h et résolue avec GetRealAddress, comme les autres fonctions du SDK. Aucun offset ou algorithme du moteur modifié.

KENSHI_PROBE_FUNCTION_TARGET sélectionne periodicUpdate, update4Frame ou charsUpdateUT ; une valeur non vide est prioritaire sur l’ancien KENSHI_PROBE_AI_TARGET. ping.function_target_source expose la source. Une valeur inconnue/trop longue désactive cette seule sonde, sans fallback. KENSHI_PROBE_FUNCTION_THREAD_CPU prend de même priorité sur AI_THREAD_CPU si non vide ;1 active les lectures par appel,0 les désactive. La campagne présente emploie charsUpdateUT et CPU0, avec identité FILETIME en TLS conservée.

ping.function_profiling/profiled_function/function_probe_target_valid et les champs function_thread_* décrivent la sélection. systems.profiled_function et les séries function_ms/calls/nested_entries_skipped sont génériques. Les alias IA ne sont présents que pour une vraie cible IA ; en mode charsUpdateUT ils sont null et ai_profiling=false. charsUpdateUT_mean_ms et sa série reprennent alors la mesure correspondante. Il reste17 outils MCP.

function_diagnostics.py refuse les fonctions/alias contradictoires, les anciennes sondes coexistantes et les séries mal libellées. analyze_profiled_function.py garde les identités exactes pour les joints CPU, rôles SDK et rôles principal/rendu observés. L’analyse des anciennes mesures IA reste lisible ; runtime/ai-081-compatibility-085.json confirme les valeurs historiques identiques, avec seulement trois nouveaux champs génériques ajoutés, sans écraser l’ancien rapport.

## Campagne Heng pause/x1/pause

Brut **runtime/scenarios/pause-cpu-20261028T092535Z.json**, SHA-256 **4644cef7fe6fa2f129062d8b538fa5d0e45f7265cf9fbb15418c606a57be4f13**, completed=true, PID33936. Rapport dérivé runtime/chars-085-analysis.json. Vrai MCP stdio ; aucune suite pytest pendant les phases. La caméra est protégée à travers les chargements et les mesures ; les trois phases évoluent séquentiellement sans remettre la ville au même état initial.

| Phase | CPU processus, processeurs logiques moyens | Progression de l’horloge | Population observée | Appels dans les600 frames finales |
|---|---:|---:|---:|---:|
| Pause initiale |1,802266|0 h|403|0|
| x1 |2,468963|+0,186541 h|413–434|600|
| Pause finale |1,709298|0 h|430|0|

Les intervalles OS durent respectivement20,391/20,359/20,266 s. Les résidus CPU signés sont0/+0,015625/+0,031250 s ; une identité manque à la borne finale dans chacune des deux premières phases, aucune dans la troisième. Les inventaires et la variation de population restent conservés, pas assimilés à des environnements identiques.

À x1, frames18128..18727 :600 appels extérieurs, **0,007906 ms inclusif/frame**, maximum0,051500 ms, aucune entrée imbriquée/troncature de threads. Tous portent **TID40448/création134376529869010045**, joint exactement à l’OS et aux rôles game_thread/renderer_service_thread observés aux bornes. Le thread entier consomme16,078125 s CPU dans son intervalle OS, soit0,789731 processeur logique avec le dénominateur processus. Aucun CPU par appel n’est déclaré mesuré : valeurs null et600 indisponibles.

La fenêtre de fonction porte sur600 frames, celle de l’OS sur environ20 s ; leurs coûts ne sont pas divisés pour annoncer une couverture exclusive. Les appels terminés sont comptés dans leur bucket de fin ; une période vide n’exclut pas d’autres travaux. Les fenêtres finales de pause ne contiennent aucun appel de cette fonction, alors que le thread principal continue à consommer environ0,79 processeur logique.

Le rôle SDK world_ai_non_render est34252/création134376529988183642, avec0,055171/0,363783/0,048573 processeur logique entre les phases. Le worker **10688/création134376529988181936** reste hors rôles vérifiés et hors de cette fonction :0,001533/0,355340/0,002313 logique. Le rôle physique21516 représente0,050653 logique à x1 ; les deux alias SDK physique/interface sont dédupliqués. Aucun coût exclusif de simulation ou gain du moteur n’est déduit de ces contrastes.

## Validation et état laissé

**312 pytest passent en4,48 s** ; les tests natifs v100 de sélection, buckets et profondeur après exception passent. Compilation/liaison v100 x64 réussies. runtime/chars-085-smoke.json confirme trois sondes, vrai nom, mode CPU0, aucun hook IA parallèle,17 outils et copie en pause ; stats3600 valides, charge utile compacte48341 octets sous la borne64 Kio.

Archive crashes/20261028T092303542614Z-deployment-085, ancienne DLL0.8.4/config/settings/journal ; runtime/deploy-085.json. WPR inactif, sauvegardes et identités jeu35336/watchdogs27108/38500 vérifiés avant arrêt des seuls processus du projet. Symboles propres085 conservés sous runtime/symbols/0.8.5, sans binaire de jeu ajouté à Git.

runtime/chars-085-final.json confirme jeu33936 en pause/mode normal, contrôle caméra relâché/Edge=true, **702/702/738 fichiers** source/copie/ancien snapshot conformes et settings byte-identique au préalable de ce déploiement. Gardes false, watchdog frais/zéro erreur/autoload réussi,17 outils/sept rôles SDK, WPR inactif et aucun contrôleur de campagne actif. Helpers13460/14864 à ce relevé, identités à relire avant arrêt. Échéance config/activation1793225700 inchangée.

La caméra peut répondre de nouveau au bord après restitution de préférence. L’ancien snapshot n’a pas retrouvé sa propriété en mémoire et current_save reste un nom interne collant. La charge extérieure n’est pas quantifiée, le panneau RE_Kenshi n’a pas été revérifié visuellement. Ces mesures ne comparent pas causalement des versions.

La capture ETW administrateur Heng reste différée sans intervention demandée. Il faut maintenant examiner les moyens de relever des piles utilisateur cohérentes sans privilège système, ou une autre entrée SDK étayée, avant de multiplier des sondes choisies par leur nom. Aucun nouveau système supposé de RenderTimeBackthread ne doit être inventé ; toute nouvelle sonde remplace la sélection courante.
