<a id="cpu-en-pause-et-à-x1-dans-une-même-ville"></a>

# CPU in pause and at x1 in the same city

The native **pause / x1 / pause** sequence near Heng consumes respectively **1,835; 2,353; 1,792 mean logical processors**. CPU therefore does not disappear in pause. The thread shared by GameWorld and Renderer remains near 0,8 in all three phases; two other threads consume substantially more at x1. Their functions remain unknown: this recording does not turn residual CPU into rendering cost, or the difference into exclusive simulation cost.

Plugin **0.7.5, v100 x64, 17 MCP tools and three unchanged system hooks**. No redeployment, process stop, or video setting change. Ownership of the managed snapshot is retained.

<a id="preuves-et-reproduction"></a>

## Evidence and reproduction

- Raw: `runtime/scenarios/pause-cpu-20261028T041739Z.json`, SHA-256 **200b5b7da382777c5b50cfc8c175c4df079300c5ee0e041baf9ab85a32a5ad40**.
- Analysis: `runtime/pause-cpu-analysis.json`, with raw-data fingerprint and thread matching by TID and creation FILETIME.
- Final check: `runtime/scenarios/pause-cpu-075-final.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_pause_cpu.py
& ./.venv/Scripts/python.exe tools/research/analyze_pause_cpu.py runtime/scenarios/pause-cpu-20261028T041739Z.json
```

The collector uses an actual MCP stdio session for every command. It reloads KenshiProbe_test, prepares Heng, allows ten seconds at x1, then waits for three seconds of stable readiness. The same scene and view are retained across all three phases without an intermediate reload. Each activation is followed by three seconds of stabilization, then a requested twenty-second CPU recording, with a scene read every 0,5 second. Activation and this stabilization lie outside the CPU interval. 500-row inventories bracket each phase; no test suite runs during these intervals.

<a id="résultats"></a>

## Results

| Phase | Process CPU seconds | Actual enclosing CPU duration | Mean logical processors | Clock progression | Population during observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pause before | 37,531250 | 20,453 s | 1,835000 | 0 h | 398–398 |
| Simulation x1 | 47,968750 | 20,390 s | 2,352563 | 0,186874 h | 417–429 |
| Pause after | 36,593750 | 20,422 s | 1,791879 | 0 h | 429–429 |

The mean of both paused rates represents **77,08 %** of the x1 rate. The descriptive x1-minus-mean-pause difference is **+0,539123 logical processor**; the second pause is 0,043121 below the first. There is only one interval per phase, at successive times and with a different population. No confidence interval, marginal character cost, optimization gain, or causal decomposition of this delta is established.

All 120 thread identities are matched in each interval, with no omissions, and are shared across the three phases with the same creation time. OS boundary reads take 63 to 79 ms. Process-minus-thread-sum residuals are **−0,093750; −0,156250; −0,015625 CPU second**, retained without normalization. Counters are quantized and thread readings sequential. Scene-to-scene durations and CPU-counter durations differ slightly; both are retained.

<a id="threads-à-investiguer"></a>

## Threads to investigate

Each thread's whole CPU rate, divided by its phase's process interval:

| TID | Observed role | Pause before | x1 | Pause after |
| --- | --- | ---: | ---: | ---: |
| 35716 | GameWorld and Renderer service | 0,785337 | 0,809987 | 0,798771 |
| 37324 | Unattributed function | 0,005348 | 0,317251 | 0,000765 |
| 39984 | Unattributed function | 0,045837 | 0,294262 | 0,052027 |
| 32072 | Unattributed function | 0,173416 | 0,150962 | 0,171384 |

The first is counted only once despite its two roles. TIDs are bound here to creation times, not treated as persistent identities after restart. Workers 37324 and 39984 are priority targets for stack attribution; naming them physics, AI, or navigation from this contrast alone would be premature. Other applications' load remains uncontrolled and unquantified.

No retained slow call completes within the three phases' CPU bounds; the 3600-frame contexts are not truncated in this capture. This provides no navigation-worker identity for those phases. The role's absence from the groups does not mean zero navigation CPU.

The final **600-frame** windows, separate from CPU intervals, contain **0 / 55 / 0 completed findPath calls**, with mean frame intervals of **6,534 / 7,154 / 6,769 ms**. They are inside their phases' scene bounds but end a few frames after the end-of-CPU heartbeats; the report states this explicitly. These numbers do not summarize the entire twenty seconds and cannot identify the other threads' work.

<a id="qualité-de-scène-et-limites"></a>

## Scene quality and limitations

Pause, multiplier, and camera pass checks at every observation. The clock is frozen in both pauses and advances at x1. Boundary inventories are complete in all three phases. Within each pause, labels, multiplicities, and positions are identical before/after. The x1 inventory changes from 417 to 429 and the clocks differ: the analysis rejects an exhaustive roster difference for this non-atomic phase. Population also changed during stabilization before x1; the protocol retains that fact.

Pause does not guarantee that all engine or loaded-module work stops. Conversely, a thread whose CPU increases at x1 may execute several types of work. The sequence helps prioritize observations, not select a system rewrite already. Hook timings remain inclusive, and simulation, rendering, waits, and streaming are not isolated here.

<a id="validation-et-état-laissé"></a>

## Validation and final state

**182 Python tests pass in 4,06 s**: phase guards, clocks, invalid counters, process change, signed contrasts, and thread matching without inventing zero for a missing thread. Native data attest execution; synthetic tests verify processing.

The initial copy is reloaded paused, with the normal reference camera, Edge scrolling=true, no active tracked combat or temporary control. Source/copy and preferences are preserved; the final check also verifies the separate snapshot. Watchdog and final deadline remain unchanged at **28 October22 h15 UTC**.

The administrator CPU-stack pilot is still pending. A separate lead, consulted only in official documentation, is the start-procedure metadata exposed by [PSS_THREAD_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_thread_entry). A start procedure is not the currently executing stack. [PSS flags](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags) distinguish thread inventory, context, and memory copy; no PSS, context, or clone capture was performed here. Check utility and permissions before implementation; do not present this lead as a CPU trace or attribution already obtained.

Separate follow-up: thread-start-metadata.md later describes a PSS capture limited to metadata, validated on helpers and then performed on the paused game. Both workers share an MSVCR100 entry; their function is unresolved. This later read is not part of the CPU intervals above and does not turn them into a profile of executed modules.
