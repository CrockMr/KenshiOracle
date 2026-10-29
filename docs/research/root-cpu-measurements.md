<a id="root--compteurs-cpu-optionnels-même-dll-0818"></a>

# Root: optional CPU counters, same 0.8.18 DLL

The existing CPU mode was enabled after an archived restart, without modifying or reinstalling the DLL. At Heng, the x5 window retains **1651 Root calls**, **7,160992 ms wall time per frame**, and a CPU-counter sum of **8531,25 ms**. These counters also bracket measurement code and nested callbacks. They provide neither exclusive engine CPU, GPU time, nor a gain over previous campaigns.

MCP retains **17 tools**, the plugin **v100 x64**, three profiled systems charsUpdate/findPath/Root, and five effective installations: three dedicated detours and two services. No new Game call or hook. The argument-free bool signature and loaded binding remain those of the [previous Root report](root-frame-measurements.md).

<a id="calibration-avant-activation"></a>

## Calibration before activation

`tools/research/benchmark_thread_cpu.cpp`, compiled by `tools/research/benchmark-thread-cpu-v100.cmd`, reads its own thread's counters; it opens no game process. Three processes each run seven repetitions of 20000 read pairs, then a scan with CPU activity limited to 500 ms. Toolset v100, x64, /O2. Before/after scenes confirm the same paused game time.

The median of 21 repetitions is **0,529625 µs per pair**, minimum **0,491300**, maximum **0,548815 µs**. This cost includes the helper's loop, conversions, and checks; it is not the complete hook cost in Kenshi. The DLL startup check separately observes **0,23 µs per read** over 200 reads; these protocols are not interchangeable.

| Helper process | Scan reads | Positive deltas | CPU sum ms | Observed positive increment ms |
|---|---:|---:|---:|---:|
| 1 | 1353891 | 31 | 484,375 | 15,625 |
| 2 | 1347331 | 32 | 500,000 | 15,625 |
| 3 | 1358541 | 31 | 484,375 | 15,625 |

All other scan deltas are zero. **FILETIME's 100 ns unit is not its precision.** The increment observed here does not guarantee resolution in the game or on another machine. A per-call zero proves no absence of CPU work; a delta exceeding that call's wall duration can result from quantization. Analyzers retain these values without clamping. The following means are sums divided by retained frame counts, without guaranteed per-frame CPU precision.

Controller: `runtime/thread-cpu-calibration/20261028T195531645597Z/controller.json`, SHA256 **dc16044be1c418673c1d69b4578c150680474fb37cfe4694f69c905bc33e425f**. Replay: `runtime/thread-cpu-calibration-analysis.json`. It checks fingerprints of both sources, the executable, and every stdout, the plan, zero/positive partitions, histograms, sums, and observed GCD. Separate executable SHA256 **e4899cb08584ac7488ec16a51957b8d3b065dc8f89d975db480f1f366db54576**, under the Git-ignored build directory.

<a id="campagne-cpu-activé"></a>

## Campaign with CPU enabled

`KENSHI_PROBE_FUNCTION_THREAD_CPU=1` is set at startup. Root selection, AI CPU disabled, Nav CPU enabled, command timing, and deadline remain unchanged. The DLL is strictly the 0.8.18 one, SHA256 **24ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**. Archive **crashes/20261028T200628106023Z-root-cpu-mode-on** preserves the previous state; `runtime/root-cpu-restart.json` records `native_dll_reinstalled=false` and identities verified before stopping.

Real MCP smoke: 60 calls, 60 counters available, none unavailable. Pre-campaign cadence: 78 frames over 513,9912 ms, last-ten mean 6,95081 ms. **796 Python tests pass in 23,70 s**; they finish before acquisition. New checks cover quantized counters, explicit CPU modes, partitions, and CPU-disabled compatibility in particular.

`tools/research/live_root_cpu.py` reloads the protected KenshiProbe_test copy, verifies the loaded module/export/address, prepares Heng for 10 s at x1, and waits for stability. It requests three 12 s windows, pause/x5/pause, after 3 s warmup each; requested observations every 0,5 s and complete inventories with limit 500. The copy is reloaded paused and the camera released during final cleanup.

| Phase | Frames/calls | Mean Root wall ms | Mean interval ms | p99 interval ms | User CPU ms | Kernel CPU ms | CPU sum ms | CPU sum / frames ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pause before | 1795/1795 | 6,843799 | 6,964272 | 11,9179 | 5656,250 | 2937,500 | 8593,750 | 4,787604 |
| x5 | 1651/1651 | 7,160992 | 7,331158 | 11,9149 | 6484,375 | 2046,875 | 8531,250 | 5,167323 |
| Pause after | 1795/1795 | 6,852462 | 6,962866 | 11,9017 | 6734,375 | 2500,000 | 9234,375 | 5,144499 |

Every call has an available counter; zero ignored nesting, overflow, or unknown identity. Wall maxima: 12,806600 / 40,236800 / 12,582600 ms. Aggregate calls=frames does not prove one call in every undisplayed frame: only the last 100 individual rows are retained. Wall durations and CPU counters have different read points; they include nested work and can cross bucket boundaries. Root/interval differences are not an overhead or wait measurement by subtraction, and offline calibration does not establish neutrality of the complete hook.

Root identity **T18372 / creation FILETIME134376915914545795** joins the main thread and render service at the boundaries, and both OS CPU endpoints. Its whole CPU is **8,984375 / 9,015625 / 9,578125 s**, over OS windows of **12,532 / 12,141 / 12,531 s**. These differ from the retained-call windows: no exclusive-coverage fraction or “remaining CPU” is inferred.

Process CPU: 18,703125 / 26,234375 / 21,796875 s, or **1,492429 / 2,160808 / 1,739436 logical processors**. Signed process-minus-computable-thread residuals: 0 / +0,0625 / +0,015625 s. No identity omitted at endpoints. Populations 397..397 / 449..454 / 454..454; game_total_hours progression 0 / **+0,5561561584472088 h** / 0. NPC states are not deterministic, and these sequences are not a CPU-enabled/disabled A/B.

<a id="rejeu-et-compatibilité"></a>

## Replay and compatibility

Complete capture: **runtime/scenarios/root-cpu-20261028T200957553841Z.json**, SHA256 **41dbf03088c48eb2a36d2adfa1c355030a9361dfb590410c2448d1fcb033924d**. Analysis: `runtime/root-cpu-0818-analysis.json`. From the root:

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_root_cpu.py runtime\scenarios\root-cpu-20261028T200957553841Z.json --expected-sha256 41dbf03088c48eb2a36d2adfa1c355030a9361dfb590410c2448d1fcb033924d --output runtime\new-report-root-cpu.json
```

Manifest **docs/research/performance-cohorts-root-cpu.json**, SHA256 **eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675**, keeps **seven cohorts and twenty-two windows** separate. Both previous manifests remain unchanged. Report `runtime/performance-cohorts-root-cpu-v1.json`, SHA256 **e66f64669f9bc060cbd1e0f12f208b659ad3e277185b66a6d438f5b3c6884896**; Markdown with the same basename.

`runtime/root-cpu-cohorts-replay-proof.json` proves byte-identical replay under seeds 0/8675309 and canonical equality of the specialized CPU analysis. Metrics for the six older cohorts remain identical. The only earlier provenance that changes is the Root analyzer source SHA, because its expected CPU mode becomes explicit; the historical report is therefore not claimed byte-identical after this source change. Specialized CPU-disabled replay remains strictly equal to the recorded result: `runtime/root-cpu-off-compatibility.json`.

<a id="audit-et-suite"></a>

## Audit and next steps

`runtime/root-cpu-0818-final.json` confirms game **37556 / Unix creation 1793217991.454578**, copy paused at **404,3333339691162 h**, normal camera, temporary control released, Edge restored, and battle inactive. The **702/702/738 files** from validation/copy/old snapshot match references; settings unchanged, two restoration guards false, fresh watchdog without error, WPR inactive, and no remaining test controller. Helpers 5948 / creation 1793217991.2477891 and 41992 / creation 1793217991.2881176; freshly verify path, command, and creation time before any stop.

This measurement makes aggregate inclusive Root CPU observable, with its limitations. The next useful campaign concerns the heavy combat scenario with the same boundary and mode, rather than a version comparison; it must retain windows, inventories, adaptive budget, restoration, and separate cohorts. No engine optimization is justified by a simple wall/CPU difference. Autonomous shutdown remains mandatory no later than **28 October at 22h15UTC**; no new acquisition may delay its preparation.
