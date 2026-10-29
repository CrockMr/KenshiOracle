# MedicalSystem::periodicUpdate — 0.8.9

À Heng, cette fonction rejoint le rôle SDK **world_ai_non_render**. Les 600 frames finales à x1 contiennent **5 660 appels, 18,333490 ms murales inclusives**, soit **0,030556 ms par frame**. Aucun appel n’apparaît dans les 600 frames finales de chaque pause. Ce relevé ne mesure pas son CPU exclusif et ne démontre aucun gain du moteur.

## Sonde et validation

`KENSHI_PROBE_FUNCTION_TARGET=medicalPeriodicUpdate` remplace ZoneManager dans l’unique emplacement sélectionnable. Les trois sondes restent charsUpdate, findPath et MedicalSystem ; 17 outils MCP sont exposés. MedicalSystem.h déclare `void _NV_periodicUpdate()` : original et wrapper reçoivent un `MedicalSystem*`, sans float. GetRealAddress résout le symbole non virtuel du SDK ; AddHook transmet les arguments originaux sans modifier le comportement. Aucun RVA numérique ni prototype AI détourné.

Ping annonce `medical_periodic_update_profiling`, les statistiques génériques nomment MedicalSystem::periodicUpdate et les alias IA/charsUpdateUT/physique/Zone sont inactifs. Les temps CPU par appel sont désactivés ; le cache TLS conserve indépendamment la création FILETIME du thread. CPU indisponible signifie null, sans zéro mesuré. La sonde ne couvre pas automatiquement toutes les fonctions médicales ni d’éventuelles autres implémentations virtuelles.

Compilation et liaison **v100 x64** réussies, essais natifs du sélecteur/buckets/profondeur réussis et **454 tests pytest passent en 21,85 s**. Le recalcul des données ZoneManager 0.8.8 reste strictement identique : `runtime/zone-088-compatibility-089.json`. Le vrai MCP vérifie version/cible/capacités et copie en pause dans `runtime/medical-089-smoke.json`. Aucune nouvelle modification des headers SDK depuis 0.8.8.

## Campagne pause, x1, pause

Brut : `runtime/scenarios/pause-cpu-20261028T122800Z.json`, completed=true, SHA-256 **b2cd8b30ffdc65b450e75cc92e08edf029810fc0b7c90c83d3495cfbd3dcb495**. Analyse : `runtime/medical-089-analysis.json`. Jeu PID **39204**, création Unix **1793190312.050583**, chemin et commande vérifiés. Caméra contrôlée, échauffement puis trois phases ; aucun pytest ni build pendant leurs mesures.

| Phase | Frames finales | Appels | Total mural inclusif | Moyenne par frame | Max appel |
|---|---|---:|---:|---:|---:|
| Pause avant |17629..18228|0|0 ms|0 ms|0 ms|
| x1 |20808..21407|5660|18,333490 ms|0,030556 ms|0,093100 ms|
| Pause après |23876..24475|0|0 ms|0 ms|0 ms|

Les 5 660 appels appartiennent tous au **TID 13132 / création FILETIME 134376639240828501**, joint par identité exacte aux compteurs Windows et au rôle SDK non rendu. Zéro entrée imbriquée omise, zéro troncature de threads ; 5 660 appels sans CPU disponible, conformément au mode sélectionné. La moyenne par frame ne doit pas être présentée comme une moyenne par appel.

| Phase OS | Durée processus | CPU processus | Moyenne en processeurs logiques | Progression simulée | Population aux bornes |
|---|---:|---:|---:|---:|---:|
| Pause avant |20,328 s|34,453125 s|1,694861|0 h|404→404|
| x1 |20,438 s|46,437500 s|2,272116|+0,187174 h|414→445|
| Pause après |20,359 s|34,562500 s|1,697652|0 h|445→445|

À x1, le thread entier 13132 consomme **4,671875 s CPU** dans l’intervalle natif de threads de **20,422 s**, soit environ **0,228767 processeur logique**. Ce n’est pas le CPU exclusif de MedicalSystem. Les fenêtres fonctionnelles de 600 frames et les fenêtres OS ont des bornes distinctes : aucun ratio de couverture n’est calculé entre elles. Les résidus signés processus/threads sont −0,015625 /−0,140625 /−0,031250 s. Deux identités manquent à la seconde borne en première pause, une manque à la première borne à x1 ; aucune omission en pause finale. Aucun résidu n’est attribué à une fonction.

Les contextes élargis de 3 600 frames contiennent respectivement **1 /29 860 /5 133 appels**. Le dernier chevauche la phase active ; il ne démontre pas une activité médicale pendant la fenêtre finale en pause. Réponses compactes observées : 48 754 /52 568 /48 942 octets, sous le plafond indépendant de 64 Kio dans ces cas.

## Restitution, reproduction et limites

`runtime/medical-089-final.json` confirme copie en pause, multiplicateur 0, heure **404,3333339691162 h** identique à la référence, caméra normale et contrôle temporaire relâché. Les **702/702/738 fichiers** source/copie/snapshot sont conformes ; settings.cfg est byte-identique au préalable du déploiement, gardes false. Watchdog frais sans erreur, WPR inactif, aucun contrôleur de scénario restant. Le défilement de bord est restitué à true ; la caméra peut donc se déplacer après les essais.

Déploiement archivé : `crashes/20261028T122457509551Z-deployment-089`. Symboles propres dans `runtime/symbols/0.8.9` : DLL SHA **1eb5451accfe89043ef2299b7687b1b6f2f4da1f36515e966749f6959ee69525**, PDB SHA **bedee83488762fb14ad6c5c120b8369611660194c1f72247ef5be1e6e7023b1c**. Les preuves anciennes sont conservées. Aucun fichier du jeu, SDK, sauvegarde ou code décompilé dans le checkpoint des sources propres.

L’analyse hors jeu est reproductible avec `analyze_profiled_function.py` sur le brut ci-dessus, vers un nouveau fichier de sortie. Répéter un scénario vivant exige une session autorisée, la copie distincte et ses gardes ; ne pas prolonger l’échéance du 28 octobre à 22 h 15 UTC. Aucune action administrateur attendue.

Les petits coûts muraux observés de MedicalSystem et de ZoneManager ne suffisent pas à expliquer tout le worker ni à les exclure de pics futurs. La prochaine étape utile est un diagnostic plus large et borné des threads actifs, puis des conditions lourdes à x5 avec fenêtres adaptées au nombre réel de frames. Le thread principal/rendu reste proche de 0,8 processeur logique dans ces pauses ; cela n’attribue pas automatiquement son CPU au rendu. La population, le streaming et la charge extérieure varient, l’état mémoire des PNJ n’est pas déterminisé ; aucune comparaison entre versions ne constitue une mesure de gain.
