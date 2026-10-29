# MedicalSystem::periodicUpdate — 0.8.9

At Heng, this function joins SDK role **world_ai_non_render**. The final 600 x1 frames contain **5 660 calls, 18,333490 inclusive wall ms**, or **0,030556 ms per frame**. No call appears in the final 600 frames of either pause. This record measures neither its exclusive CPU nor any engine gain.

<a id="sonde-et-validation"></a>

## Probe and validation

`KENSHI_PROBE_FUNCTION_TARGET=medicalPeriodicUpdate` replaces ZoneManager in the sole selectable slot. The three probes remain charsUpdate, findPath and MedicalSystem; 17 MCP tools are exposed. MedicalSystem.h declares `void _NV_periodicUpdate()`: original and wrapper receive a `MedicalSystem*`, without float. GetRealAddress resolves the SDK's non-virtual symbol; AddHook passes original arguments without changing behavior. No numeric RVA or repurposed AI prototype.

Ping advertises `medical_periodic_update_profiling`, generic statistics name MedicalSystem::periodicUpdate and AI/charsUpdateUT/physics/Zone aliases are inactive. Per-call CPU times are disabled; the TLS cache independently retains thread creation FILETIME. Unavailable CPU means null, not measured zero. The probe does not automatically cover all medical functions or possible other virtual implementations.

**v100 x64** compilation and linking succeeded, native selector/bucket/depth trials passed and **454 pytest tests pass in 21,85 s**. Recalculation of ZoneManager 0.8.8 data remains strictly identical: `runtime/zone-088-compatibility-089.json`. Real MCP checks version/target/capabilities and the paused copy in `runtime/medical-089-smoke.json`. No new SDK-header change since 0.8.8.

<a id="campagne-pause-x1-pause"></a>

## Pause, x1, pause campaign

Raw capture: `runtime/scenarios/pause-cpu-20261028T122800Z.json`, completed=true, SHA-256 **b2cd8b30ffdc65b450e75cc92e08edf029810fc0b7c90c83d3495cfbd3dcb495**. Analysis: `runtime/medical-089-analysis.json`. Game PID **39204**, Unix creation **1793190312.050583**, path and command verified. Camera controlled, warm-up then three phases; no pytest or build during their measurements.

| Phase | Final frames | Calls | Inclusive wall total | Mean per frame | Max call |
|---|---|---:|---:|---:|---:|
| Pause before |17629..18228|0|0 ms|0 ms|0 ms|
| x1 |20808..21407|5660|18,333490 ms|0,030556 ms|0,093100 ms|
| Pause after |23876..24475|0|0 ms|0 ms|0 ms|

All 5 660 calls belong to **TID 13132 / creation FILETIME 134376639240828501**, joined by exact identity to Windows counters and the non-render SDK role. Zero omitted nested entries, zero thread truncation; 5 660 calls without available CPU, as configured. The per-frame mean must not be presented as a per-call mean.

| OS phase | Process duration | Process CPU | Mean logical processors | Simulated progression | Population at boundaries |
|---|---:|---:|---:|---:|---:|
| Pause before |20,328 s|34,453125 s|1,694861|0 h|404→404|
| x1 |20,438 s|46,437500 s|2,272116|+0,187174 h|414→445|
| Pause after |20,359 s|34,562500 s|1,697652|0 h|445→445|

At x1, whole thread 13132 consumes **4,671875 CPU s** in the native thread interval of **20,422 s**, about **0,228767 logical processors**. This is not exclusive MedicalSystem CPU. The 600-frame function windows and OS windows have distinct boundaries: no coverage ratio is calculated between them. Signed process/thread residuals are −0,015625 /−0,140625 /−0,031250 s. Two identities are missing at the second boundary in the first pause, one at the first boundary at x1; no omission in final pause. No residual is attributed to a function.

Broader 3 600-frame contexts contain **1 /29 860 /5 133 calls** respectively. The last overlaps the active phase; it does not demonstrate medical activity during the final paused window. Observed compact responses: 48 754 /52 568 /48 942 bytes, below the independent 64 KiB ceiling in these cases.

<a id="restitution-reproduction-et-limites"></a>

## Restoration, reproduction and limits

`runtime/medical-089-final.json` confirms paused copy, multiplier 0, time **404,3333339691162 h** identical to the reference, normal camera and temporary control released. All **702/702/738 files** of source/copy/snapshot conform; settings.cfg is byte-identical to the pre-deployment state, guards false. Watchdog fresh without error, WPR inactive, no remaining scenario controller. Edge scrolling is restored to true, so the camera can move after trials.

Archived deployment: `crashes/20261028T122457509551Z-deployment-089`. Own symbols in `runtime/symbols/0.8.9`: DLL SHA **1eb5451accfe89043ef2299b7687b1b6f2f4da1f36515e966749f6959ee69525**, PDB SHA **bedee83488762fb14ad6c5c120b8369611660194c1f72247ef5be1e6e7023b1c**. Old evidence is preserved. No game file, SDK, save or decompiled code in the own-source checkpoint.

Analysis outside the game is reproducible with `analyze_profiled_function.py` on the raw capture above, writing a new output file. Repeating a live scenario requires an authorized session, separate copy and its guards; do not extend the October 28 at 22:15 UTC deadline. No administrator action expected.

The small observed wall costs of MedicalSystem and ZoneManager neither explain the whole worker nor exclude them from future spikes. The next useful step is broader bounded diagnosis of active threads, then heavy x5 conditions with windows adapted to the actual frame count. The main/render thread remains near 0,8 logical processors in these pauses; this does not automatically attribute its CPU to rendering. Population, streaming and external load vary, NPC memory state is not deterministic; no cross-version comparison constitutes a gain measurement.
