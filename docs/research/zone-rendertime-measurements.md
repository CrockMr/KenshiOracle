# ZoneManager::updateRendertimeThread — 0.8.8

The new probe finds this function on the SDK role **world_ai_non_render**, with the thread's exact Windows identity. It continues to run in pause. In the final 600 frames at x1, the 600 calls total **118,798499 ms inclusive wall time**, or **0,197997 ms per frame**, with a maximum of 0,611200 ms per call.

This window does not measure the function's exclusive CPU and does not share the bounds of the twenty-second OS recording. The result supports further worker decomposition; it establishes neither a single bottleneck nor a performance gain.

<a id="implémentation-et-validation"></a>

## Implementation and validation

`KENSHI_PROBE_FUNCTION_TARGET=zoneRendertimeThread` replaces the single selected function. The prototype comes from ZoneManager.h: `void updateRendertimeThread(const Ogre::Vector3&)`. The original is typed `void(ZoneManager*, const Ogre::Vector3&)`; the wrapper passes the original reference, without converting it from the AI*,float prototype or modifying the argument. Resolution uses the SDK's GetRealAddress and AddHook, without a numeric RVA copied into the plugin.

The three probes remain charsUpdate, findPath, and this selection; charsUpdateUT and AI are not hooked simultaneously. The existing menu service remains unchanged. Ping advertises `zone_rendertime_thread_profiling`; generic statistics carry the actual name. Old AI/charsUpdateUT/physics aliases are null for this target. Per-call CPU disabled, creation FILETIME retained through the TLS cache; unavailable CPU values are null, not measured zeros.

**448 tests pass in 21,52 s**, native selector/bucket/depth tests pass, and v100 x64 compilation succeeds. The historical charsUpdateUT 0.8.5 report is recalculated with strictly identical results: `runtime/chars-085-compatibility-088.json`. The real MCP smoke test `runtime/zone-088-smoke.json` confirms 17 tools, three probes, the target installed, and the copy paused; the n=3600 response was compacted to 50454 bytes in this check.

The first build encountered C2011: ParticlePool is defined identically twice, in ZoneManager.h and combat/CombatClass.h. Dependency preparation compares the full bodies, then adds a shared guard. The definition and memory layout do not change; the normalized body SHA remains **c42be0620bb080a7f13cee1247ef3ba9648e075d6329e289cb9de980f0ee7404** in both files. Idempotence verified and before/after fingerprints in `runtime/sdk-particlepool-088.json`. Headers remain external and ignored by Git. The next build succeeds.

<a id="heng--pause-x1-pause"></a>

## Heng: pause, x1, pause

Raw: `runtime/scenarios/pause-cpu-20261028T115207Z.json`, completed=true, SHA-256 **54d7e190659c7fe374cc998d5c6c70f747a502d28964748fea35a1a81c51272d**. Analysis: `runtime/zone-088-analysis.json`. Game PID **37288**, Unix creation time **1793188199.0609565**, executable verified. All three function windows lie within their scene bounds; the 3600-frame context remains separate. No pytest or compilation during the phases.

| Phase | Function-window frames | Calls | Inclusive wall-time total | Mean per frame | Max call |
|---|---|---:|---:|---:|---:|
| Pause before |11356..11955|600|97,751504 ms|0,162919 ms|0,604500 ms|
| x1 |14409..15008|600|118,798499 ms|0,197997 ms|0,611200 ms|
| Pause after |17616..18215|600|98,701697 ms|0,164503 ms|0,556100 ms|

All entries belong to thread **34240 / creation FILETIME 134376618121861931**, joined by TID and creation time to OS counters and the SDK role world_ai_non_render. Zero omitted nested entries, zero thread-table overflows. All 600 CPU calls are unavailable in each window, as required by the selected mode.

| OS phase | Process duration | Mean process CPU, logical processors | Whole-thread CPU, 34240 | Simulated progression |
|---|---:|---:|---:|---:|
| Pause before |20,375 s|1,794479|1,000000 s|0 h|
| x1 |20,407 s|2,429467|6,750000 s|+0,187075 h|
| Pause after |20,344 s|1,751131|1,093750 s|0 h|

The normalized whole-thread values provided by the join use its retained bounds: approximately **0,049080 /0,330769 /0,053763 logical processor**. Those denominators may differ slightly from the process window. Signed process/thread residuals are **+0,25 /−0,109375 /0 s**, retained without clamping; one identity lacks a second boundary at x1, another during the final pause. No residual is assigned to ZoneManager.

Population is stable at 393 in the first pause, 424→451 at x1, then stable at 451. The camera is controlled during measurement; streaming and simulation can evolve between phases. No coverage ratio is calculated between the 600 function frames and twenty seconds of CPU. The function also being called in pause confirms that a role named “AI” is not exclusive AI or simulation CPU.

The expanded 3600-frame contexts retain per-call maxima of 1,185500/0,789700/0,611200 ms. They may overlap another phase: these maxima are not strictly bounded to each condition's twenty seconds.

<a id="restitution-et-suite"></a>

## Restoration and next steps

The `runtime/zone-088-final.json` check confirms the copy returned to **404,3333339691162 h**, identical to its initial reference: pause, normal camera, Edge=true, and temporary control released. **702/702/738 files** from source/copy/snapshot compliant, settings.cfg identical to the predeployment state, guards false. Fresh watchdog, zero errors, successful autoload, 17 tools/seven SDK roles/three probes, WPR inactive, no active scenario controller.

Archive: `crashes/20261028T114929424772Z-deployment-088`, after fresh verification of only the project's processes. Separate symbols under `runtime/symbols/0.8.8`: DLL SHA **b0de947a7045a94029069da2b75fa310bac21676cfcc397428615728fc36f074**, PDB **41830ac1b55e76d2b76524dd2ea2b18fb1c53e0b7401a837007ff84cd552d3a2**. Deployment modified no source save or game file.

The next candidate is **MedicalSystem::_NV_periodicUpdate()**, declared in MedicalSystem.h and already observed in a historical active stack. Its prototype is MedicalSystem* without float. It may replace the single selected function if decomposition continues, without a fourth probe. Exclusive BirdManager CPU remains unknown and its class is not declared in local headers: do not create a direct API from RTTI. Outside load is not fixed, complete NPC state is not deterministic, and no cross-version comparison establishes a gain.
