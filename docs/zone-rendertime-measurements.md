# ZoneManager::updateRendertimeThread — 0.8.8

La nouvelle sonde retrouve cette fonction sur le rôle SDK **world_ai_non_render**, avec l’identité Windows exacte du thread. Elle continue de fonctionner en pause. Dans les 600 frames finales à x1, les 600 appels totalisent **118,798499 ms murales inclusives**, soit **0,197997 ms par frame**, avec un maximum de 0,611200 ms par appel.

Cette fenêtre ne mesure pas le CPU exclusif de la fonction et ne couvre pas les mêmes bornes que le relevé OS de vingt secondes. Le résultat justifie de poursuivre la décomposition du worker ; il ne démontre ni un goulot unique ni un gain de performances.

## Implémentation et validation

`KENSHI_PROBE_FUNCTION_TARGET=zoneRendertimeThread` remplace l’unique fonction sélectionnée. Le prototype vient de ZoneManager.h : `void updateRendertimeThread(const Ogre::Vector3&)`. L’original est typé `void(ZoneManager*, const Ogre::Vector3&)` ; le wrapper transmet la référence originale, sans la convertir depuis le prototype AI*,float et sans modifier l’argument. La résolution utilise GetRealAddress et AddHook du SDK, sans RVA numérique copié dans le plugin.

Les trois sondes restent charsUpdate, findPath et cette sélection ; charsUpdateUT et l’IA ne sont pas accrochées simultanément. Le service existant au menu reste inchangé. Ping annonce `zone_rendertime_thread_profiling` ; les statistiques génériques portent le vrai nom. Les anciens alias IA/charsUpdateUT/physique sont null pour cette cible. CPU par appel désactivé, création FILETIME conservée par le cache TLS ; les valeurs CPU indisponibles sont null, pas des zéros mesurés.

**448 tests passent en 21,52 s**, tests natifs sélecteur/buckets/profondeur réussis et compilation v100 x64. Le rapport historique charsUpdateUT 0.8.5 est recalculé strictement à l’identique : `runtime/chars-085-compatibility-088.json`. Le smoke MCP réel `runtime/zone-088-smoke.json` confirme 17 outils, trois sondes, cible installée et copie en pause ; réponse n=3600 compactée à 50454 octets dans ce contrôle.

Le premier build avait rencontré C2011 : ParticlePool est défini deux fois à l’identique dans ZoneManager.h et combat/CombatClass.h. La préparation des dépendances compare les corps complets puis ajoute un garde commun. La définition et son organisation mémoire ne changent pas ; le SHA du corps normalisé reste **c42be0620bb080a7f13cee1247ef3ba9648e075d6329e289cb9de980f0ee7404** dans les deux fichiers. Idempotence vérifiée et empreintes avant/après dans `runtime/sdk-particlepool-088.json`. Les headers restent externes, ignorés Git. Le build suivant réussit.

## Heng : pause, x1, pause

Brut : `runtime/scenarios/pause-cpu-20261028T115207Z.json`, completed=true, SHA-256 **54d7e190659c7fe374cc998d5c6c70f747a502d28964748fea35a1a81c51272d**. Analyse : `runtime/zone-088-analysis.json`. Jeu PID **37288**, création Unix **1793188199.0609565**, exécutable vérifié. Les trois fenêtres fonctionnelles sont incluses dans leurs bornes de scène ; le contexte de 3600 frames reste distinct. Aucun pytest ou compilation pendant les phases.

| Phase | Frames de la fenêtre fonction | Appels | Total mural inclusif | Moyenne par frame | Max appel |
|---|---|---:|---:|---:|---:|
| Pause avant |11356..11955|600|97,751504 ms|0,162919 ms|0,604500 ms|
| x1 |14409..15008|600|118,798499 ms|0,197997 ms|0,611200 ms|
| Pause après |17616..18215|600|98,701697 ms|0,164503 ms|0,556100 ms|

Toutes ces entrées appartiennent au thread **34240 / création FILETIME 134376618121861931**, joint par TID et création aux compteurs OS et au rôle SDK world_ai_non_render. Zéro entrée imbriquée omise, zéro débordement du tableau de threads. Les 600 appels CPU sont indisponibles dans chaque fenêtre, conformément au mode choisi.

| Phase OS | Durée processus | CPU processus moyen, processeurs logiques | CPU du thread entier 34240 | Progression simulée |
|---|---:|---:|---:|---:|
| Pause avant |20,375 s|1,794479|1,000000 s|0 h|
| x1 |20,407 s|2,429467|6,750000 s|+0,187075 h|
| Pause après |20,344 s|1,751131|1,093750 s|0 h|

Les valeurs normalisées du thread entier données par la jointure utilisent ses bornes conservées : environ **0,049080 /0,330769 /0,053763 processeur logique**. Ces dénominateurs peuvent différer légèrement de la fenêtre du processus. Les résidus signés processus/threads sont **+0,25 /−0,109375 /0 s**, conservés sans clamp ; une identité n’a pas de seconde borne à x1, une autre pendant la pause finale. Aucun résidu n’est affecté à ZoneManager.

La population vaut 393 stable en première pause, 424→451 à x1, puis 451 stable. La caméra est contrôlée pendant les mesures ; le streaming et la simulation peuvent évoluer entre phases. Aucun ratio de couverture n’est calculé entre les 600 frames fonctionnelles et vingt secondes de CPU. Le fait que la fonction soit appelée aussi en pause confirme qu’un rôle nommé « IA » ne constitue pas du CPU exclusif d’IA ou de simulation.

Les contextes élargis de 3600 frames conservent des maxima de 1,185500/0,789700/0,611200 ms par appel. Ils peuvent chevaucher une autre phase : ce ne sont pas des maxima strictement bornés aux vingt secondes de chaque condition.

## Restitution et suite

Le contrôle `runtime/zone-088-final.json` confirme le retour de la copie à **404,3333339691162 h**, identique à sa référence initiale : pause, caméra normale, Edge=true et contrôle temporaire relâché. **702/702/738 fichiers** source/copie/snapshot conformes, settings.cfg identique au préalable du déploiement, gardes false. Watchdog frais, zéro erreur, autoload réussi, 17 outils/sept rôles SDK/trois sondes, WPR inactif, aucun contrôleur de scénario actif.

Archive : `crashes/20261028T114929424772Z-deployment-088`, après vérification fraîche des seuls processus du projet. Symboles propres sous `runtime/symbols/0.8.8` : DLL SHA **b0de947a7045a94029069da2b75fa310bac21676cfcc397428615728fc36f074**, PDB **41830ac1b55e76d2b76524dd2ea2b18fb1c53e0b7401a837007ff84cd552d3a2**. Aucune sauvegarde source ni fichier du jeu modifié par le déploiement.

Le candidat suivant est **MedicalSystem::_NV_periodicUpdate()**, déclaré dans MedicalSystem.h et déjà vu en pile active historique. Son prototype est MedicalSystem* sans float. Il peut remplacer l’unique fonction sélectionnée si la décomposition se poursuit, sans quatrième sonde. Le CPU exclusif BirdManager reste inconnu et sa classe n’est pas déclarée dans les headers locaux : ne pas créer une API directe à partir du RTTI. La charge extérieure n’est pas fixée, l’état PNJ complet n’est pas déterminisé et aucune comparaison entre versions n’établit un gain.
