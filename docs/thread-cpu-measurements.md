# Attribution du CPU aux threads — 28 octobre 2026

La campagne native de dix PNJ à Mongrel consomme **2,304 processeurs logiques en moyenne** sur 45,094 secondes. Le thread partagé par GameWorld et le service Renderer représente 34,33 % du CPU du processus ; un worker observé dans les appels de navigation, 7,34 % ; les autres threads, 58,35 %. Ce relevé indique où poursuivre le diagnostic. Il ne mesure aucun gain d'optimisation et ne permet pas encore de nommer les fonctions dominantes des autres threads.

Le plugin reste **0.7.5, v100 x64**, avec les trois hooks de systèmes existants. Aucun hook, arrêt de jeu ou déploiement supplémentaire pour cette campagne. Toutes les commandes de scénario passent par une vraie session MCP stdio ; les compteurs OS sont lus séparément par le contrôleur Python.

## Preuves et reproduction

- Capture brute locale : `runtime/scenarios/battle-20261028T025346Z.json`, SHA-256 `653b2130e9504c8ab900d682bc5f3352269da6461ca26f848c1a05981ddff589`.
- Rapport : `runtime/thread-cpu-analysis.json` ; descriptions de threads : `runtime/thread-descriptions-20261028T025346Z.json`.
- Vérification finale : `runtime/scenarios/thread-cpu-campaign-075-final.json`.

Depuis la racine du projet :

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tests/live_battle.py 16863-gamedata.base --faction Bloodraiders --opponent-template 1227-gamedata.base --opponent-faction 'Mercenary Guild' --town Mongrel --focus --interval .25 --seconds 45 --pairs 5 --mcp --thread-cpu
& ./.venv/Scripts/python.exe mcp-server/analyze_thread_cpu.py runtime/scenarios/battle-20261028T025346Z.json --output runtime/thread-cpu-analysis.json
```

La première commande refait un essai et restaure la copie en pause ; la seconde réanalyse seulement le brut indiqué. La génération des acteurs n'est pas ensemencée, des renforts urbains interviennent et la population évolue de 141 à 218. Cette recette reproduit le protocole, sans garantir un combat identique. La comparaison entre campagnes ou vitesses exige un état initial contrôlé, notamment le garde de pose décrit dans scene-snapshot-measurements.md.

## Résultat de l'intervalle englobant

CPU total du processus : **103,875 secondes CPU** en 45,094 secondes réelles. Les parts suivantes utilisent ce même dénominateur ; elles ne sont pas renormalisées.

| Groupe exclusif de comptage | Secondes CPU | Processeurs logiques moyens | Part du CPU du processus |
| --- | ---: | ---: | ---: |
| Thread GameWorld et Renderer, TID 35716 | 35,656250 | 0,790709 | 34,3261 % |
| Worker observé en navigation, TID 37196 | 7,625000 | 0,169091 | 7,3406 % |
| Autres threads identifiés | 60,609375 | 1,344067 | 58,3484 % |

Le thread commun est compté une seule fois. Son CPU comprend tout le travail exécuté sur ce thread, rendu compris. Le CPU du worker de navigation comprend également tout son travail : **7,34 % n'est pas la part exclusive de findPath**, et d'autres workers de navigation peuvent rester non identifiés.

Parmi les threads sans rôle établi, les TID 39984, 37324 et 32072 consomment respectivement 10,500000, 8,328125 et 7,031250 secondes CPU. Une lecture ultérieure des descriptions Windows sur les douze threads dominants n'a donné que des chaînes vides. Aucun nom de système, notamment physique ou graphisme, n'est attribué à ces threads sans piles ou symboles probants.

## Méthode et limites

`WindowsThreadSampler` demande seulement le droit de requête limitée, vérifie l'appartenance au PID et lit les dates de création et compteurs CPU avec GetThreadTimes. Les dates FILETIME restent des chaînes décimales, pour préserver leurs bits en JSON. Un TID n'est rapproché entre bornes que si sa date de création correspond. Les handles sont refermés immédiatement, même après une erreur. Le champ de sortie d'un thread vivant n'est pas interprété : Windows le documente comme indéfini. Voir [GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes) et [GetProcessIdOfThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessidofthread).

Les bornes recensent **120 identités appariées** ; trois threads absents à la seconde borne sont explicitement exclus, sans inventer leur CPU. Les lectures séquentielles prennent environ **94 ms puis 63 ms**. Les compteurs sont quantifiés et les bornes processus/threads ne sont pas simultanées : la somme des threads est 103,890625 s, soit un résidu signé processus moins threads de **−0,015625 s**. Ce résidu reste visible ; il n'est pas ramené artificiellement à zéro. L'intervalle englobe lectures MCP et attentes, sans alignement exact sur une fenêtre de frames.

Les rôles viennent des heartbeats et des seuls appels lents retenus dont la frame de fin tombe dans l'intervalle observé. Le contexte de diagnostic de 3600 frames compte 66 appels au-dessus du seuil mais n'en conserve que 32 : `retention_truncated=true`. Il ne constitue pas un inventaire exhaustif des workers. La fenêtre finale de 600 frames reste séparée : 201 appels findPath terminés, 200 true et un false, maximum 126,208 ms ; moyenne d'intervalle de frame 9,050 ms, p99 12,902 ms. Ce dernier échantillon ne représente pas à lui seul les 45 secondes.

La lecture GetThreadDescription vérifie également l'identité et libère la mémoire retournée ; une description peut changer et ne prouve pas la fonction exécutée. Voir [GetThreadDescription](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreaddescription).

## Prochaine attribution : piles CPU Windows

Un pilote local de deux secondes, sur la copie en pause, est prêt dans `tests/live_etw_pilot.py` avec `tests/cpu-sampling.wprp`. Il utilise une instance WPR unique et n'arrête que cette instance. Les fournisseurs demandés concernent CPU, processus et modules à l'échelle du système ; l'analyse doit sélectionner l'identité et la durée de vie du jeu. Aucun fournisseur disque, réseau ou registre n'est demandé. Les traces restent locales dans runtime/etw, ignoré par Git. Voir les [options WPR](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options) et l'[analyse CPU](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis).

La tentative `runtime/etw/KenshiProbePilot_dd0f07a66fb0/controller.json` échoue au démarrage avec **0xc5585011**, « Failed to enable policy to profile system performance ». Le jeton courant n'est pas administrateur. Aucune trace n'a été créée, aucune session n'est restée active et le jeu est resté en pause. Il s'agit d'un refus de droits Windows ; aucune politique système n'a été modifiée. L'utilisateur a été sollicité pour exécuter le pilote dans un PowerShell administrateur, ou poursuivre sans capture système. Tant que cette intervention n'est pas confirmée, ne pas répéter le démarrage à l'identique.

Si le pilote réussit, vérifier le manifeste, l'arrêt de l'instance et la trace avant une capture de combat plus longue. Identifier alors les piles dominantes avec les symboles disponibles, sans supposer qu'un TID a une fonction exclusive. Choisir ensuite une amélioration fondée sur ces piles ; toute nouvelle cible native doit remplacer un hook existant pour garder le maximum de trois.

## Restauration et validation

Les **702 fichiers de KenshiProbe_validation et les 702 de KenshiProbe_test** correspondent chacun au manifeste témoin, après la campagne. PID 19892 et création inchangés, plugin 0.7.5, partie disponible en pause, caméra de référence et mode normal, Edge scrolling=1, aucun combat suivi actif et gardes de restauration des préférences à false. Le watchdog reste sain et borné au 28 octobre à 22 h 15 UTC ; aucune capture WPR n'est active au contrôle final.

**124 tests Python passent en 3,94 s**, dont identités réutilisées, compteurs régressifs, bornes manquantes, résidu signé, groupes sans double compte et fusion des contextes de navigation. Les tests synthétiques valident le traitement ; le brut natif ci-dessus atteste les observations du jeu.
