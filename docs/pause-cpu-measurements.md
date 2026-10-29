# CPU en pause et à x1 dans une même ville

La séquence native **pause / x1 / pause** près de Heng consomme respectivement **1,835 ; 2,353 ; 1,792 processeur logique moyen**. Le CPU ne disparaît donc pas avec la pause. Le thread partagé par GameWorld et Renderer reste proche de 0,8 dans les trois phases ; deux autres threads consomment nettement plus à x1. Leurs fonctions restent inconnues : ce relevé ne transforme pas le CPU résiduel en coût de rendu, ni la différence en coût exclusif de simulation.

Plugin **0.7.5, v100 x64, 17 outils MCP et trois hooks de systèmes inchangés**. Aucun redéploiement, arrêt de processus ou réglage vidéo modifié. La propriété du snapshot géré est conservée.

## Preuves et reproduction

- Brut : `runtime/scenarios/pause-cpu-20261028T041739Z.json`, SHA-256 **200b5b7da382777c5b50cfc8c175c4df079300c5ee0e041baf9ab85a32a5ad40**.
- Analyse : `runtime/pause-cpu-analysis.json`, avec empreinte du brut et rapprochement des threads par TID et création FILETIME.
- Contrôle final : `runtime/scenarios/pause-cpu-075-final.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_pause_cpu.py
& ./.venv/Scripts/python.exe mcp-server/analyze_pause_cpu.py runtime/scenarios/pause-cpu-20261028T041739Z.json
```

Le collecteur utilise une vraie session MCP stdio pour toutes les commandes. Il recharge KenshiProbe_test, prépare Heng, laisse dix secondes à x1 puis attend trois secondes de disponibilité stable. La même scène et la même vue sont conservées entre les trois phases, sans rechargement intermédiaire. Chaque activation est suivie de trois secondes de stabilisation, puis d'un relevé CPU demandé de vingt secondes, avec scène toutes les 0,5 seconde. L'activation et cette stabilisation sont hors intervalle CPU. Les inventaires de 500 lignes encadrent chaque phase ; aucune suite de tests n'est exécutée pendant ces intervalles.

## Résultats

| Phase | Secondes CPU processus | Durée CPU englobante réelle | Processeurs logiques moyens | Progression de l'horloge | Population pendant les observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pause avant | 37,531250 | 20,453 s | 1,835000 | 0 h | 398–398 |
| Simulation x1 | 47,968750 | 20,390 s | 2,352563 | 0,186874 h | 417–429 |
| Pause après | 36,593750 | 20,422 s | 1,791879 | 0 h | 429–429 |

La moyenne des deux taux en pause représente **77,08 %** du taux à x1. La différence descriptive x1 moins moyenne des pauses est **+0,539123 processeur logique** ; la seconde pause est inférieure à la première de 0,043121. Il n'y a qu'un intervalle par phase, à des moments successifs et avec une population différente. Aucun intervalle de confiance, coût marginal de personnage, gain d'optimisation ou décomposition causale de ce delta n'est établi.

Les 120 identités de threads sont appariées dans chaque intervalle, sans omission, et communes aux trois phases avec la même création. Les lectures OS de borne prennent 63 à 79 ms. Les résidus processus moins somme des threads sont **−0,093750 ; −0,156250 ; −0,015625 seconde CPU**, conservés sans normalisation. Les compteurs sont quantifiés et les relevés de threads sont séquentiels. Les durées entre scènes et celles des compteurs CPU diffèrent légèrement ; les deux sont conservées.

## Threads à investiguer

Taux de CPU entier de chaque thread, divisés par l'intervalle processus de sa phase :

| TID | Rôle observé | Pause avant | x1 | Pause après |
| --- | --- | ---: | ---: | ---: |
| 35716 | GameWorld et service Renderer | 0,785337 | 0,809987 | 0,798771 |
| 37324 | Fonction non attribuée | 0,005348 | 0,317251 | 0,000765 |
| 39984 | Fonction non attribuée | 0,045837 | 0,294262 | 0,052027 |
| 32072 | Fonction non attribuée | 0,173416 | 0,150962 | 0,171384 |

Le premier est compté une seule fois malgré ses deux rôles. Les TID sont liés ici à leurs dates de création, pas considérés comme des identités persistantes après redémarrage. Les deux workers 37324 et 39984 sont des cibles prioritaires pour une attribution par piles ; les nommer physique, IA ou navigation sur ce seul contraste serait prématuré. La charge des autres applications reste non fixée et non quantifiée.

Aucun appel lent retenu ne termine dans les bornes CPU des trois phases ; les contextes de 3600 frames ne sont pas tronqués dans cette capture. Cela ne fournit pas d'identité de worker de navigation pour ces phases. L'absence de ce rôle dans les groupes ne signifie pas CPU de navigation nul.

Les fenêtres finales de **600 frames**, distinctes des intervalles CPU, contiennent respectivement **0 / 55 / 0 appels findPath terminés**, avec intervalles moyens de frame **6,534 / 7,154 / 6,769 ms**. Elles sont à l'intérieur des bornes de scènes de leurs phases, mais terminent quelques frames après les heartbeats de fin CPU ; le rapport l'indique explicitement. Ces chiffres ne résument pas les vingt secondes entières et ne suffisent pas à identifier le travail des autres threads.

## Qualité de scène et limites

Pause, multiplicateur et caméra passent les contrôles à chaque observation. L'horloge est figée dans les deux pauses et progresse à x1. Les inventaires sont complets aux bornes des trois phases. Dans chaque pause, libellés, multiplicités et positions sont identiques avant/après. L'inventaire à x1 évolue de 417 à 429 et les horloges diffèrent : l'analyse refuse une différence exhaustive de roster dans cette phase non atomique. La population a aussi évolué durant la stabilisation précédant x1 ; le protocole conserve ce fait.

La pause ne garantit pas l'arrêt de tous les travaux du moteur ou des modules chargés. Inversement, un thread dont le CPU augmente à x1 peut exécuter plusieurs types de travail. La séquence est utile pour prioriser des observations, pas pour choisir déjà une réécriture de système. Les temps des hooks restent inclusifs et la simulation, le rendu, les attentes et le streaming ne sont pas isolés ici.

## Validation et état laissé

**182 tests Python passent en 4,06 s** : gardes de phase, horloges, compteurs invalides, changement de processus, contrastes signés et rapprochement de threads sans inventer de zéro pour un thread absent. Les données natives attestent l'exécution ; les tests synthétiques vérifient le traitement.

La copie initiale est rechargée en pause, caméra normale de référence, Edge scrolling=true, aucun combat suivi actif ni contrôle temporaire. Source/copie et préférences sont conservées ; le contrôle final vérifie aussi le snapshot séparé. Watchdog et borne finale restent inchangés à **28 octobre 22 h 15 UTC**.

Le pilote de piles CPU administrateur est toujours en attente. Une piste distincte, seulement consultée dans la documentation officielle, est la métadonnée de procédure de démarrage exposée par [PSS_THREAD_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_thread_entry). Une procédure de démarrage n'est pas la pile actuellement exécutée. Les [indicateurs PSS](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags) distinguent inventaire de threads, contexte et copie mémoire ; aucune capture PSS, de contexte ou de clone n'a été exécutée ici. Vérifier utilité et droits avant toute implémentation ; ne pas présenter cette piste comme une trace CPU ou une attribution déjà obtenue.

Suivi distinct : thread-start-metadata.md décrit ensuite une capture PSS limitée aux métadonnées, validée sur helpers puis réalisée sur le jeu en pause. Les deux workers partagent une entrée MSVCR100 ; leur fonction n'est pas résolue. Cette lecture ultérieure ne fait pas partie des intervalles CPU ci-dessus et ne les transforme pas en profil par module exécuté.
