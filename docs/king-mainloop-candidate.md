# KingOfRenderThread::mainloop — candidate écartée sans hook

La méthode SDK `KingOfRenderThread::mainloop(float)` **ne fournit pas la frontière de travail recherchée** : l’entrée vérifiée met simplement le champ `TIME` à jour puis retourne immédiatement. Aucun hook, appel moteur, redémarrage ou nouvelle version du plugin n’est ajouté pour cette piste. La **0.8.17 reste installée**, avec 17 outils MCP et trois frontières profilées.

## Pourquoi cette candidate

Les [piles utilisateur historiques](user-stack-capture-measurements.md) passent par Ogre et `KingOfRenderThread::startup`. Ce dernier est un ancêtre durable ; son nom n’établit ni coût CPU exclusif ni fréquence par frame. Après les mesures MainLoop et Renderer, la déclaration finie `mainloop(float)` méritait une vérification avant instrumentation. Elle n’apparaissait dans aucune des quatre piles retenues ; cette absence limitée ne prouvait pas qu’elle n’était jamais appelée.

Le SDK fourni déclare `void KingOfRenderThread::mainloop(float time)` dans KingOfRenderThread.h, ligne 28. Son export et import `?mainloop@KingOfRenderThread@@QEAAXM@Z` sont présents dans KenshiLib.lib. Header SHA256 **e93b1b2f0ecdc2f6e51c5e1dc3cd0be88de49589c22ad7d407b220af6ba0397d**, bibliothèque **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Le champ float `TIME` est déclaré à l’offset zéro dans ce même en-tête. `runtime/king-loop-sdk-0818.json` est un nom de prévalidation de candidate : **aucune 0.8.18 n’a été produite**.

## Vérification liée au build et au processus

La carte SDK existante est reconstruite avec les trois sources exactes et leurs empreintes : KenshiLib.dll, Steam_1.0.65.br et EXE SHA256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. L’entrée est retrouvée par le **symbole et son slot**, sans utiliser le RVA du commentaire ni appliquer de delta global. Aucune borne de fonction n’est inventée à partir du symbole suivant ou de l’absence de région unwind.

Dans le **PID38472/création native FILETIME134376841722811092**, chemin/commande/création contrôlés, les stubs chargés et les **7622 valeurs de slots** sont vérifiés avant et après. Cinq octets de l’entrée King, non instrumentée par le projet, sont lus via un handle query/read et correspondent exactement au fichier. DUMPBIN v100 décode seulement cette plage bornée : écriture de l’argument float dans l’objet, puis retour. Les handles sont fermés, le processus reste le même et aucun objet n’est modifié. Le premier DUMPBIN a refusé une plage sans préfixe hexadécimal ; la syntaxe corrigée est conservée dans la preuve, sans nouvelle capture de jeu.

Preuve **`runtime/king-candidate-live-entry.json`**, SHA256 **49b5aeea530eb3be18717145f6aa187cc95bad471bb8ad87a090f9d6c48136ca**. Elle conserve identités, sources, vérifications des slots avant/après, lecture comparée, commandes, empreintes des sorties et nettoyage. Les octets/désassemblages restent **uniquement sous runtime, ignoré Git** ; aucun code du jeu n’est ajouté au dépôt.

Une seconde plage Renderer a été lue à titre de contexte. **Ses 39 octets sont un fragment**, avec branche sortante : ils ne constituent pas un corps complet ni une preuve statique que tout Renderer est court. La mesure réelle de l’original Renderer reste celle du [rapport 0.8.17](renderer-measurements.md). Seule l’entrée King a été comparée au code vivant ; Renderer possède déjà le detour de service du projet.

## Décision et limites

Écarter cette candidate évite une instrumentation peu utile et une campagne identique sans hypothèse pertinente. Cette vérification ne mesure **ni fréquence d’appel ni CPU de King**, ne démontre pas de gain et ne résout pas tout le coût du thread principal. Le nom mainloop ne garantit pas qu’il englobe une frame.

REA a été consulté : serveur disponible, session initialement fermée et propre. Son décodage natif ciblé nécessitant l’import Ghidra complet, ce court diagnostic utilise le parser lié aux empreintes et DUMPBIN local. L’utilisateur autorise REA au besoin ; une **question distincte** a porté sur le dossier de `startup`. Le client a interrompu la requête après450 s, avant le budget Ghidra900 s ; aucun dossier obtenu, export zéro record et session fermée/nettoyée. Le [trajet indépendant vers Ogre](main-thread-loop-route.md) a néanmoins été résolu par lectures bornées, sans nouveau hook.

La déclaration `Renderer::renderOneFrame` du SDK est marquée sans adresse ; ne pas inventer son binding KenshiLib pour obtenir une sonde. Les pistes suivantes doivent respecter les API réellement fournies et la limite de trois systèmes. Le jeu reste en pause pendant le diagnostic statique, sauvegardes protégées et échéance 22 h 15 UTC inchangée.
