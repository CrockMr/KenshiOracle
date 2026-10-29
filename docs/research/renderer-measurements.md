<a id="original-renderer--mesures-0817"></a>

# Original Renderer — 0.8.17 measurements

Original `Renderer::_NV_update()` measures **0,819574 wall microsecond per active frame** at Heng, for **7,056608 ms** mean callback interval. This precise entry is very short in campaign; **does not measure all rendering or GPU**. No engine gain/exclusive CPU claimed. At this scale, timer/trampoline's own cost not isolated: do not treat mean as pure engine time.

<a id="sélection-et-périmètre"></a>

## Selection and scope

`rendererUpdate` replaces MainLoop selection, also disables Havok. Existing Renderer hook reused: two dedicated system detours (charsUpdate/findPath), two service detours, **four effective installations and three profiled boundaries**. No duplicate detour at same address or fourth profiled system.

Supplied signature `void Renderer::_NV_update()`, Renderer.h line 44, nonvirtual alias of virtual declaration line 43. Symbol/import `?_NV_update@Renderer@@QEAAXXZ` verified in KenshiLib.lib. Header SHA256 **49367b8a20dda80a495870ee54df655768d909607f5a327a75102b3a0af5009c**; library **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Evidence `runtime/renderer-sdk-0817.json`. No comment RVA used for binding; no game code copied.

`OriginalRendererInvocation<Renderer>` forwards same pointer, calls original once. Native test checks pointer identity, count and no call on second object; MainLoop/Renderer selectors stay distinct. Successful Renderer installation activates selection after this hook, then emits selection log.

Timer begins after heartbeat, pause protection, initial command drain and loading-state service. **Initial work excluded; any callback reached inside original remains included**, alongside waits/other nested work. `hook_source=existing_renderer_service_hook`, `leading_service_excluded=true` and explicit native scope promise neither total service exclusion nor GPU time exclusion.

Existing outermost profiler, creation TLS read once, eight-identity capacity, wall end before recording lock, per-call CPU disabled/null. Scopes may cross bucket bounds. Other probes may overlap: no exclusive sum/subtraction. Sample **696 bytes**, chars history **2523600**, older telemetry helpers/serializer unchanged.

<a id="validation-et-campagne"></a>

## Validation and campaign

**721 Python tests pass in 22,05 s**, including 16 new Renderer checks. Native v100: pointer/single call, selector separation and old floats/buckets/depth successful. v100 x64 compilation linked. Real MCP smoke checks17 tools,60 actual Renderer calls, flags, scopes, sizes/aliases. Paused cadence check **74 frames over 508,269 ms**, tail10 mean **6,944480 ms**. No slowdown like rejected 0.8.14; cause of old anomaly still unknown.

`tools/research/live_renderer.py` reloads KenshiProbe_test copy with pause protection/Edge lock, prepares Heng 10 s x1 then waits for stable readiness. Three requested 12 s windows after 3 s warmup each: pause/x5/pause. Observations requested every 0,5 s, complete inventories limit 500, OS endpoint identities. No concurrent build/benchmark during acquisition. Copy reloaded paused at trial end, camera control released.

| Phase | Frames/calls | Original mean µs/frame | Max call µs | Mean interval ms | Interval p99 ms |
|---|---:|---:|---:|---:|---:|
| Pause before | 2032/2032 | 0,781987 | 6,9001 | 6,181928 | 7,8976 |
| x5 | 1783/1783 | 0,819574 | 35,3999 | 7,056608 | 9,4361 |
| Pause after | 1886/1886 | 0,775767 | 3,9999 | 6,627360 | 8,8295 |

Native fields in milliseconds; call column converted here to microseconds (×1000). No skipped nesting, overflow or unknown Renderer thread. Equal aggregate calls/frames does not prove a call in every unshown frame: only 100 final individual rows retained.

All calls join **T29164/creation FILETIME 134376841722811107**, identity found at both CPU endpoints and game_thread/service_thread in bracketing heartbeats. **Whole-thread** CPU9,65625/10,171875/9,875 s, over OS windows12,594/12,609/12,516 s. Not Renderer-entry CPU. Process CPU22,078125/28,546875/23,203125 s, or1,753067/2,264008/1,853877 logical processors. Signed residuals+0,03125/−0,078125/−0,078125 s. Thread **T22944 not observed after** active window omitted; consumption not invented. Neither pause has omissions; Renderer thread verified in all three windows.

Original charsUpdate0/0,347020/0 ms/frame. Populations410..410/443..452/452..452; game_total_hours0/+0,57817459106451/0. State/time/population evolve; no causal comparison with another phase/version. Callbacks do not guarantee displayed FPS. CPU windows/buckets distinct; do not assign “remainder” by subtraction or convert other campaigns into additive shares.

Main requests admitted without reduction:n2032/57426 bytes,n1783/61983,n1886/57531; final stats n3600/58181. Compact re-encoded bytes, not exact TCP/MCP size; native64 KiB limit/budget plans unchanged.

<a id="preuves-et-rejeu"></a>

## Evidence and replay

Capture `runtime\scenarios\renderer-20261028T180433342866Z.json`, completed=true, SHA256 **ada3a6bd984db83f78d28ea8359f9199be794228b0517b11d9b392d5d71ff33b**. Report `runtime/renderer-0817-analysis.json`. Wrapper checks source/scope, aliases, hook count, single selection and CPU joins from raw data. Old MainLoop/chars replays checked at checkpoint.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_renderer.py runtime\scenarios\renderer-20261028T180433342866Z.json --expected-sha256 ada3a6bd984db83f78d28ea8359f9199be794228b0517b11d9b392d5d71ff33b --output runtime\new-report-renderer.json
```

DLL **304128 bytes/SHA2566a4d4735ee608503fc4ecb626b531b96efbca3a938d6298265bcf3da8a82a976**, owned PDB **10382336/SHA25607dbec057c9bb93f180de43c3484dca89bef0ef729ccb940113d01c03a0982a8**, under `runtime/symbols/0.8.17`. Archive `crashes/20261028T180240899551Z-deployment-0817`, evidence `runtime/deploy-0817.json`. Only project processes stopped, freshly verified by path/command/creation; old 0.8.16 preserved.

Audit `runtime/renderer-0817-final.json`: **PID38472/Unix creation 1793210572.281109**, copy paused/multiplier0 at 404,3333339691162 h, normal camera, temporary control released, Edge=true, battle inactive. **702/702/738 files** source/copy/snapshot compliant, settings identical to beforehand, guards false, fresh watchdog without error,WPR inactive, no remaining controller. Helpers **3644/creation1793210570.6763327** and **5464/creation1793210570.6396365**; recheck identities before stopping.

<a id="question-suivante"></a>

## Next question

Measured MainLoop/Renderer entries do not explain all main-thread activity. Previously validated user stacks pass through Ogre/KingOfRenderThread::startup; latter is a long-lived ancestor, not demonstrated CPU cost or good completed-call target if original lasts entire session. SDK also declares `KingOfRenderThread::mainloop(float)`, finite candidate to verify in symbols/observations before dedicated selection. Name proves neither frequency nor coverage. Possible selection would replace Renderer and include internal callbacks; three systems maximum. No blind probe addition, expected administrator capture or identical heavy trial without hypothesis.

Autonomous deadline **22 h15 UTC/23 h15 Paris** unchanged. No manual intervention expected.

Diagnostic follow-up: KingOfRenderThread::mainloop(float) candidate [ruled out without hook](king-mainloop-candidate.md), after entry verification in file/memory. 0.8.17 unchanged; [startup route to Ogre](main-thread-loop-route.md) resolved statically. REA reached450 s client deadline without dossier; session cleaned.
