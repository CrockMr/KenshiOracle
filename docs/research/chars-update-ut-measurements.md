<a id="attribution-de-charsupdateut--085"></a>

# charsUpdateUT attribution — 0.8.5

GameWorld::charsUpdateUT is observed on the main thread shared with render service, not the remaining worker. The final x1 window's 600 calls total 4,743702 inclusive wall ms. The remaining worker's function is still unidentified; this measurement does not justify optimizing charsUpdateUT.

<a id="une-fonction-sélectionnée-trois-sondes-maximum"></a>

## One selected function, three probes maximum

The selected probe replaces the AI function: charsUpdate, findPath and charsUpdateUT are the three system probes. GameWorld/Renderer service callbacks remain separate. The original charsUpdateUT hook is typed void(GameWorld*), the AI hook void(AI*,float); a shared functor collects measurements without altering those prototypes. The non-virtual declaration was checked in GameWorld.h and resolved through GetRealAddress, like other SDK functions. No engine offset or algorithm changed.

KENSHI_PROBE_FUNCTION_TARGET selects periodicUpdate, update4Frame or charsUpdateUT; a nonempty value takes precedence over old KENSHI_PROBE_AI_TARGET. ping.function_target_source exposes the source. An unknown/overly long value disables this probe alone, without fallback. KENSHI_PROBE_FUNCTION_THREAD_CPU likewise takes precedence over AI_THREAD_CPU when nonempty; 1 enables per-call reads, 0 disables them. This campaign uses charsUpdateUT and CPU0, with TLS FILETIME identity retained.

ping.function_profiling/profiled_function/function_probe_target_valid and function_thread_* fields describe selection. systems.profiled_function and function_ms/calls/nested_entries_skipped series are generic. AI aliases exist only for an actual AI target; in charsUpdateUT mode they are null and ai_profiling=false. charsUpdateUT_mean_ms and its series then carry the corresponding measurement. There are still 17 MCP tools.

function_diagnostics.py rejects contradictory functions/aliases, coexisting old probes and mislabeled series. analyze_profiled_function.py retains exact identities for CPU joins, SDK roles and main/render roles observed. Analysis of old AI measurements remains readable; runtime/ai-081-compatibility-085.json confirms identical historical values, with only three new generic fields added, without overwriting the old report.

<a id="campagne-heng-pausex1pause"></a>

## Heng pause/x1/pause campaign

Raw capture **runtime/scenarios/pause-cpu-20261028T092535Z.json**, SHA-256 **4644cef7fe6fa2f129062d8b538fa5d0e45f7265cf9fbb15418c606a57be4f13**, completed=true, PID33936. Derived report runtime/chars-085-analysis.json. Real stdio MCP; no pytest suite during phases. The camera is protected through loads and measurements; all three phases evolve sequentially without resetting the town to the same initial state.

| Phase | Process CPU, mean logical processors | Clock progression | Observed population | Calls in final 600 frames |
|---|---:|---:|---:|---:|
| Initial pause |1,802266|0 h|403|0|
| x1 |2,468963|+0,186541 h|413–434|600|
| Final pause |1,709298|0 h|430|0|

OS intervals last 20,391/20,359/20,266 s respectively. Signed CPU residuals are 0/+0,015625/+0,031250 s; one identity is missing at the final boundary in each of the first two phases, none in the third. Inventories and population variation are retained, not treated as identical environments.

At x1, frames 18128..18727: 600 outer calls, **0,007906 inclusive ms/frame**, maximum 0,051500 ms, no nested entry/thread truncation. All carry **TID40448/creation134376529869010045**, joined exactly to the OS and game_thread/renderer_service_thread roles observed at the boundaries. The whole thread consumes 16,078125 CPU s over its OS interval, or 0,789731 logical processors using the process denominator. No per-call CPU is declared measured: null values and 600 unavailable calls.

The function window covers 600 frames, the OS window about 20 s; their costs are not divided to claim exclusive coverage. Completed calls count in their ending bucket; an empty period does not exclude other work. Final paused windows contain no call to this function, while the main thread continues consuming about 0,79 logical processors.

SDK role world_ai_non_render is 34252/creation134376529988183642, with 0,055171/0,363783/0,048573 logical processors across phases. Worker **10688/creation134376529988181936** remains outside verified roles and this function: 0,001533/0,355340/0,002313 logical processors. Physics role 21516 represents 0,050653 logical processors at x1; the physics/interface SDK aliases are deduplicated. No exclusive simulation cost or engine gain is inferred from these contrasts.

<a id="validation-et-état-laissé"></a>

## Validation and state left behind

**312 pytest tests pass in 4,48 s**; native v100 selector, bucket and post-exception depth tests pass. v100 x64 compilation/linking succeeded. runtime/chars-085-smoke.json confirms three probes, real name, CPU0 mode, no parallel AI hook, 17 tools and paused copy; stats3600 valid, compact payload 48341 bytes below the 64 KiB limit.

Archive crashes/20261028T092303542614Z-deployment-085, old DLL0.8.4/config/settings/log; runtime/deploy-085.json. WPR inactive, saves and game35336/watchdogs27108/38500 identities checked before stopping only project processes. Own symbols085 retained under runtime/symbols/0.8.5, without adding a game binary to Git.

runtime/chars-085-final.json confirms game33936 paused/normal mode, camera control released/Edge=true, **702/702/738 files** of source/copy/old snapshot conform and settings byte-identical to this deployment's prior state. Guards false, watchdog fresh/zero errors/autoload successful, 17 tools/seven SDK roles, WPR inactive and no active campaign controller. Helpers13460/14864 at this reading; identities must be reread before stopping. Config/activation deadline1793225700 unchanged.

The camera can respond to the edge again after preference restoration. The old snapshot has not recovered its in-memory ownership and current_save remains a sticky internal name. External load is unquantified, and the RE_Kenshi panel was not visually rechecked. These measurements do not causally compare versions.

The administrator Heng ETW capture remains deferred without requested intervention. Next examine ways to obtain coherent user stacks without system privilege, or another supported SDK entry point, before multiplying probes chosen by name. No assumed new RenderTimeBackthread system may be invented; every new probe replaces the current selection.
