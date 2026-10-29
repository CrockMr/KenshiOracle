# Trajet du thread principal vers la boucle Ogre

Les quatre anciennes piles retenues passent par le même appel depuis `KingOfRenderThread::startup`. Le diagnostic statique retrouve le trajet **startup → thunk → Renderer::go → Ogre::Root::startRendering**. Il s’agit d’un chemin lié aux observations conservées, **pas d’une attribution CPU**. Aucun nouveau hook ni changement du plugin : 0.8.17, 17 outils MCP, trois frontières profilées.

## Provenance et méthode bornée

Les piles viennent du PID historique33936/création Unix1793179386.9010031, thread principal40448/création FILETIME134376529869010045. Leur contrôleur est `runtime/stacks/heng-20261028T101436907912Z/controller.json`, SHA256 `c51fb4edf498683df6de65a484f07d0dbac7197e521ddfc41c56989c1976cc06`. L’analyse SDK/piles vérifiée est `runtime/stacks-085-analysis.json`, SHA256 `ce3ac761e7bb761a2bf03fed1768fc45047c805f51ca3e15cdd46253121385f3`. Ce ne sont pas de nouvelles piles du processus courant.

Les sources EXE/KenshiLib.dll/table RVA sont revérifiées par empreintes, sans utiliser les commentaires des headers ni un delta global. Dans chaque pile, l’adresse de retour d’origine demeure inchangée : le diagnostic examine seulement l’encodage de l’appel qui la précède. Le décodage DUMPBIN démarre à l’entrée de la région observée ; aucune limite globale de fonction n’est inventée à partir de cette région, de fragments voisins ou du symbole précédent.

Les quatre observations retrouvent le retour RVA0x86c5ad et son appel direct à0x86c5a8. Celui-ci atteint un thunk relatif à0xf97a, puis l’entrée0x812890, alias **exact** du slot SDK5876 `Renderer::go()`. L’en-tête fourni Renderer.h déclare cette méthode et son champ `Ogre::Root* root` à l’offset0x68. Le court relais charge ce champ et transmet la main via l’import statique **OgreMain_x64.dll / Root::startRendering**. Les adresses sont uniquement des preuves dans le build identifié ; elles ne deviennent pas un binding à copier dans le plugin.

Preuves successives : `runtime/startup-callsite-analysis.json`, `runtime/startup-call-target-analysis.json`, puis **`runtime/renderer-go-static-route.json`**, SHA256 **25bf2145d23bd608721be0a0d72137764b0a4e0506dbbd6504a5329bfc2984d9**. Chacune conserve ses parents, sources, commandes de décodage bornées et empreintes. Les scripts lisent les sources et observations locales ; aucun code cible n’est exécuté. Le premier helper de résolution a demandé le mauvais groupe d’imports du parser et a échoué avant écriture du rapport ; groupe EXE corrigé, résultat final conservé. Aucun relevé de jeu répété pour cette correction.

Les noms d’imports sont des **déclarations statiques** : le diagnostic n’authentifie pas la cible actuelle de l’IAT Ogre dans un processus. Les cadres Ogre/D3D11 présents dans les piles sont compatibles avec ce trajet, mais quatre observations ne constituent ni distribution pondérée ni preuve du goulot GPU. Le CPU des threads entiers reste celui des fenêtres OS distinctes ; aucune durée de cette boucle n’est mesurée ici.

## Ce qu’apporte REA, et sa limite observée

REA/Ghidra12.1.4 a été ouvert sur l’EXE SHA256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. Une requête ciblée de dossier `startup` a déclenché l’import et l’analyse par défaut ; le journal observé progressait dans le RTTI. Budget de démarrage déjà configuré : **900 s**. Le client MCP a interrompu l’appel à **450 s**, avant ce budget. C’est un **délai client**, pas un nouveau provider_timeout à330 s ni un résultat de décompilation.

L’erreur est conservée dans `runtime/rea-startup-dossier-result.json`. L’export `runtime/rea-startup-evidence.json` contient **zéro record de dossier** : ne pas présenter l’analyse comme achevée ni conclure à une absence de code. `close_binary` a réussi et la session finale est **fermée, cleanup_pending=false**. Aucun nouveau lancement identique, aucun paramètre de sécurité modifié. Preuve de tentative : `runtime/rea-startup-attempt.json`, SHA256 **cc3bbbb261527725500a003a981393969b77ad7de7e6d1b4f4d226a204a6f435**.

Pour une future question nécessitant réellement Ghidra, il faut d’abord un délai hôte `mcp_servers.rea.tool_timeout_sec` dépassant900 s avec marge de requête/nettoyage, ou le transport CLI documenté qui évite cette limite client. Cela ne garantit pas que l’analyse terminera dans900 s. Aucun changement de configuration ou intervention utilisateur n’est exigé pour les conclusions statiques déjà obtenues.

## Conséquences pour le profilage

La [candidate King::mainloop](king-mainloop-candidate.md) met seulement TIME à jour ; elle est écartée sans instrumentation. `Renderer::go` et `startup` rejoignent une boucle durable : leurs appels ne constituent pas une frontière utile de frame terminée sans démonstration supplémentaire. L’entrée [Renderer::update mesurée](renderer-measurements.md) ne couvre donc pas par son seul nom toute cette boucle. `Renderer::renderOneFrame` est marqué sans adresse dans le SDK : ne pas inventer son binding KenshiLib ni remplacer cette lacune par un RVA manuel.

Les prochaines améliorations doivent partir des mesures existantes : diagnostic reproductible distinguant temps mural des appels, CPU OS des threads et observations ponctuelles ; classement des questions encore ouvertes avant toute modification d’algorithme. Les sept recherches lentes false à coordonnées distinctes ne justifient pas un cache d’échecs ; l’objet BirdManager observé ne donne pas encore le CPU exclusif de son calcul. Les campagnes lourdes déjà terminées ne sont pas rejouées sans hypothèse nouvelle.

Après ces lectures statiques, l’audit séparé `runtime/renderer-0817-diagnostic-final.json` retrouve le même PID38472, copie en pause à404,3333339691162 h, caméra normale/contrôle relâché, **702/702/738 fichiers protégés conformes**, settings identique, watchdog sans erreur, 17 outils et sept rôles SDK. Aucun nouveau build : les721 tests restent ceux de la production0.8.17 inchangée. Raw désassemblages et données du jeu restent uniquement sous runtime ignoré Git.
