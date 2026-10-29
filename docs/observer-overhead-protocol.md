# Protocole du coût de collecte après 0.8.19

**Protocole proposé, sans acquisition ni validation attestée par ce document.** Il vise l’effet des lectures MCP sur une partie en pause, avec la même DLL et les mêmes réglages. Les durées de service et de transport avaient évolué différemment après les [transferts JSON](json-ownership-measurements.md) ; le [mode agrégé 0.8.19](aggregate-statistics-measurements.md) réduit le volume transmis mais construit encore les statistiques complètes. Il faut donc mesurer séparément ces effets.

## Question et plan borné

Comparer trois conditions dans une même session de jeu, avec un serveur MCP et un contrôleur persistants :

| Condition | Lectures pendant le bloc | Fréquences à tester |
|---|---|---|
| M — acquisition minimale | Aucun getter ; mêmes réveils du timer que les autres conditions | Calendriers de 1 Hz et de 10 Hz, sans requête |
| F — réponse complète | `get_frame_stats(n=60, detail='full')` | 1 Hz et 10 Hz |
| A — agrégats | `get_frame_stats(n=60, detail='aggregates')` | 1 Hz et 10 Hz |

Un pilote comprend **six triades par fréquence**, chacune comportant M, F et A pendant **5 s par condition** : 36 blocs, soit 180 s de fenêtres prévues hors préparation. Les six ordres MFA, MAF, FMA, FAM, AMF et AFM sont utilisés une fois par fréquence. Le pilote utilise un ordre déterministe préenregistré : pour chaque permutation, la triade à 1 Hz précède celle à 10 Hz. Les fréquences sont intercalées et les positions équilibrées, mais le plan n'est pas randomisé ; un effet systématique de cet ordre reste possible. Les conclusions restent celles d’un pilote court.

Chaque bloc F/A prévoit respectivement 5 ou 50 lectures, espacées depuis une origine monotone fixe. Une seule requête à la fois ; aucune rafale de rattrapage. Enregistrer échéance prévue, départ/retour effectifs, échéances ratées et éventuel dépassement de la fin de bloc. Un bloc dont la fréquence n’est pas tenue reste une preuve de saturation, pas une observation à la fréquence nominale réussie. Le témoin M conserve le coût du timer et de l’observation commune : ce n’est pas un jeu sans instrumentation.

Le contrôleur utilise explicitement `time.perf_counter` pour le calendrier, les latences, les bornes CPU processus/threads et les bornes CPU du contrôleur. Son implémentation et sa résolution déclarées sont conservées. Chaque attente revérifie l'échéance, même après un réveil anticipé d'asyncio. Les anciens horodatages `time.monotonic` ne sont pas convertis ni mélangés à cette horloge.

## État initial et zones hors mesure

Conserver la DLL identifiée par SHA, version native, sélection Root, flags CPU et timing des commandes, settings, résolution, fenêtre/focus et cadence du watchdog. Utiliser seulement KenshiProbe_test, avec copie de référence protégée. Exiger pause effective, multiplicateur zéro, heure simulée identique, monde prêt, caméra stable et absence de bataille suivie. Vérifier les identités PID/exécutable/création ; un redémarrage invalide la continuité du pilote. Les variations d’inventaire restent enregistrées et les blocs concernés sont signalés, même en pause.

Préchauffer la session et l’historique avant mesure. Le plan exécuté conserve un warmup de **1 s d'attente neutre sans commandes** avant chaque bloc, puis les lectures communes de scène et de rôles. Cette pause ne constitue pas un préchauffage propre à chaque condition ; une rémanence du bloc précédent reste possible. Les lectures d’identité, de scène et de rôles sont identiques à chaque bloc et restent hors de sa fenêtre CPU. Aucune liste de personnages, capture, compilation ou autre scénario pendant les blocs. Garder les réponses en mémoire ; écrire les fichiers et calculer les tailles JSON après la fenêtre pour ne pas ajouter ce travail au régime observé.

Le contrôleur doit terminer les compteurs CPU OS **avant** les getters finaux de scène/statistiques. Le relevé initial se place après les contrôles et le warmup. Ces zones neutralisent les commandes auxiliaires dans la fenêtre CPU choisie ; elles ne rendent pas automatiquement identiques les bornes de scène, des buckets et du CPU.

## Mesures et bornes à conserver

- **Jeu :** CPU utilisateur/noyau du processus et des threads calculables aux deux endpoints OS ; identité Root jointe par TID et création, durées monotones, omissions et résidu signé. Les autres processus de la machine ne sont ni arrêtés ni reconfigurés pour améliorer le résultat.
- **Collecteur :** CPU du contrôleur et du serveur MCP, avec PID/exécutable/création et endpoints propres. Éviter un double compte des wrappers et signaler un enfant disparu. La baisse de travail du client ne doit pas être annoncée comme baisse du CPU du jeu.
- **Chaque lecture :** latence MCP murale, service natif, attente en file, n réellement reçu, bornes de frames, mode, erreur éventuelle et octets JSON compacts réencodés. Ces octets ne sont pas le trafic exact TCP/MCP. Les [périmètres du service](command-service-measurements.md) excluent notamment la sérialisation réseau ; leurs différences ne deviennent pas du CPU exclusif.
- **Callbacks :** récupérer les statistiques agrégées après le bloc, dans la limite de **3600 frames**, et enregistrer explicitement leur première/dernière frame. Calculer n à partir des compteurs observés et vérifier continuité, nouveaux buckets et bornes. Une fenêtre dépassant le budget ou nécessitant une réduction de n n’est pas une fenêtre entière comparable : conserver l’échec et raccourcir uniformément un nouveau plan, sans écraser l’essai. Le getter glissant peut décaler le début et la fin par rapport au CPU ; publier ces portées séparément, sans promettre une capture figée exactement sur cinq secondes.

Le mode agrégé rend ce dernier relevé réalisable avec un petit payload, mais ne fournit pas les lignes individuelles de toute la fenêtre. Les bornes ne permettent pas de reconstruire les durées de chaque frame ou de supprimer a posteriori toute frame touchée par un contrôle auxiliaire.

## Analyse et critères de conclusion

Fixer avant acquisition les comparaisons : A−F pour volume, latence et CPU ; F−M et A−M pour l’effet total de collecte à chaque fréquence. Garder les six triades séparées, puis publier les six différences appariées, leur médiane, étendue et nombre de signes concordants. Présenter aussi les témoins M dans l’ordre temporel afin de voir une dérive. Un changement de signe fréquent, une forte dérive ou des échéances ratées empêche de conclure à un effet stable ; conserver le résultat comme indéterminé ou comme limite de débit.

Une réduction des octets n’implique pas une baisse de CPU ou de latence. Les hypothèses CPU doivent pouvoir être contredites par les mesures correspondantes, sans sélectionner seulement les blocs favorables. Le pilote ne suffit pas à fixer une amélioration universelle ; une confirmation nécessite un plan déclaré et une nouvelle série indépendante. Ne pas généraliser de la pause au combat, ni interpréter l’intervalle de callback comme FPS affichés.

Les compteurs CPU sont quantifiés ; la [calibration du helper](root-cpu-measurements.md) ne garantit pas leur précision en jeu. Conserver zéros, deltas supérieurs à de courts temps muraux et résidus signés. Ne pas soustraire la durée Root, les services et le CPU OS pour fabriquer une attribution exclusive. Aucun résultat n’est fusionné avec les anciennes cohortes comme s’il provenait du même monde déterminisé.

## Faisabilité, restitution et autorisation

Les **17 outils et trois systèmes existants** suffisent : getters full/aggregates, pause, scène, heartbeat et identités sont disponibles ; les lecteurs CPU OS et les métadonnées de service existent. Le contrôleur `tests/live_observer_overhead.py` et l'analyseur `mcp-server/analyze_observer_overhead.py` sont préparés et testés pour l’ordre préenregistré, les répétitions, les échéances, le CPU du collecteur et le rejet des fenêtres non comparables. Aucun nouveau hook système ou outil MCP n’est requis par ce protocole.

Le nettoyage doit restituer la copie en pause, l’heure, la caméra et les contrôles, puis vérifier sauvegardes/settings/gardes et l’état du watchdog. Conserver le brut même sur échec. L'utilisateur a explicitement annulé l'ancienne fin du **28 octobre 2026 à 22 h 15 UTC / 23 h 15 Paris** et demandé de continuer. Le contrôleur accepte désormais `session_until: null` ; si une nouvelle échéance numérique est configurée, le budget et la réserve de clôture continuent de s'appliquer. Chaque campagne reste de durée bornée par son plan.

La référence de caméra est prise après verrouillage et stabilisation, puis contrôlée jusqu'à la lecture précédant la libération. Le pilote restitue le réglage Edge initial, pas les coordonnées de caméra antérieures au verrou : une dérive après libération reste possible. Les scènes avant verrou, sous verrou et après libération sont conservées séparément ; la vérification des sauvegardes s'exécute même si un contrôle de caméra échoue.
