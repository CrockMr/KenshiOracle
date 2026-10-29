<a id="rapport-de-mise-en-place--27-octobre-2026"></a>

# Setup report — 27 October 2026

<a id="état-actuel-les-sections-suivantes-conservent-lhistorique"></a>

## Current state (the following sections retain the history)

- **0.8.2 linked with v100 x64, installed/actual MCP; 262 pytest tests in 4,21s; 17 tools/three probes.** Scrolling lock during load_save restricted to the copy, explicit release; view/clock stable for two seconds in-game, then preference restored. Administrator WPR pilot actually valid (30,9MB,4510 Kenshi stack observations,zero losses), first Heng attempt rejected before mutation/capture because the camera moved. Corrected targeted capture ready, RunAs launch canceled by Windows, administrator retry requested.702/702/738 files compliant; preferences identical but autosaveindex/continue advanced, no byte-identity claim. See etw-camera-validation.md, runtime/camera-082-final.json, and local ETW validation. The following entries are historical.

- **0.8.1 linked with v100 x64, installed/actual MCP; 251 pytest tests in 4,00 s and native selector/bucket/nesting tests passed.** Single AI hook selected at startup, explicit metadata, and old periodic telemetry null in update4Frame mode. At Heng x1:31 010 calls,0,032379 ms inclusive/frame (600 frames), thread 37692 exactly joined to the non-render role, zero calls in final paused windows. Worker 26476 still unknown. Quantized CPU 31,25 ms exceeds19,428 ms wall time, no clamping/coverage; motivates an identity cache independent of per-call CPU reads. Old0.8.0 raw data reanalyzed without changing measurements. Archive deployment-081, 702/702/738 files compliant, copy reloaded paused, exact preferences, and healthy watchdog. See ai-target-selection-measurements.md and runtime/ai-081-final.json. The following entries are historical.

- **0.8.0 linked with v100 x64, installed/actual MCP; 241 pytest tests in 4,00 s and native bucket/post-exception nesting tests passed.** AI::_NV_periodicUpdate replaces the physics probe, still three probes/17 tools. At Heng x1:5 984 calls,0,701594 ms inclusive/frame over 600 frames, thread 18336 exactly joined to the non-render SDK role; zero calls in final paused windows. Call CPU 453,125 ms exceeds accumulated wall420,956 ms, quantization retained without exclusive coverage. Worker 19228 remains unknown. Archive deployment-080;702/702/738 files compliant, copy reloaded paused, exact preferences, and healthy watchdog. See ai-periodic-measurements.md and runtime/ai-080-final.json. The following entries are historical.

- **0.7.9 linked with v100 x64, installed/actual MCP; 230 pytest tests in 3,99 s; 17 tools/three probes.** ResourceLoader and NavMeshGenerator joined to OS CPU identities:0,078125 s /0 s measured over 20,375 s; SaveFileSystem threadID=0 remains unknown. Five unique SDK threads after physics deduplication,13,897 % of process CPU in this test, whole-thread costs. Remaining worker 19272 unidentified. New deduplicated-coverage/unknown tests; old 0.7.7 join compatible. Deployment archived,702/702/738 files compliant, copy reloaded paused, exact preferences, healthy watchdog. See sdk-thread-roles-measurements.md and runtime/sdk-079-final.json. The following entries are historical.

- **0.7.8 linked with v100 x64, installed and actual MCP; 227 pytest tests in 3,78 s; 17 tools/three probes.** Optional world_physics_interface read, physics alias confirmed in source and Heng (same TID/creation time), without an unnecessary new CPU interval. Exact compatibility of 0.7.7 recordings and unknown values at incomplete boundaries tested. Native thread_details omission default fixed and verified, wrong types rejected. Archive deployment-078, copy returned paused,702/702/738 files compliant, exact preferences, watchdog without error; runtime/sdk-078-final.json and sdk-thread-roles-measurements.md. The following entries are historical.

- **0.7.7 linked with v100 x64, installed/actual MCP; 222 pytest tests pass in 3,96 s; still 17 tools and three probes.** Optional paused SDK-role reads with TID/PID/creation time verified by Windows. Three roles linked to x1 CPU: world non-render0,271672 logical/11,40 % of process, navmesh0,004605, physics back-thread 0,046814. Whole-thread costs, not exclusive functions. Worker 16564 remains unattributed. Native pause/wrong-boolean guards observed; joins and aliases tested. Deployment archived, game25120, copy restored paused,702/702/738 files compliant, exact preferences; healthy watchdog/deadline unchanged. See sdk-thread-roles-measurements.md and runtime/sdk-077-final.json. The following entries are historical.

- **0.7.6 compiled/linked with v100 x64, installed, actual MCP stdio; 207 pytest tests pass in 4,00 s and native physics-aggregation tests passed.** PhysicsActual::_NV_backThreadUpdate replaces charsUpdateUT: three probes, old field null, no algorithm changed. Physics observed on thread 34744, separate from GameWorld8612; creation time exactly joined to OS CPU, approximately 0,043 logical processor for that whole thread at x1 in Heng.600-frame/600-call windows, partial CPU/quantization and overflow documented; no cross-version gain inferred. Deployment archived, new game identity19920, copy restored paused,702/702/738 files compliant, exact preferences. Old snapshot retained on disk, in-memory association lost after restart. Watchdog and deadline unchanged. See physics-probe-measurements.md and runtime/physics-076-final.json. The following entries are historical.

- **193 pytest tests pass in 4,07 s; plugin 0.7.5/v100 x64/17 tools/three hooks unchanged.** PSS limited to thread metadata validated on helpers, then read once on the paused game with query rights and without an administrator session.126 threads captured, resources released;119/120 previous CPU identities joined. Workers37324/39984 share MSVCR100+0x21dbc and remain unattributed. Grouping by startup module does not measure exclusive module CPU. No game state modified, clock/view/pause preserved, last complete manifest bound by fingerprint, healthy watchdog/deadline unchanged. See thread-start-metadata.md and runtime/thread-metadata-final.json. ETW pilot remains pending; the following entries are historical.

- **182 pytest tests pass in 4,06 s; plugin 0.7.5/v100 x64/17 tools/three hooks unchanged.** Native pause/x1/pause CPU sequence at Heng:1,835/2,353/1,792 mean logical processors. GameWorld/Renderer thread remains near 0,8; two unattributed workers consume more at x1. Mean pauses equal77,08 % of x1 rate, descriptive contrast without exclusive cost or claimed gain. Identities/inventories checked, evolving x1 population, frame windows separate from CPU bounds. Source/copy/snapshot/preferences intact; copy restored paused, fresh watchdog/deadline unchanged. See pause-cpu-measurements.md and runtime/scenarios/pause-cpu-075-final.json. The following entries are historical.

- **168 pytest tests pass in 4,00 s; plugin 0.7.5/v100 x64/17 tools/three hooks unchanged.** Paused Heng:412 complete rows with the existing500 limit,250 intermediate rows correctly excluded, then 412 identical. The guard can therefore cover this scene without redeployment; future default limit increased to 500, configurable, still independent of native 64 KiB. Source/copy/snapshot/preferences intact; copy restored paused, fresh watchdog/deadline unchanged. See heavy-inventory-measurements.md and runtime/scenarios/heavy-inventory-075-final.json. No engine gain claimed; the following entries are historical.

- **165 pytest tests pass in 4,01 s; plugin 0.7.5/v100 x64/17 tools/three hooks unchanged.** Native paused precheck: two reloads of the same snapshot produce172 then 147 update-list characters, including74 then 48 Fogmen, despite two identical tracked actors. Complete/stable inventories at two instants per load; repeated names retained as multiplicities. An environment guard is added to future horizons before speed activation, tested/replayed offline (accepted/accepted/rejected/rejected), without a new identical native battle. Source/copy/snapshot/preferences intact, copy restored paused, fresh watchdog/bound unchanged. See environment-preflight-measurements.md. Variation cause and stack-based CPU attribution remain open; the following entries are historical.

- **145 pytest tests pass in 3,94 s; plugin 0.7.5 and three hooks unchanged.** Four resumptions of the same combat snapshot, x1/x5/x5/x1 order, reach a target horizon of 0,5 simulated hour; initial visible guards identical, overshoots retained. Medical outcomes and populations diverge even at equal speed: no gain or identical work inferred. First pilot stopped/restored after observing the speed command unpause; bounds corrected before all four completed runs. Source/copy 702 files each and snapshot738 files compliant; copy paused and view/preferences restored, healthy watchdog. See snapshot-horizon-measurements.md and runtime/scenarios/snapshot-horizon-075-final.json. Administrator CPU-stack capture remains pending. The following entries are historical.

- **Plugin 0.7.5 unchanged,124 pytest tests pass in 3,94 s; native Windows CPU attribution added without a new hook.** Ten-NPC combat over 45,094 s through MCP stdio:2,303522 mean logical processors,34,33 % of CPU on GameWorld/Renderer thread,7,34 % on an observed navigation worker,58,35 % on others. Groups describe whole threads; dominant functions still unknown.120 identities matched, three exclusions and signed residual retained. Navigation audit with explicit truncated context:97 observations/77 distinct calls. Complete final verification:702 compliant files for each save, game paused/reference view/preferences restored, healthy watchdog/deadline unchanged. WPR pilot denied by Windows policy0xc5585011, without remaining trace/session; optional administrator intervention requested to continue stack attribution. See thread-cpu-measurements.md and runtime/scenarios/thread-cpu-campaign-075-final.json. The following entries are historical.

- **0.7.5 compiled with v100 x64 and loaded;109 pytest tests pass in 3,79 s; actual MCP stdio inventory of 17 tools.** New save_scene_snapshot through public SaveManager::save, strict test name, target absence checked, and overwrite natively rejected. Separate snapshot, tracking recovered in the same session, and pause applied before publishing readiness. Both initial 0.7.5 reloads have identical health/time but a1,897-unit vertical variation, rejected by the guard; two additional paused observations match exactly. Limitations retained in scene-snapshot-measurements.md, no full determinization claimed. Navigation audit extended to battle format:62 observations/45 distinct calls, two nonempty false outputs. All702 files from each initial save still match control; view, pause, mode, and preferences restored. Native deadline brought forward to 22 h15 min00 s UTC, without extension.

- **0.7.3 compiled with v100 x64 and loaded;89 pytest tests pass in 3,81 s; still 16 MCP tools and three system hooks.** Targets and seven medical parts observed. Explicit faction selection, ambiguities rejected, opponent allowed only with already mutually hostile factions. Actual combat at Mongrel: two NPCs then ten, injuries/received attacks/unconsciousness observed. Second run uses actual MCP stdio tools for every command, including creation/restoration; five KOs observed in 45,125 s. Guard reinforcements present, non-isolated scenario. Same PID31284, source save intact, copy/camera/Edge scrolling/pause restored. See battle-observations.md. The following states are historical.

- **0.7.1 compiled with v100 x64, loaded;76 pytest tests pass in 3,87 s; actual MCP stdio with 16 tools confirmed.** Additions: detailed inventory bounded to 100 rows, NPC-pair preparation on paused copy, combat/blood tracking by prefix, raw SDK input, and temporary edge-scrolling control. No fourth hook. Two-NPC creation/objectives observed over 20,422 s; actual hits unconfirmed at this point. Copy, camera, and Edge scrolling restored, source intact; see battle-observations.md. The following0.6.x states are historical.

- **0.6.3 compiled/loaded,67 pytest tests pass in 3.61 s**. Offline audit with identities/processes, deduplication, and camera quality;44 observations grouped into27 distinct calls after the last campaign. All-call true/false counters natively reconciled with totals, output-array sizes observed. SDK clocks verified: game hours frozen in pause, raw timer continuing to advance. City measurement3×600 frames per condition: clock progression x5/x1=4,999217. This measurement does not prove zero latency for every AI task; report simulation-clock-measurements.md.
- city-paired-20261028T004449Z: camera controlled, same PID37836, no restart, successful restoration and saves preserved. Last long context call (180 ms) completed before x5 preparation; it is absent from stabilized windows. False returns in those windows are fast, preventing generalization of older slow-sample cost to all false returns.

- Update on28 October, around 01 h28 Europe/Paris: **0.6.2 compiled/loaded,53 pytest tests pass in 3.18 s**, still 15 tools and three system hooks. Optional findPath-call CPU and Havok vectors captured. Four162..168 ms wall calls consumed approximately 141..172 ms CPU; quantized values retained, details in navigation-diagnosis.md. First x1 condition with camera drift excluded; a guard now checks every window.
- Real incident after city-paired-20261028T002159Z measurements: Windows PermissionError during state.tmp→state.json, watchdog exit followed by closure of its game; initial restoration incomplete, saves intact. Archive crashes/20261028T002453.1222217Z-state-publication. Fix: bounded retries, supervision maintained on publication failure. Offline tests then an **actual four-second lock** validated: PID40056 and creation time unchanged, frames 3363→3879, failed-publication counter0→3, fresh-state recovery. Reference view/pause restored in the new process; evidence runtime/state-lock-validation.json and runtime/scenarios/restored-camera-062-recovered.json.

- Update on28 October, around 01 h09 Europe/Paris: **0.6.1 compiled/loaded,41 pytest tests pass in 3.13 s**. Atomic bucket publication and per-thread findPath diagnostics, without a new hook or MCP tool. Campaign 5 then 1, 5×600 frames per condition:1983 calls on threads other than GameWorld, including14 slow154..166 ms calls, all on the same separate thread with false return. Overall process CPU measured, native identity/consistency checks passed. See navigation-diagnosis.md for evidence/limitations; CPU of individual calls still unknown. Copy restored paused, source/copy quick.save intact.

- Update on28 October, around 00 h58 Europe/Paris: **0.6.0 compiled with v100 x64 and loaded,33 pytest tests pass in 3.16 s,15 MCP tools**. prepare_town_scene uses the public movement controller to move the copy's player group. Heng observed: two active cities,447..453 update entries,160..167 characters within 2000 units of center, over thirty seconds. Both players' arrival verified from subsequent positions. A temporary world_ready=false transition interrupted the first script; retry without repeated mutation and final restoration succeeded. Evidence populated-20261027T235525Z.json / populated-20261027T235611Z.json in runtime/scenarios.
- Two city measurement pairs under 0.6.0: runtime/measurements/city-paired-20261027T235740Z (1→5) and city-paired-20261027T235907Z (5→1),3×300 frames per condition, before/after populations retained. Initial view, normal mode, and pause restoration confirmed; source intact and PID9772 stable. Results/limitations in city-measurements.md; findPath wall-time spikes remain to be classified by thread, no gain claimed.
- Actual MCP stdio: tools/research/live_mcp_inventory.py obtained15 tools and called ping/get_scene_state/list_towns against the engine without error. Local evidence runtime/mcp-inventory.json. This test starts the server for its session and does not confirm permanent registration in the Codex client.

- Update on28 October, around 00 h44 Europe/Paris: **0.5.1 compiled and loaded,31 pytest tests pass in 3.21 s,14 MCP tools**. Inventory of 304 cities and camera state read in-game, without an additional hook. Camera test toward Heng immediately accepted, then constrained by the engine under 0.5.0 and 0.5.1; no populated city validated. Evidence under runtime/scenarios/ and details in scenario-candidates.md.
- Reloading retains free-camera mode: restoration fixed with set_camera_free before load_save, validated with tests/live_restore.py. Camera positions identical to initial read, free mode false, pause true. Source save preserved at reference SHA-256. Process 36676 passed through these tests without watchdog restart; PIDs do not authorize a later stop.

- Update on28 October, around 00 h10 Europe/Paris: **version 0.4.0**, third hook NavMesh::findPath installed and called in-game; **22 pytest tests pass in 3.18 s**. v100 compilation succeeded after reproducible SDK-header fixes (typename and struct tag EdgePathNode), explained in [dependency preparation](../first-run.md). Windows now have verified non-overlapping identifiers.
- Reversed pair 5 then 1 run under 0.4.0:110 then 210 findPath calls over 900 frames per condition; local data paired-20261027T230735Z and results in initial-measurements.md. Initial speed restored, copy paused again. Source save still at reference SHA-256. Healthy watchdog, automatic recovery validated after deployment.

- Main version 0.3.2 compiled with v100 x64; optional bootstrap compiled with the same toolset. **21 pytest tests pass in 3.18 s**. Native JSON tests also passed.
- Pause:true and multiplier0 observed. Speeds2 and 5 reread after several frames; restored to 1, unpaused. UI label does not necessarily track setGameSpeed(speed,false).
- Public SaveManager load observed on KenshiProbe_test. Internal returned name remains KenshiProbe_validation because the save is a copy. Old folder-name equality check fixed in live_load.py.
- Three real300-frame windows collected at speed1. See initial-measurements.md and local runtime/measurements/ files; no bottleneck attribution or optimization gain inferred.
- Restart requested through **actual MCP stdio**: PID37860 →17000, acknowledgment3be2b8fbb84844da9b7d7d80f74ab67b, archive crashes/20261027T224119.477232Z with reason=requested and log.
- Simulated abrupt exit of only the test process: PID17000 →26820, archive crashes/20261027T224152.618904Z with reason=process_exit.
- Controlled freeze with psutil.suspend of PID26820, after startup grace expired: restart to PID28396, archive crashes/20261027T224549.017486Z with reason=heartbeat_timeout. Script had a safety resume in finally; the watchdog terminated the suspended process.
- False positive discovered in real conditions with 0.3.1: restart during normal loading. Fixed with loading and loading_timeout=120 s, bounded grace tested offline. The same PID37860 then passed through a load and resumed frames without restart; loading returned to false.
- The0.3.0 Ogre listener was not invoked. It was replaced by Renderer::_NV_update; render heartbeat advances in the menu, and the hook serves ping/load_save. This is not a third profiling hook: only charsUpdate and charsUpdateUT remain timed systems.
- First bootstrap test: KenshiLib assertion due to missing WholeProgramOptimization. Build fixed. Preloader installed with Unix expiry1793225755. Full recovery then validated without UI input: restart_game through MCP, PID13752 →21456, archive crashes/20261027T224929.442453Z, automatic launcher validation and loading KenshiProbe_test. world_ready=true and frame=497 observed; service_thread=game_thread=12844. loading=false, autoload_requested=true, autoload_error=null.
- A pair of three windows at speed1 then 5 collected with the same copy reloaded before each condition; local files paired-20261027T225206Z and table in initial-measurements.md. Initial speed1 restored.
- Source-save and copy quick.save still have the same SHA-256:04488B407BC57F8FDB1CBBDD8D1AFC006D2B179F020FF89A9ACF459DF934FBEB. Source preserved.
- session_until added to watchdog: tests verify an expired campaign starts no process and the deadline closes the owned process. Local deadline1793225755; this safeguard complements shutdown automation.

Live scripts are not pytest tests, and their effects are limited to the copy and identified processes. Older mentions of TODO(load_save), nine tools, and unperformed compilation below describe early steps, not current state.

<a id="exécuté"></a>

## Executed

- Python 3.12.14, local virtual environment; MCP SDK1.30.0 (FastMCP), pytest 9.2.0.
- `.venv/Scripts/python.exe -m pytest -q`: **12 passed in 2.49s**. Loopback-socket and stdio-subprocess tests executed outside the restrictive network sandbox.
- Fragmented protocol, identifier matching, unsupported error, invalid JSON response, and timeout.
- Server tools against fake plugin, boundary validation, log, missing/stale status; actual MCP stdio initialization, inventory of nine tools, and ping through ClientSession.
- Watchdog: startup grace, process exit, heartbeat stop, archiving log/dummy dump, acknowledgment of requested restart, automatic restarts. One test starts/stops an actual dummy Python process.
- Project XML read: two x64 configurations, both v100, source Probe.cpp.
- Git status inspection: no file from the pre-existing Kenshi directory, downloaded dependency, or generated file listed for addition.

<a id="non-exécuté"></a>

## Not executed

- Native plugin compilation and C++ parser tests: no v100 toolset found. Visual Studio18 Community has v145, which does not satisfy the required ABI.
- RE_Kenshi/KenshiLib installation, game launch, hook safety, character-list completeness, pause/speed effects, real measurements, and native-crash recovery. The local game reports 1.0.68; RE_Kenshi and KenshiLib DLLs were absent from the inspected root.
- The fake plugin validates Python exchanges; it does not validate C++ code or engine APIs.

<a id="todo-restant-dans-le-code"></a>

## Remaining code TODO

One marker: `plugin/Probe.cpp`, `TODO(load_save)`: validate loader entry point, instance, lifetime, and load transition. The command currently returns an error. Screenshot capture is optional and unimplemented. Other required validations are detailed in open-questions.md and first-run.md.

The Git repository was initialized without a commit. No game file was modified and no game launched during this work.

<a id="validation-native-ultérieure-du-27-octobre"></a>

## Subsequent native validation on27 October

This section supersedes historical limitations above for plugin compilation/loading.

- Installed compiler: Microsoft C/C++16.00.30319.01 for x64 (v100). Release build succeeded with Visual Studio18 MSBuild and VCTargetsPath v4.0. Warnings come from KenshiLib/MyGUI headers.
- Official dependencies downloaded under references/KenshiLib_Examples_deps, revision b566d74bf3d74629cc2fb632a97595b8202993f1. Boost1.60 extracted locally; no global environment-variable changes.
- Generated DLL: plugin/build/Release/KenshiProbe.dll. dumpbin confirms export ?startPlugin@@YAXXZ and dependencies KenshiLib.dll, WS2_32.dll, KERNEL32.dll, MSVCP100.dll, and MSVCR100.dll.
- `tests/test-json-v100.cmd`: Native JSON checks passed. Tested code is exactly plugin/json.h, compiled with v100 x64.
- Installed under Re_Kenshi/mods/KenshiProbe/ from the empty official HelloWorld template. Enabled in data/mods.cfg, previous backup mods.cfg.before-kenshi-probe. These installation files remain outside Git.
- Game launched: compatibility process Re_Kenshi/RE_Kenshi/kenshi_x64.exe --norestart, launched from Re_Kenshi/. Log: RE_Kenshi0.3.5 and KenshiLib0.5.0.
- Actual log: “KenshiProbe -> KenshiProbe.dll”, “[KenshiProbe] profiling hooks installed”, and “[KenshiProbe] listening on loopback”.
- First actual ping in the menu: plugin error after 9 seconds, “main thread timeout”. Network connection works, but the hook does not drain the queue in the menu. The expired request is canceled; a game must be loaded to continue validation.
- Local watchdog configuration fixed to target the persistent process with a separate working directory. The validation game is not watchdog-supervised and was not automatically restarted.
- After this adjustment, Python suite rerun: **12 passed in 3.23s**.

Next: first ping with advancing in-game frame counter, measurements, control commands, real watchdog validation, and safe save loading.

<a id="validation-dans-la-partie-chargée"></a>

## Validation in the loaded game

- `tests/live_probe.py`, run manually: actual ping succeeds, plugin 0.1.0 and game1.0.65 Steam. Counter observed from 2372 to 2375 over two calls bracketing reads.
- 300-frame sample: mean 15.4488 ms, median 14.9664 ms, p95 18.9501 ms, p99 28.47 ms, maximum 44.6728 ms. Speed/pause conditions not recorded: this validates measurement, not a reproducible performance baseline.
- System hooks: charsUpdate mean 0.18457 ms, charsUpdateUT mean 0.00471 ms. These values do not necessarily cover all AI or navigation.
- list_characters(limit=5) returned five names, factions, and positions; total_update_list=79.
- `tools/research/live_mcp.py`, run manually: official MCP stdio initialization and successful ping/get_frame_stats calls against the actual plugin.
- Four requests rejected by the actual plugin: invalid JSON, duplicate id key, unknown command, wrong limit type. A subsequent ping succeeded, frame=3684.
- Live scripts are not collected by pytest. To rerun from the root: set PYTHONPATH to mcp-server, then run `.venv/Scripts/python.exe tests/live_probe.py` or `tools/research/live_mcp.py`.

Still to validate: pause/speed command effects and real supervision with restart. No restart or speed/pause change was made in the loaded game. TODO(load_save) remains open.
