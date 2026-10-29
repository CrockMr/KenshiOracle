<a id="combat-depuis-un-snapshot-à-horizon-simulé-commun"></a>

# Battle from a snapshot at a shared simulated horizon

Four runs **x1, x5, x5, x1** reloaded the same snapshot of two hostile NPCs at Mongrel without drawing new characters. Each starts with identical observed health, positions, clock and camera. Medical outcomes nevertheless differ, including at the same speed. Protocol measures a shared clock horizon; it does not yet provide identical combat work for marginal-cost or optimization-gain comparison.

Plugin **0.7.5 unchanged, v100 x64, 17 MCP tools, three system hooks**. Commands use a real MCP stdio session. No new hook, deployment, process stop, NPC creation or save-file write during this campaign.

<a id="preuves-et-reproduction"></a>

## Evidence and reproduction

- Raw: `runtime/scenarios/snapshot-horizon-20261028T033243Z.json`, SHA-256 **02c0864cfe331d5fcc02ce814ce9b20740ec610522c5aa878a36f10c0a986f42**.
- Summary: `runtime/snapshot-horizon-analysis.json`, raw fingerprint retained.
- Independent final check: `runtime/scenarios/snapshot-horizon-075-final.json`.
- Snapshot: `KenshiProbe_test_scene_20261028T022539600581Z`, 738-file manifest in creation evidence; visible reference from `snapshot-paused-settling-075.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_snapshot_horizon.py --snapshot-proof runtime/scenarios/snapshot-20261028T022539600581Z.json --baseline-proof runtime/scenarios/snapshot-paused-settling-075.json
& ./.venv/Scripts/python.exe tools/research/analyze_snapshot_horizon.py runtime/scenarios/snapshot-horizon-20261028T033243Z.json --output runtime/snapshot-horizon-analysis.json
```

First command requires current plugin still owns this snapshot. In-memory association does not survive restart; rejection must not be bypassed by a fresh draw presented as identical. Second command only reanalyzes files. Script now refuses to start in the final thirty minutes, checks margin before every run and reserves time to restore the initial copy in finally.

<a id="bornes-observées"></a>

## Observed bounds

Requested horizon **0,5 game hour**. Controller reads scene every 0,2 real second then pauses at crossing. Actual observed hours and overshoot retained, without artificially correcting duration.

| Order | Speed | Observed game hours | Real seconds, clock | Process CPU seconds | Starting population | Population during reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | x1 | 0,501579 | 55,015 | 123,281250 | 156 | 156–273 |
| 2 | x5 | 0,508999 | 11,535 | 23,390625 | 176 | 186–292 |
| 3 | x5 | 0,508982 | 11,507 | 24,437500 | 156 | 156–344 |
| 4 | x1 | 0,501266 | 55,104 | 119,187500 | 162 | 162–305 |

Overshoot reaches about **1,80 % of target horizon** at x5 versus 0,25–0,32 % at x1. Real seconds per game hour have medians 109,807 at x1 and 22,635 at x5, descriptive ratio about 4,85. Short interval includes activation, streaming and requests; not directly comparable to older stabilized town windows.

CPU measured over an enclosing interval slightly different from clock interval: 55,016; 11,547; 11,500; 55,094 real seconds. Cost includes rendering, all modules, commands, OS reads and paused endpoints. Signed process-minus-thread-sum residuals respectively **+0,031250; +0,093750; −0,093750; +0,015625 CPU second**; no thread excluded for missing identity in these four captures. Quantization/sequential reading remain visible. A navigation worker absent from one run's retained slow calls does not mean zero navigation CPU.

<a id="résultats-médicaux"></a>

## Medical outcomes

For actor `KenshiProbeFight_1_0`:

| Run | Final blood change | Final flesh-sum change | Unconscious at last read | First observed unconsciousness, real seconds | Simulated hours at that observation |
| --- | ---: | ---: | --- | ---: | ---: |
| x1, order 1 | −45,944 | −216,602 | yes | 18,796 | 0,170565 |
| x5, order 2 | −29,814 | −150,211 | no | none observed | — |
| x5, order 3 | −27,853 | −152,398 | yes | 3,515 | 0,146616 |
| x1, order 4 | −18,750 | −95,440 | yes | 16,563 | 0,148819 |

Times indicate first **observation**, not exact event time. Other actor loses respectively 15,471; 0; 0; 30,086 flesh sum. No cohort death observed at run end. Do not convert differences into hit counts or completed-task counts.

Second run contains nine reads with targets outside the cohort; others contain none. Absence in the sample does not establish isolated combat. Initial populations/trajectories vary; the two actors' health/pose do not cover all AI/equipment states or world characters. Same visible guards at x1 already yield very different damage. Nothing here causally attributes damage differences to speed.

Other applications' load neither fixed nor quantified. A four-second pytest suite notably ran during first x1 run. Measurements still cover game process alone, but this concurrency further limits cross-condition performance comparison. Two repetitions per speed remain descriptive.

<a id="correction-du-contrôleur-et-gardes"></a>

## Controller correction and guards

Pilot `snapshot-horizon-20261028T033127Z.json` stops before measurement because **set_game_speed itself removes pause**. Copy, snapshot and preferences restored/preserved; pilot remains evidence, not counted as completed run. Public `GameWorld::setGameSpeed(float,bool)` signature verified in GameWorld.h; unpausing effect natively observed, not assumed from boolean name.

Correction places clock and CPU start **before** this command, then verifies effective speed at every read. Four subsequent runs pass starting guards with zero medical, spatial or clock difference; no tolerance widened. Previous 1,897339-unit vertical rejection remains valid in other evidence: this campaign does not erase it. Controller also rejects duplicate names, nonfinite values, incomplete medical shapes, moved camera, lost actor or PID change.

**145 Python tests pass in 3,94 s.** Additional tests cover guards, incomplete-run exclusion, horizon overshoot, process identity and distinguishing the two clocks for medical observations.

<a id="état-laissé-et-prochaine-étape"></a>

## State left and next step

PID19892/creation time unchanged, initial copy reloaded, normal-mode reference camera, pause active, Edge scrolling=true and temporary control released. **702 KenshiProbe_validation files and 702 KenshiProbe_test files**, plus **738 snapshot files**, match manifests. settings.cfg byte-identical after campaign; restoration guards false. Healthy watchdog, zero publication errors, final boundary unchanged **28 October 22 h15 UTC**.

Next CPU-stack diagnostic remains conditional on the already requested administrator Windows pilot; no new trace appeared. In parallel, improve observation of environment/uncovered states, then define comparable scene/work criterion before engine optimization. Immediately repeating the quartet would not establish a cause. No optimization gain claimed.

Follow-up: environment-preflight-measurements.md subsequently confirms, without combat simulation, update-list population varying 172 to 147. Environment guard now added to controller for future runs; not part of the historical quartet here. Its replay on new raw data accepts first environment and rejects second. No historical result reclassified as a controlled comparison of the whole game world.
