<a id="coût-de-collecte--pilote-en-pause-avec-kenshiprobe-0819"></a>

# Collection overhead: paused pilot with KenshiProbe 0.8.19

The accepted pilot contains **36 blocks, 660 MCP reads and no skipped deadline**. At 10 Hz, full mode is associated with a longer mean callback interval than the control in all six triads: median difference **+0,10936 ms**, range **+0,06101 to +0,41160 ms**. Game CPU fluctuates in both directions. Aggregate mode reduces responses from about 36 kB to 3,95 kB; this pilot does not establish a CPU or callback advantage. These observations concern a single paused session, with no conclusion about FPS gains, causality or statistical significance.

<a id="acquisition-et-état-contrôlé"></a>

## Acquisition and controlled state

The [protocol](observer-overhead-protocol.md) uses the 17 existing tools, the same 0.8.19 DLL and the same settings. Each triad contains a control without a getter during the block (`baseline`), five or fifty `get_frame_stats(n=60, detail='full')` reads, and the same number of `detail='aggregates'` reads. Frequencies are 1 and 10 Hz; each has six triads covering all six permutations of the three conditions. Order is deterministic and balanced, **not randomized**. The six pairs per comparison are the analysis units; requests are not treated as 660 independent replications.

Each block targets 5 s. The recorded controller schedules **1 s of neutral waiting without a command** before shared scene and heartbeat reads. This is not a 2 s warm-up in the condition being studied. The protocol text was aligned with that controller plan; raw metadata describes the wait actually performed. Final checks and statistics remain outside game CPU collection, but a carryover effect on the next block cannot be excluded.

All 108 block scene reads show **78 loaded characters, 1 active town**, effective pause, zero multiplier and simulated time `404.3333339691162`. The tracked battle is inactive. Camera center and position match the reference taken after locking, through the check before release. Stable inventories and positions do not prove identical internal activity or machine load across blocks.

The process remains PID `32156`, creation `1793219931.5380297`, executable `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe --norestart`. The Root thread is joined by TID `18784` and creation `134376935315380313`. The DLL retains SHA-256 `796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3`, with three system hooks and two existing service hooks. No additional hook or tool was added for this measurement.

<a id="volumes-et-latences"></a>

## Volumes and latencies

For each read block, first calculate the median of its 5 requests at 1 Hz or 50 requests at 10 Hz. The table then shows **the median [minimum; maximum] of the six block medians**. It does not pool requests from multiple blocks into one distribution. The control makes no statistics request during its window and therefore has no corresponding latency.

| Frequency and response | JSON bytes per result | MCP client latency, ms | Native service, ms | Queue wait, ms |
|---|---:|---:|---:|---:|
| 1 Hz, full | 35 985 [35 974 ; 35 990] | 11,769 [9,383 ; 15,285] | 2,230 [2,119 ; 2,412] | 3,078 [1,424 ; 6,054] |
| 1 Hz, aggregates | 3 946 [3 943 ; 3 948] | 9,703 [7,997 ; 12,326] | 2,346 [2,186 ; 2,447] | 2,969 [1,286 ; 4,568] |
| 10 Hz, full | 35 989 [35 985,5 ; 35 991] | 11,791 [10,901 ; 12,850] | 2,204 [2,178 ; 2,218] | 3,590 [2,940 ; 4,741] |
| 10 Hz, aggregates | 3 944,75 [3 942 ; 3 946] | 11,110 [9,558 ; 11,846] | 2,251 [2,222 ; 2,381] | 4,252 [2,990 ; 5,058] |

Bytes come from compact JSON re-encoding of the received result, without the transport envelope. The observed reduction is about **89 %**. Across the six paired `aggregates − full` differences, median volume change is −32 039,5 bytes at 1 Hz and −32 045 bytes at 10 Hz; all twelve differences are negative.

At 10 Hz, all six paired client-latency differences are negative: median **−0,890 ms**, range −1,838 to −0,624 ms. Native service is nevertheless longer in all six pairs: median **+0,04975 ms**, range +0,01710 to +0,18360 ms. At 1 Hz, client latency decreases in five of six pairs, median −1,190 ms and range −6,213 to +0,256 ms; service increases in five of six, median +0,05800 ms and range −0,21170 to +0,24890 ms.

These different scopes prevent presenting reduced client latency as faster statistics computation. [Aggregate mode](aggregate-statistics-measurements.md) still builds the complete response before replacing two lists with `null` and their omission counts. [Native service](command-service-measurements.md) measures wall time for execution, response assignment and logging; it notably excludes telemetry attachment, network serialization and client transport. It is not exclusive CPU time.

<a id="différences-appariées-de-cpu-et-de-callbacks"></a>

## Paired CPU and callback differences

Each cell gives **median [minimum; maximum]; number of positive differences out of 6**. A positive value means treatment exceeds its reference. CPU is in logical-processor equivalents: CPU seconds divided by each counter's own duration, without normalization to the machine's core count. The callback metric is the statistics window's mean, not exclusive `Root::renderOneFrame` duration.

| Hz | Treatment − reference | Game-process CPU | Root-thread CPU | Controller CPU | Mean callback interval, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | −0,02756 [−0,12738 ; +0,21217] ; 2/6 | +0,02337 [−0,00265 ; +0,03897] ; 5/6 | +0,00003 [−0,00300 ; +0,00601] ; 4/6 | +0,00143 [−0,62351 ; +0,32596] ; 3/6 |
| 1 | aggregates − baseline | +0,06267 [−0,20039 ; +0,15313] ; 4/6 | +0,00017 [−0,02516 ; +0,04654] ; 3/6 | +0,00154 [−0,00298 ; +0,00606] ; 5/6 | −0,02837 [−0,86700 ; +0,19846] ; 2/6 |
| 1 | aggregates − full | −0,06221 [−0,12490 ; +0,16640] ; 2/6 | −0,01589 [−0,05673 ; +0,00757] ; 2/6 | +0,00004 [−0,00600 ; +0,00886] ; 5/6 | −0,03417 [−0,30468 ; +0,51289] ; 3/6 |
| 10 | full − baseline | −0,04393 [−0,13168 ; +0,32913] ; 2/6 | +0,01448 [−0,06026 ; +0,03720] ; 5/6 | +0,01048 [+0,00001 ; +0,02089] ; 6/6 | +0,10936 [+0,06101 ; +0,41160] ; 6/6 |
| 10 | aggregates − baseline | −0,03129 [−0,22045 ; +0,13930] ; 3/6 | +0,01903 [−0,03693 ; +0,02574] ; 5/6 | +0,01062 [+0,00296 ; +0,02122] ; 6/6 | +0,09692 [−0,00677 ; +0,48892] ; 5/6 |
| 10 | aggregates − full | −0,04950 [−0,22895 ; +0,15060] ; 2/6 | +0,00476 [−0,02463 ; +0,02334] ; 3/6 | −0,00290 [−0,00895 ; +0,01229] ; 2/6 | −0,06507 [−0,31314 ; +0,42791] ; 2/6 |

In triad order at 10 Hz, the six `full − baseline` callback differences are **+0,081783 ; +0,411605 ; +0,079408 ; +0,061012 ; +0,136937 ; +0,227934 ms**. For `aggregates − baseline`, they are **−0,006773 ; +0,098469 ; +0,241582 ; +0,488924 ; +0,095362 ; +0,074112 ms**. This signal justifies treating collection frequency as a measurement variable. The advantage of `aggregates` over `full` remains mixed: at 10 Hz, four callback differences are negative and two positive, with a range widely crossing zero.

The control itself varies: its mean callbacks range from 7,346 to 8,585 ms at 1 Hz, and 7,384 to 7,975 ms at 10 Hz. Its process CPU ranges respectively from 1,327 to 1,768 and 1,553 to 1,725 logical equivalents. Balanced design and pairing eliminate neither this variability nor the possible effect of deterministic order. Game CPU differences do not prove a reduction of its overall cost.

<a id="bornes-calendrier-et-limites"></a>

## Boundaries, scheduling and limits

| Measured scope | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Request block, s | 5,00088 | 5,00774 | 5,01571 |
| Process CPU counters, s | 5,06265 | 5,07171 | 5,09359 |
| Root-thread CPU counters, s | 5,06310 | 5,07651 | 5,11488 |
| Controller CPU counters, s | 5,12392 | 5,14111 | 5,18001 |
| Retained callback count | 600 | 657 | 706 |

All 36 callback windows were obtained with one aggregate request each, preserving their requested n without exceeding the 3600 budget. Their cumulative intervals range from about 5,126 to 5,184 s. These are rolling bucket windows, distinct from CPU intervals and the request window; aggregate data cannot individually subtract every callback near auxiliary checks.

Accepted scheduling uses `perf_counter`, declared implementation `QueryPerformanceCounter()`, monotonic, non-adjustable, declared resolution `1e-7 s`. The waiting loop rechecks the deadline after every wake. All 660 request starts follow the plan without catch-up, overlap or skipping; maximum observed lateness is **16,485 ms**. The control retains 330 recorded wakes. Fine declared resolution does not guarantee equivalent scheduler or CPU-counter precision.

CPU of the **separate MCP server is unavailable**: the adapter does not supply its process identity. Controller CPU therefore does not represent the complete cost of collection. It includes its work over an interval slightly wider than the block, while encoding and final endpoints remain outside the game CPU window. The control retains the plugin, watchdog, hooks, shared endpoints and timer wakes; it is not an uninstrumented reference.

Two OS omissions are retained: thread `33092` not observed after block 2, and thread `42992` not observed before block 3, with zero-based indices. The Root thread remains identified. The signed process-minus-observed-thread-sum residual ranges from **−0,53125 to +0,125 s**; it is neither clamped to zero nor presented as CPU attributable to a function. Sequential reads, counter quantization and machine noise remain limits, as in the [Root CPU report](root-cpu-measurements.md).

The series supplies no significance test, equivalence margin, stationarity proof or extrapolation to an active scene or combat. Confirmation requires a new independent series, documented randomized order, MCP server identity/CPU and explicit carryover control. A campaign after October 28, 2026 at 22:15 UTC requires new authorization.

<a id="essais-rejetés-et-restitution"></a>

## Rejected trials and restoration

Two raw files remain separately archived and excluded from comparisons:

- `observer-overhead-20261028T210549980627Z.json` (local evidence, not published), SHA-256 `3f6978934f9690f31552f53b12d274345b387b243862a9cbed29c4e9393b0eb8`: stopped before any measurement, **0 measured blocks**, because the camera moved between the initial read and locking. The reference is now taken after stabilization under lock; the final position check precedes release.
- `observer-overhead-20261028T211140302156Z.json` (local evidence, not published), SHA-256 `cb91beb08dd13b863d9aa2d57788e4bf52acb2a102269d75ebd0ba38d86281c0`: controller declared completion, but strict replay rejected **72 early wakes or starts**, up to **13 ms**. The early-wake evidence (local evidence, not published) is retained. The old `time.monotonic` based on `GetTickCount64`, with declared resolution 15,625 ms, was replaced with QPC and rechecking waits. Old timestamps are neither converted nor mixed with the accepted pilot.

At accepted-pilot exit, the copy remains paused at the same time; `free_camera=false`, camera control released and initial Edge setting restored to `true`. Protected saves, including `KenshiProbe_validation`, the copy and snapshot, are checked against their manifests; pilot-specific settings, DLL and sources are unchanged. Both restoration guards remain `false` before and after.

**Initial camera coordinates are not restored.** Movement between the initial reading and locked reference is about 12,732 units; movement observed after release is about 18,501 units. Stability is established during locked reads through `pre_release_scene`, not after Edge restoration. This distinction also appears in the analyzer's limits.

After this campaign, Computer Use moved the pointer back onto an empty area of the already open RE_Kenshi panel. Three reads one second apart find the camera stable, with no lock held, Edge=true and pointer `(639,354)` in the window. The supplementary evidence (local evidence, not published) rechecks the 702/702/738 files, settings and pause. This is a post-acquisition check, not a modification or retroactive validation of the campaign's visual conditions.

The same evidence directly verifies all 108 counts of 78/1 and constancy of Root/symbol/address/service identity across all 660 responses. These checks supplement generic replay: its contract does not yet enforce those two invariants in every future capture.

<a id="preuves-et-rejeu-hors-jeu"></a>

## Evidence and replay outside the game

The final validation suite reports **992 passing tests in 31,94 s**. Sources of the controller, analyzer, relevant helpers and their tests are frozen in `runtime/observer-sources-20261028T212056197Z` (local evidence, not published). The analyzer used has SHA-256 `c5aa755acf16be898e4c0b6ac5e073a3b3c905293726fc22d28eaa0c8355c628`; the controller `46b47e83017c6c5b3f7f953795dc91aebea26c937cf8351718f66b0bf18e8f76`.

| Evidence | SHA-256 |
|---|---|
| Accepted raw capture (local evidence, not published), 27 917 268 bytes | `f6000a1c50ad1495b34419f33c2ae8dd9bc0cea0c0a74a01a7f20e6f715f11da` |
| Analyzed report (local evidence, not published), 93 918 bytes | `bb355fb729cf59be9724eb1741b9ecf0e98d56438c96c81162a905552e18df05` |
| Evidence of both replays (local evidence, not published) | `c6022ad33e1e204a383be0e675b6696776588bb981eeb4c1ebc3a5549a7bee75` |

Python seeds `0` and `8675309` produce byte-identical reports. This validates reproducibility of analysis on the same raw capture; these are not two new acquisitions. To rerun analysis only from the project root, choose a **new output name**: exclusive creation rejects overwriting.

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe tools/research/analyze_observer_overhead.py `
  runtime/scenarios/observer-overhead-20261028T212059381502Z.json `
  --expected-sha256 f6000a1c50ad1495b34419f33c2ae8dd9bc0cea0c0a74a01a7f20e6f715f11da `
  --output runtime/observer-overhead-replay-new.json
```

The raw SHA is verified before analysis. Comparisons above can be recalculated from `result.blocks` and `result.paired` in the report; additional paired latencies use per-block medians from `blocks[].requests` in the raw capture. This replay needs no new game launch.
