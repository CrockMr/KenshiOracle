> Active state: plugin **0.8.1**, SDK roles retained; selected AI target update4Frame, [current measurements](ai-target-selection-measurements.md). Figures for 0.7.9 and earlier below remain historical.

<a id="rôles-de-threads-sdk--état-courant-079"></a>

# SDK thread roles — current state 0.7.9

**Resource loading and the navigation generator are now linked to exact Windows identities, but do not explain the most expensive remaining worker in this trial.** The seven exposed roles correspond to five verified threads, one physics alias and one unavailable save identity. Version 0.7.9 retains 17 MCP tools and three system probes, v100 x64; no engine algorithm is replaced.

<a id="accès-sdk-groupés"></a>

## Grouped SDK access

ResourceLoader.h declares ResourceLoader::getInstance() and public ThreadClass inheritance (secondary base, adjusted by the C++ compiler). SaveFileSystem.h declares getSingleton() and ThreadClass inheritance. NavMesh.h publicly exposes generator; NavMeshGenerator.h defines its ThreadClass inheritance. Getters are linked through the official SDK library and actually called in-game. No base offset is re-encoded, no constructor called. Optional reads only from the main callback, with the world ready and paused and no pending save/load; no new name-field read or hook.

Optional roles resource_loader, save_file_system and navmesh_generator join world_physics_interface. The three initial roles remain required. Reanalysis of 0.7.7 data retains exactly the historical cached join (runtime/sdk-077-compatibility-079.json). Aliases and roles present at only one endpoint or unverified retain their explicit treatment.

SaveFileSystem exists here, but its SDK threadID field is 0 and its identity unusable: available=true, identity_verified=false, CPU unknown. This means neither zero cost for all saving nor absence of delegated threads.

<a id="relevé-à-heng"></a>

## Heng measurements

- New game PID **7716** after archive crashes/20261028T055854044666Z-deployment-079 (old 0.7.8 DLL/config/preferences/log, reason deployment_0.7.9).
- Smoke: runtime/sdk-079-smoke.json; all seven rows returned, six role identities verified including the physics alias, one unavailable identity.
- Raw MCP: **runtime/scenarios/sdk-roles-20261028T060036Z.json**, SHA-256 **4e64161ad08bb63fe22e9eeb0a7bf29718d0e541e1e6f5464ff146758f3c4367**.
- Recomputed analysis: **runtime/sdk-079-analysis.json**; final state **runtime/sdk-079-final.json**.

The scenario reloads the copy, prepares Heng, stabilizes streaming, reads roles while paused, runs x1 then measures twenty requested seconds. It rereads roles while paused and restores the copy. No pytest during the CPU interval. SDK identities bracket the scenes and match TIDs/creation times at both OS endpoints.

**48,234375 CPU seconds in 20,375 real seconds = 2,367331 mean logical processors.** Clock advances 0,186876 hour, population 406 to 446. Five threads are absent at the second endpoint and explicitly excluded; signed process-minus-covered-sum residual **−0,046875 s CPU**, not normalized.

| SDK role | TID | Whole-thread CPU (s) | Mean logical processors | Process share |
| --- | ---: | ---: | ---: | ---: |
| world_ai_non_render | 23468 | 5,500000 | 0,269939 | 11,4027 % |
| world_navmesh | 32120 | 0,171875 | 0,008436 | 0,3563 % |
| physics_backthread | 19104 | 0,953125 | 0,046779 | 1,9760 % |
| world_physics_interface | 19104 | same thread as above | same thread | same thread |
| resource_loader | 16792 | 0,078125 | 0,003834 | 0,1620 % |
| navmesh_generator | 40520 | 0,000000 measured | 0,000000 measured | 0,0000 % measured |
| save_file_system | unknown | unknown | unknown | unknown |

The generator's zero is a quantized counter delta, not evidence of absolutely no work. Verified roles remain stable before/after. After deduplicating the physics alias: **5 unique threads, 6,703125 s CPU, 0,328988 logical processor, or 13,8970 % of process CPU**. Analysis exposes known_sdk_thread_cpu separately from the historical join to preserve old caches. It never sums the same TID/creation twice.

Unidentified worker **TID 19272**, creation FILETIME **134376407470372177**, consumes **6,500000 s CPU / 0,319018 logical processor**; next is TID 33784, 0,183282. Neither is assigned a function by creation order or resemblance to older versions. The table covers whole threads, not exclusive costs of all resources/AI/navigation/physics. No performance-gain comparison across versions, RE_Kenshi panel not visually verified, other applications' load unquantified.

<a id="validation-restauration-et-prochaine-hypothèse"></a>

## Validation, restoration and next hypothesis

**230 pytest pass in 3,99 s**, with distinct roles/aliases/unavailable identity, deduplicated CPU coverage and unknowns retained. v100 x64 compilation/linking succeeded before deployment; new getters and conversions confirmed in-game. The optional native parameter remains functional and mistyped strings rejected. Hidden Start-Process launch releases the parent handle; no Popen warning observed.

Game **7716**, watchdog wrapper **12552**/child **37596**, are the final-check identities, to reread before action. Copy reloaded paused, normal reference view, Edge scrolling=true, tracked combat inactive and temporary control released. **702/702/738 files** source/copy/old snapshot compliant; settings.cfg byte-identical to beforehand, guards false. Fresh watchdog without error, autoload successful; deadline and activation **1793225700** unchanged. No active measurement controller. The old snapshot exists on disk but its in-memory ownership is no longer assumed.

These new identities rule out both objects as major explanations of this CPU in this sample. Identical CPU profiling would not clarify the unknown worker's functions. Next usable hypothesis without a fourth probe: measure public AI::_NV_periodicUpdate(float) calls, in AI/AI.h, **replacing** the inexpensive physics probe, accumulating by thread identity and checking signatures/linking. This can isolate inclusive function cost on a known or unknown thread; no optimization before evidence, no GetRealAddress on the virtual periodicUpdate member itself. Administrator CPU-stack pilot still pending; do not repeat the question or failure without a user-side change.

Numbers in older sections below belong to their own processes and remain historical.

<a id="historique--rôles-de-threads-sdk--078"></a>

# History: SDK thread roles — 0.7.8

**The main physics interface and its back-thread are the same Windows thread in the verified scenes.** This avenue therefore identifies no additional worker. Version 0.7.8 retains 17 MCP tools and three system probes; no game algorithm is replaced.

<a id="nouvelle-preuve-sans-répéter-le-cpu"></a>

## New evidence without repeating CPU measurements

PhysicsActual.h publicly declares PhysicsInterface : ThreadWannabe : ThreadClass, and GameWorld.h exposes physics. The optional reader adds world_physics_interface alongside physics_backthread, with the same TID/PID/creation checks and pause/save/load guards. No new offset or hook.

After loading KenshiProbe_test, then at Heng after ten seconds of x1 simulation and stabilization, both roles have the same identity: **PID 30380, TID 16028, creation FILETIME 134376399467422055**. Two paused reads at Heng, frames 8453 and 8854, recover this identity; 404 characters in both reads. Other observed roles are world_ai_non_render TID 30104 and world_navmesh TID 32792. These identities belong to this process and are not joined to older-version measurements.

- MCP smoke and native checks: runtime/sdk-078-smoke.json.
- Heng scene: runtime/scenarios/sdk-alias-20261028T054744Z.json, SHA-256 **0a5f46ea9ca3cad0663f364c66d53abb419ae0f61d1ba9e37adc0809b250677e**.
- Final check: runtime/sdk-078-final.json.
- Deployment archive: crashes/20261028T054533762503Z-deployment-078; reason deployment_0.7.8, old 0.7.7 DLL/config/preferences/log retained.

The controller ran no new CPU interval: the alias supplies no additional attribution to measure. CPU figures for 0.7.7 below remain historical. No percentage is carried to PID 30380; no cross-version gain claimed. Observing the alias does not guarantee invariance in every game or game version.

<a id="compatibilité-et-défaut-corrigé"></a>

## Compatibility and corrected defect

The three initial roles remain required for analysis; world_physics_interface is optional. Older captures reanalyze without changing their cached joins, attested by runtime/sdk-077-compatibility-analysis.json. If the extra role appears at only one endpoint, its CPU remains unknown. Aliases count as one identity, not two consumers to sum. Unknown roles, duplicates or missing required roles remain rejected.

Preflight revealed that native calls omitting thread_details failed under 0.7.7 with missing field, while the MCP server always supplied false. **0.7.8 restores native-level default false**: omission and explicit false validated in-game, mistyped string still rejected. MCP server retains boolean validation. No tool-count change.

**227 pytest pass in 3,78 s.** Initial restricted-environment compilation failed C1902 (PDB manager), then authorized local compilation and v100 x64 linking succeeded. Installed after successful linking. Watchdog launched with Start-Process -WindowStyle Hidden and parent handle explicitly released; no Popen warning observed for this launch. --config paths compared after resolution because PowerShell produced a valid mixture of separators.

<a id="état-restauré-et-suite"></a>

## Restored state and continuation

Game 30380, watchdog wrapper 2440/child 32296 at final check: recheck path/command/creation before action. Copy reloaded paused, normal reference camera, Edge scrolling=true, tracked combat inactive and temporary control released. **702 source files, 702 copy and 738 old snapshot** all compliant; settings.cfg byte-identical to beforehand, recovery guards false. Fresh watchdog without error, deadline/activation **1793225700** unchanged. Test controllers finished. No visual RE_Kenshi-panel check after this restart.

The remaining 0.7.7 worker is not identified by this addition. Headers contain other accessible ThreadClass objects: ResourceLoader::getInstance(), SaveFileSystem::getSingleton() and NavMesh::generator (NavMeshGenerator). Accesses merely located, neither linked nor read in 0.7.8; their full declarations, lifetimes and linking would require verification before extension. Avoid successive restarts for one field at a time. Another targeted hypothesis: AI/AI.h declares AI::_NV_periodicUpdate(float), whose probe could replace the inexpensive physics probe; inclusive cost and delegated calls would still need separating. Do not exceed three probes or call GetRealAddress on a virtual method. Administrator CPU-stack pilot still pending; no new attempt without a change.

<a id="historique--rôles-de-threads-sdk-reliés-au-cpu--077"></a>

# History: SDK thread roles linked to CPU — 0.7.7

A consuming worker is now linked to the object returned by **GameWorld::AINonRenderThread()**: its thread represents **0,271672 logical processor, or 11,40 % of process CPU**, in the Heng x1 capture. Navmesh and physics back-thread also link to exact Windows identities. These roles describe threads referenced by SDK objects; they do not isolate functions that consumed this CPU.

Version **0.7.7 is compiled/linked in v100 x64, installed and validated through real MCP stdio**, still with **17 tools and three system probes**. No new hook: the change adds an optional read to get_scene_state. No engine algorithm replaced.

<a id="sources-et-contrat-de-lecture"></a>

## Sources and read contract

Access comes from installed SDK headers:

- GameWorld.h: AINonRenderThread(), navmesh and physics.
- PhysicsActual.h: PhysicsInterface::getBackthread(), inheritance through ThreadWannabe then ThreadClass.
- NavMesh.h: ThreadClass inheritance.
- ThreadClass.h: threadHandle and threadID.

`get_scene_state(thread_details=true)` requires a ready world, **paused**, without pending load or save. Default false performs none of these identity queries. The server validates the boolean and the DLL rechecks it. This parameter does not create an eighteenth tool.

For each object, the reader copies the SDK TID, duplicates its handle with only THREAD_QUERY_LIMITED_INFORMATION, then checks **GetThreadId, GetProcessIdOfThread and GetThreadTimes**. TID must match the SDK field and PID the current game. Creation FILETIME returned as an exact decimal string. Only the duplicated handle is closed by a scope guard; the borrowed game handle is never closed. No raw pointer or handle retained in the response or between reads.

Public name field not read, lacking guarantees about concurrent changes. Labels world_ai_non_render, world_navmesh and physics_backthread describe SDK accesses used; they do not derive from Windows names or inferred stacks. identity_verified attests identity, not that the thread is currently executing or performs only one system. Absent object, invalid handle or disagreement returned without inventing a valid TID.

<a id="preuves-et-déploiement"></a>

## Evidence and deployment

- Archive: `crashes/20261028T051812394044Z-deployment-077`, old 0.7.6 DLL, configuration, preferences and log; reason `deployment_0.7.7`, not an engine crash.
- `runtime/deploy-077.json`: identities reread before stopping game 19920 and watchdogs 19296/36144, DLL fingerprints. Only project processes stopped.
- New game **25120**, watchdog wrapper **6412**/child **10988** at final check, automatic copy loading confirmed.
- `runtime/sdk-077-smoke.json`: three SDK/Windows identities verified while paused.
- Raw: `runtime/scenarios/sdk-roles-20261028T052110Z.json`, SHA-256 **966b4871b06953bce3d52dc75a378e2e131227302ab709d58fe693842c5108f9**.
- Analysis recomputed from raw: `runtime/sdk-roles-analysis.json`.
- Final state: `runtime/sdk-077-final.json`.

The deployment Python parent emitted a Popen finalizer warning, WinError 6, after detached launch. Watchdog and game were then verified actually active, without publication error; the parent warning is neither classified as a game crash nor concealed. For a future detached launch, prefer hidden Start-Process with explicit parent-handle management, then verify processes.

<a id="mesure-x1-à-heng"></a>

## Heng x1 measurements

The controller prepares Heng from KenshiProbe_test, allows planned streaming and captures roles while paused. It enables x1, allows three seconds to stabilize, then measures twenty requested seconds with per-thread OS CPU counters and scenes every 0,5 second. After measurement, a second paused read must recover the same roles and creation times. A details request during simulation was **natively rejected**, as expected, without changing speed.

The process consumes **48,531250 CPU seconds in 20,360 real seconds**, or **2,383657 mean logical processors**. Clock advances 0,186529 hour, observed population varies 415 to 430. One thread absent at the second endpoint remains explicitly excluded; signed process-minus-thread-sum residual **−0,171875 CPU second**, without normalization.

| SDK object role | Verified TID | Whole-thread CPU seconds | Mean logical processors | Process CPU share |
| --- | ---: | ---: | ---: | ---: |
| world_ai_non_render | 26984 | 5,531250 | 0,271672 | 11,3973 % |
| world_navmesh | 5372 | 0,093750 | 0,004605 | 0,1932 % |
| physics_backthread | 18656 | 0,953125 | 0,046814 | 1,9639 % |

Creation times identical before/after and exactly match CPU samples. The three roles are distinct here; the protocol nevertheless permits aliases, and analysis counts unique identities rather than automatically summing roles.

Worker **16564**, about **0,333067 logical processor**, remains the leading thread outside these three roles and the main service. Its role is not attributed by TID proximity, creation order or resemblance to an old process. Old 0.7.5/0.7.6 data are not joined to the new PID.

Values cover whole threads. They are neither exclusive cost of all AI, navigation or physics, nor function stacks. Population, caches and other applications are not fixed for cross-version comparison. RE_Kenshi panel not visually checked after this startup; no performance gain claimed.

<a id="reproduction-et-validation"></a>

## Reproduction and validation

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_sdk_thread_roles.py
& ./.venv/Scripts/python.exe tools/research/analyze_sdk_thread_roles.py runtime/scenarios/sdk-roles-20261028T052110Z.json
```

The first command conducts a new trial and restores the copy; the second only reanalyzes raw data. The report rejects contradictory cached joins, frame regression or SDK reads that do not bracket CPU-interval scenes. Changed/unverified identity or a thread missing from an endpoint gives an unknown value, never an invented zero.

**222 Python tests pass in 3,96 s**, including boolean transmission/validation, SDK/kernel disagreement, reused TID, aliases and evidence boundaries. DLL also rejected the mistyped native parameter; evidence in final check. Real captures attest SDK linking and the three getters in-game.

The **702 KenshiProbe_validation files, 702 KenshiProbe_test files and 738 old-snapshot files** remain compliant. settings.cfg identical before/after deployment and trial; recovery guards remain false. Copy reloaded paused, normal reference view, Edge scrolling=true, no active tracked combat or temporary control. Fresh watchdog, zero publication errors, deadline **28 October 22 h 15 UTC** unchanged. No measurement helper remains active.

Next useful evidence must clarify the remaining worker or functions executed by the non-render role. PhysicsInterface also inherits ThreadClass: world->physics interface role could be compared with getBackthread(), without assuming distinctness. Such an extension must retain compatibility with older three-role captures and add no hook. Administrator CPU-stack pilot still pending; no policy bypass performed.
