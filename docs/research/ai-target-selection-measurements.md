<a id="sélection-de-sonde-ia-et-aiupdate4frame--081"></a>

# AI probe selection and AI::update4Frame — 0.8.1

**AI::update4Frame is also observed on SDK role world_ai_non_render and does not identify the remaining worker in this trial.** The final x1 window's 31 010 calls represent **0,032379 cumulative inclusive ms per service frame**, or 19,427675 ms over 600 frames. Their very short duration motivates less intrusive profiling; no engine optimization is claimed.

Version **0.8.1**, compiled/linked v100 x64 and validated through real MCP, retains **17 tools and three system probes**. The AI target is now selectable **at game startup**, without rebuilding to switch between two functions.

<a id="sélection-et-contrat-explicite"></a>

## Selection and explicit contract

KENSHI_PROBE_AI_TARGET accepts exactly periodicUpdate (default if absent) or update4Frame. The variable must be present in the environment of the **watchdog launching the game**; changing it in an already connected MCP server does not change the running DLL. An unknown or overly long choice disables only the AI probe and reports ai_probe_target_valid=false, without installing another target instead. No target change during measurement.

AI/AI.h declares void AI::_NV_periodicUpdate(float) and void AI::_NV_update4Frame(float). Code resolves the selected non-virtual wrapper and executes **one AI AddHook only**; charsUpdate and findPath remain the other two probes. The original retains its AI*,float type and arguments. Physics and charsUpdateUT probes remain absent. The counters, TLS nesting guard and overflow bucket from 0.8.0 are retained.

- ping.ai_profiled_function: selected name, AI::periodicUpdate or AI::update4Frame; null name for invalid selection. Check ai_profiling for effective installation.
- ai_periodic_update_profiling and ai_update4_frame_profiling distinguish the sole active probe; ai_probe_target_valid distinguishes selection validation from hook success.
- get_frame_stats.systems.ai_profiled_function: generic metrics object with explicit function and scope.
- The old systems.ai_periodicUpdate is an identical alias **only when periodicUpdate is the active target**; it is null for update4Frame. Never sum the alias and generic object.
- Series ai_function_ms/calls/nested_entries_skipped describe the selected target. Old ai_periodicUpdate_* series are null for update4Frame; old physics series remain null.

Analyzers reject a contradictory alias, unknown function, function changing across phases or incompatible initial selection. analyze_ai_function.py is the canonical entry point; analyze_ai_periodic.py remains a compatible import/CLI. Without --output, the new CLI creates an .ai-analysis.json file derived from the raw filename, without overwriting the historical 0.8.0 report by default.

Native periodic/default selection and invalid values are tested natively, with real 0.8.0 history reanalyzed under the new validator. This campaign's real 0.8.1 launch uses **update4Frame**; periodic mode in 0.8.1 did not receive a new complete scenario, its body having already been tested under 0.8.0.

<a id="preuves"></a>

## Evidence

- Archive crashes/20261028T063509742045Z-deployment-081, reason deployment_0.8.1, old DLL 0.8.0/config/preferences/log; runtime/deploy-081.json. Game 19296 and watchdogs 14244/20820 verified before stopping; only project processes touched.
- New game **37552**, smoke runtime/ai-081-smoke.json: explicit function, correct flags, old periodic object and series null, three probes and seven SDK roles.
- Raw capture: **runtime/scenarios/pause-cpu-20261028T063714Z.json**, SHA-256 **2659b952175e624ffdf4458924ea735424fba26e53e458ab5129dd0ea00ff87b**.
- Canonical analysis: **runtime/ai-081-analysis.json**; old periodic function reanalyzed in runtime/ai-080-compatibility-081.json without changing its figures.
- Final state: **runtime/ai-081-final.json**.

<a id="relevé-pausex1pause-à-heng"></a>

## Pause/x1/pause observation at Heng

The controller restores KenshiProbe_test, prepares Heng and stabilizes streaming; three seconds of stabilization and twenty requested OS seconds per phase. Camera/speed/clock/PID checked during measurement, inventories at boundaries and paused SDK identities bracketing the whole run. No pytest during the interval.

| Phase | Process CPU / real time | Mean logical processors | Population | Target calls in final 600 frames |
| --- | --- | ---: | --- | ---: |
| Pause before | 37,562500 s / 20,297 s | 1,850643 | 393 stable | 0 |
| x1 | 49,531250 s / 20,344 s | 2,434686 | 407..446 | 31 010 |
| Pause after | 36,093750 s / 20,297 s | 1,778280 | 446 stable | 0 |

Clock +0,186497 h at x1, stationary while paused. Signed CPU residuals +0,078125 / +0,437500 / +0,031250 s retained; final phase: one thread missing at each boundary, explicitly excluded. No gain comparison with previous versions: population, process, caches and conditions differ.

The final x1 window, frames **13166..13765**, contains only thread **37692 / creation FILETIME 134376429227663373**, matching world_ai_non_render role identity and OS counters. **19,427675 inclusive wall ms**, mean **0,032379 ms/frame**, maximum call **0,034000 ms**; no overflow or nested entry observed. Arithmetic mean per call about **0,6265 µs**; this is not a latency quantile.

Call CPU is available for every call: **31,250 ms user, 0 ms kernel**, accumulated above 19,428 wall ms. Short durations and quantized CPU: values are retained without clamping or exclusive coverage. Two CPU reads per call have an order of magnitude comparable to this mean call (startup read ~0,2335 µs), but that calibration does not measure the complete hook cost. The result justifies reducing profiling reads; it does not provide a precise perturbation percentage.

The **whole thread**, over the 20,344 s x1 OS interval, consumes **6,390625 CPU s = 0,314128 logical processors**. OS and function (~4,517 s) windows differ; no coverage ratio is calculated. The thread moves through 0,046189 / 0,314128 / 0,053117 logical processors across phases.

Worker **26476 / creation 134376429227661575** remains without an attributed function: **0,002309 / 0,322577 / 0,000770 logical processors**. It is not found among captured rows for this target. Main service 37156 remains at ~0,737486 / 0,741926 / 0,761350 logical processors. A method name cannot establish its per-actor cadence; no AI pointer or actor identity is recorded.

<a id="validation-et-état-laissé"></a>

## Validation and state left behind

**251 pytest tests pass in 4,00 s**, covering selection/generic/history, unique alias, contradictory labels and mixed phases. Native v100 x64 tests for selector, bounded counter, reused TID and depth restoration after exception pass. SDK getters and non-virtual target linked and observed in-game. The MCP server remains at 17 tools.

Game **37552**, watchdog wrapper **2012**/child **1484** at the final check: recheck path/command/creation before action. Copy reloaded paused, normal reference view, Edge scrolling=true, tracked combat inactive and temporary control released. **702/702/738 files** of source/copy/old snapshot conform; settings.cfg byte-identical to the prior state, guards false. Watchdog fresh without error, autoload successful, deadline/activation **1793225700** unchanged, controller finished. RE_Kenshi panel not visually checked, external load not quantified.

<a id="suite-fondée-sur-ces-mesures"></a>

## Next steps supported by these measurements

CPU-disabled mode already exists, but under 0.8.1 it also deprives calls of creation FILETIME (identity querying depends on CPU reads). The priority improvement is **separating identity from CPU measurement**: read/cache thread creation once through TLS, then allow wall durations and OS joining without two GetThreadTimes calls per short call. TLS binds the cache to the thread's actual lifetime; failure must remain explicitly unknown, without inventing a valid TID/creation. Disabled CPU remains null/unavailable, never measured zero. Do not claim gains without a controlled comparison.

The remaining worker then requires another entry point. **GameWorld::charsUpdateUT()** is declared in GameWorld.h and was already hooked in older versions, with an aggregate mean but no thread identity. Reusing this entry point **instead of** the AI target, with exact generic metadata and a GameWorld* signature without float, could test that worker. Do not reuse the AI*,float prototype or add a fourth hook; do not publish these measurements under an AI method name. No cast to RenderTimeBackthread, whose definition is missing. Administrator ETW remains pending: no new attempt or question without a user change.
