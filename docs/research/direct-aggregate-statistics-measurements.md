<a id="construction-directe-des-statistiques-agrégées--0820"></a>

# Direct construction of aggregate statistics — 0.8.20

Version 0.8.20 avoids building the two lists omitted from the `aggregates` response. Its contract is compared with the old full construction followed by projection: **2 266 native assertions pass on198 synthetic snapshots**, with zero individual rows built on the aggregate path. Across seven nonempty benchmark cases, paired median construction-cost reduction ranges from **80,8 to 95,4 %**, and **76,1 to 92,5 %** with serialization. A real pilot of **36 blocks and 660 reads** is also accepted: aggregate service is about **88,2 % shorter than full service from the same DLL** in paired comparisons. Synthetic and real results have distinct scopes; **no FPS gain is established**.

The user canceled the previously planned shutdown at 23 h15 on28 October and authorized continued work in their presence. This resumption explains0.8.20 work after the 24-hour campaign. It does not turn historical0.8.19 measurements into validation of the new DLL.

<a id="changement-et-contrat-conservé"></a>

## Change and preserved contract

In [0.8.19](aggregate-statistics-measurements.md), `get_frame_stats(n, detail='aggregates')` built the full response, then replaced `per_frame` and `navmesh_slow_calls` with `null`. This projection reduced payload but retained construction work for subsequently discarded rows. The [paused observation pilot](observer-overhead-measurements.md) already separated native-service cost, MCP latency, CPU, and callback intervals.

The production path extracted into [`FrameStatistics.h`](../../plugin/FrameStatistics.h) retains traversal of samples, aggregates, percentiles, identities, bounds, and retention indicators. The slow-call ring is still copied under the same lock, then filtered by `completion_frame` within window bounds. In aggregate mode, code counts retained rows without building their JSON objects; it also skips `per_frame` row construction.

Helper [`setAggregateStatisticsDetail`](../../plugin/StatisticsDetail.h) produces the same explicit `null` values and three metadata fields: `mode`, `per_frame_rows_omitted`, `navmesh_slow_rows_omitted`. Counts match the rows the full response would have retained: at most100 for the individual series, at most32 for the filtered slow-call ring. They are inferred neither from total slow-call count nor ring capacity. Requested omission remains distinct from retention truncation.

Default and `detail='full'` still build historical rows. Invalid values remain rejected. No new public field, MCP tool, or system hook is needed; the registry remains at 17 tools, and the three-profiled-system limit is retained. Other statistics calculations and game algorithms are unchanged by this optimization.

<a id="oracle-natif-sur-une-même-entrée"></a>

## Native oracle on the same input

[`test_statistics_detail.cpp`](../../tests/test_statistics_detail.cpp) runs production code on project-owned snapshots, without game binary or data. [`StatisticsLegacyOracle.h`](../../tests/StatisticsLegacyOracle.h) retains historical reference construction. For every snapshot, the test checks:

- JSON byte equality between historical full response, current default, and explicit `full` mode;
- JSON byte equality between old projected response and direct aggregate construction;
- preservation of omission counts, bounds, and indicators, without modifying the snapshot;
- actual absence of construction for both row categories in aggregate mode, using test-only counters.

Cases include empty histories,1/7/99/100/101/3600 samples, multiple ring layouts and boundary filters, profiling flags/function targets, unavailable fields, and invalid counts. A boundary test includes calls completed at both endpoints and excludes those completed outside the window; `start_frame` does not replace this admission criterion.

The native evidence (local evidence, not published), SHA-256 `ed5d772af789fcd9c8e3a24a9fbc3cedeb716f3a193341222310d6e47c288642`, reports `passed=true`, **2266 assertions**, **198 snapshots**, `toolset='v100 x64'`, `same_aggregate_projection=true`, `default_full_unchanged=true`, `aggregate_detail_rows_built=0`. This equality concerns tested inputs. It measures neither in-game concurrent-call cost, contention, nor network latency.

<a id="benchmark-synthétique"></a>

## Synthetic benchmark

The completed benchmark compares four operations on the same immutable snapshot: historical full construction, current full construction, historical construction followed by projection, and direct aggregate construction. The primary comparison is the last against the preceding one, with and without JSON serialization; the full path provides a regression control.

[`benchmark_statistics_detail.cpp`](../../tools/research/benchmark_statistics_detail.cpp) covers empty history, lightly loaded Root histories of 60/100/600/3600 samples, and three dense cases with complete/filtered retention or a wrapped ring. It times object construction/destruction, plus serialization in the mode enabling it. Equality checks remain outside the timed section. Operations rotate through shifted order on each repetition after warmup; every measurement block contains40 operations, every process seven repetitions.

Three processes run this plan, giving **21 block pairs per case and mode**. Durations below are medians of these 21 per-operation measurements; each measurement is block time divided by 40. Reduction is calculated within each pair as `(old projected − direct) / old projected`, then summarized by median and range. It is not the ratio of both duration medians; 21 pairs are not 21 independent sessions.

**Construction and destruction, without serialization:**

| Synthetic case | Old projected, ms | Direct aggregate, ms | Paired reduction: median [min; max] |
|---|---:|---:|---:|
| Empty | 0,004883 | 0,004420 | 6,10 % [−32,57 ; 41,59] |
| Lightly loaded Root,60 frames | 1,80597 | 0,12971 | 92,68 % [91,55 ; 94,07] |
| Lightly loaded Root,100 frames | 3,06511 | 0,13978 | 95,45 % [94,60 ; 96,24] |
| Lightly loaded Root,600 frames | 3,02749 | 0,17257 | 94,48 % [93,20 ; 95,35] |
| Lightly loaded Root,3600 frames | 3,16588 | 0,30838 | 90,26 % [89,52 ; 91,13] |
| Dense,600 frames,32 retained calls | 4,44731 | 0,52664 | 88,05 % [86,49 ; 89,31] |
| Dense,600 frames,mixed retention | 3,74257 | 0,51138 | 86,30 % [82,23 ; 87,00] |
| Dense,3600 frames,wrapped ring | 4,69431 | 0,91326 | 80,78 % [76,34 ; 84,11] |

**Same operation with JSON serialization:**

| Synthetic case | Old projected, ms | Direct aggregate, ms | Paired reduction: median [min; max] |
|---|---:|---:|---:|
| Empty | 0,008123 | 0,007880 | 4,03 % [−39,77 ; 35,55] |
| Lightly loaded Root,60 frames | 1,86915 | 0,23941 | 87,51 % [84,79 ; 89,83] |
| Lightly loaded Root,100 frames | 3,16315 | 0,23384 | 92,51 % [91,56 ; 93,71] |
| Lightly loaded Root,600 frames | 3,17588 | 0,27110 | 91,57 % [90,10 ; 92,03] |
| Lightly loaded Root,3600 frames | 3,27643 | 0,40498 | 87,76 % [85,91 ; 88,87] |
| Dense,600 frames,32 retained calls | 4,76497 | 0,83076 | 82,15 % [80,08 ; 84,04] |
| Dense,600 frames,mixed retention | 4,01855 | 0,83626 | 79,40 % [75,84 ; 81,08] |
| Dense,3600 frames,wrapped ring | 5,09343 | 1,23052 | 76,05 % [74,38 ; 81,48] |

Nonempty cases show reductions in every observed pair in both modes. The empty case remains a few microseconds and its range crosses zero; it provides no stable reduction. JSON sizes before/after this optimization are identical for every input: direct aggregate is 3296 bytes for the lightly loaded n60 case, up to 7714 for dense n3600. Payload reduction was already achieved in 0.8.19; this experiment isolates avoided construction work.

The report also retains `legacy_full` and `direct_full` durations, whose differences are much smaller and change sign across repetitions. No equivalence threshold was defined to assert general absence of a full-mode performance regression. Content equality relies on the oracle, not a timing result.

The benchmark manifest (local evidence, not published), SHA-256 `09c4f85902cd63b2cbef4fc2061404e57c3efac5f904e01ac8a13f7aab7e3825`, attests `completed=true` and unchanged sources/executables. It references all three raw files, the oracle, and summary (local evidence, not published), SHA-256 `b4df19dcdd49558826ca1a5c8c7b3eb6dc7ea2ddb2307201518a7e701c2c2ce3`. The v100 x64 benchmark SHA-256 is `6b07804c90a9dd1246b4f855f59466a55356d3732621d023c04131667294df02`; the oracle executable is `d129c9704248ef13acce8e063c02b85f5fe83bbe20ba874eeed6c24699dc6b1e`. Measurements took place on28 October, from 21:54:59 to 21:57:35 UTC.

Reduced wall duration in a synthetic helper is not an equivalent gain for the complete in-game service: the benchmark includes neither IPC, concurrent mutation, real lock contention, nor rendering. Test samples do not reproduce gameplay's work distribution. History traversal/sorting, other aggregates, and ring copying still execute.

<a id="mesures-réelles-et-limites-restantes"></a>

## Real measurements and remaining limitations

The main v100 x64 build produced a **322 560-byte** DLL, SHA-256 `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e`, and corresponding PDB SHA-256 `36a13b93e3e380fe505e159fbb1d696525a6ffdbdf1178c6f3625c745481045d`. The Python suite preceding capture reports **1023 tests passed in 31,62 s**.

The real preflight (local evidence, not published), SHA-256 `7650c1a6b67e4c111337ec65e2880ee28c397ad5d99b0492d233bd9fa8075fa5`, is complete: version 0.8.20, Root profiled, three systems and five hook installations, process `28932` created at `1793224737.4120193`. Validation/copy saves and old snapshot retain their **702/702/738 manifest-compliant files**; settings unchanged, restoration guards inactive, copy paused at `404.3333339691162 h`, camera control released, and Edge restored. The watchdog resumed the copy without autoload error, with `session_until=null` and bootstrap explicitly `unlimited` under the new authorization.

The accepted pilot retains the observation plan: three conditions, six triads per frequency,5 s blocks,1 s preceding neutral wait, same deterministic permutations, and separate bounds from the [protocol](observer-overhead-protocol.md). All36 blocks contain660 requests, without skipped slots or early starts. Maximum observed start lateness is 16,695 ms. All108 scene reads show **106 loaded characters and one active city**, effective pause and identical time; camera stable under lock. All660 responses retain the same Root binding and service identity `23968 / 134376983374120248`.

The0.8.19 pilot had78 loaded characters and a different camera position. Successive sessions therefore are not a same-scene version A/B. The following comparisons are **within 0.8.20**.

<a id="réponses-et-service-en-jeu"></a>

### In-game responses and service

For every block, calculate the median of 5 requests at 1 Hz or 50 requests at 10 Hz. The table then gives the **median [minimum; maximum] of six block medians**, without pooling all requests as independent replications.

| Hz and response | JSON bytes per result | MCP client latency, ms | Native service, ms |
|---|---:|---:|---:|
| 1, full | 35 922,5 [35 862 ; 35 930] | 12,1784 [8,6932 ; 14,7817] | 2,15375 [2,04570 ; 2,26980] |
| 1, aggregates | 3 940,5 [3 936 ; 3 943] | 8,6749 [6,3356 ; 8,9175] | 0,24415 [0,23860 ; 0,27350] |
| 10, full | 35 923,5 [35 886 ; 35 926,5] | 12,1064 [11,2941 ; 13,2945] | 2,11280 [2,05670 ; 2,16130] |
| 10, aggregates | 3 942,25 [3 941 ; 3 943] | 8,8139 [7,8807 ; 8,9369] | 0,24803 [0,24180 ; 0,26025] |

Differences are calculated between block medians of the same triad, `aggregates − full`:

| Hz | Service, median [min; max], ms | Paired service reduction | Client latency, median [min; max], ms |
|---:|---:|---:|---:|
| 1 | −1,89150 [−2,03120 ; −1,79980] | 88,195 % [87,588 ; 89,488] | −3,74695 [−6,69690 ; +0,00920] |
| 10 | −1,86487 [−1,91935 ; −1,79645] | 88,182 % [87,346 ; 88,805] | −3,83698 [−4,51255 ; −2,35725] |

Service decreases in all six pairs at each frequency. Client latency decreases in five of six pairs at 1 Hz and all six at 10 Hz. Queue waiting varies in both directions; median differences are−0,614 ms and−0,307 ms. Bytes are those of the compact-JSON-re-encoded result, without MCP/TCP envelope. Native service is a wall duration excluding network serialization and transport in particular; it is not exclusive CPU.

<a id="cpu-et-callbacks--comparaison-appariée"></a>

### CPU and callbacks: paired comparison

Each cell shows **median [minimum; maximum]; positive differences out of six**. CPU values are logical-processor equivalents calculated with each counter's own duration; positive means consumption above the indicated control. Callback duration is the mean over its retained window, not CPU or displayed FPS.

| Hz | Treatment − reference | Game CPU | Root-thread CPU | Controller CPU | Mean callback, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | +0,11971 [−0,20589 ; +0,18384] ; 5/6 | −0,00189 [−0,03249 ; +0,06435] ; 3/6 | +0,00304 [−0,00008 ; +0,00602] ; 4/6 | +0,05039 [−0,13860 ; +0,25479] ; 5/6 |
| 1 | aggregates − baseline | −0,02390 [−0,26433 ; +0,18868] ; 3/6 | +0,01922 [+0,00084 ; +0,04576] ; 6/6 | +0,00297 [−0,00294 ; +0,00884] ; 4/6 | +0,02229 [−0,06156 ; +0,31443] ; 4/6 |
| 1 | aggregates − full | −0,08986 [−0,43036 ; +0,06855] ; 2/6 | +0,00332 [−0,01860 ; +0,04987] ; 3/6 | −0,00007 [−0,00895 ; +0,00891] ; 1/6 | −0,02352 [−0,09470 ; +0,16971] ; 3/6 |
| 10 | full − baseline | +0,08573 [−0,02812 ; +0,25000] ; 5/6 | +0,02053 [−0,01283 ; +0,09458] ; 5/6 | +0,01500 [+0,00586 ; +0,02730] ; 6/6 | +0,11715 [+0,02844 ; +0,15663] ; 6/6 |
| 10 | aggregates − baseline | −0,01876 [−0,09332 ; +0,05265] ; 3/6 | +0,03701 [−0,01067 ; +0,05171] ; 5/6 | +0,00764 [−0,00283 ; +0,01232] ; 5/6 | +0,11369 [−0,15103 ; +0,38784] ; 4/6 |
| 10 | aggregates − full | −0,10886 [−0,30774 ; +0,01811] ; 1/6 | −0,01585 [−0,04287 ; +0,04914] ; 2/6 | −0,00600 [−0,02417 ; +0,00645] ; 2/6 | −0,01812 [−0,30766 ; +0,26793] ; 2/6 |

At10 Hz, all six `full − baseline` comparisons again show longer callback intervals. `aggregates − full` comparisons remain mixed for callbacks and CPU despite consistent service reductions. Process CPU decreases in five of six10 Hz pairs, but this small series establishes neither significance, causality, nor universal benefit. The control remains instrumented, and balanced order is not randomized.

Scopes are distinct: request blocks **5,00048–5,01641 s**, process counters **5,06754–5,10665 s**, Root thread **5,06903–5,11832 s**, controller **5,13599–5,19429 s**. Aggregate windows contain **694–745 callbacks**, all obtained in one request with n retained and below the 3600 cap; accumulated intervals range from **5,13974 to 5,19686 s**. Endpoints and their serialization are outside the game-CPU window, without excluding effects on the next block.

Separate MCP-server CPU remains unavailable, so controller CPU is not the full collection cost. Seven threads are not observed at the final endpoint of five blocks, while Root remains identified. Signed process-minus-computable-thread-sum residual ranges from **−0,203125 to+0,21875 s**. It is retained without clamping or attribution to a function. Quantized counters, sequential reads, and machine variation prevent confusing these values with service wall duration.

<a id="restitution-et-preuves-réelles"></a>

### Restoration and real evidence

The independent final audit (local evidence, not published) is complete: same process `28932`, three final paused readings at the same time, `free_camera=false`, control released, and Edge restored to `true`. All **702/702/738 files**, settings, and guards are compliant. Both identified helpers `21020 / creation 1793224737.2479062` and `40676 / creation 1793224737.2090707` are present; watchdog fresh, without autoload or publication error. These identities describe the audit and require fresh verification before any future stop.

Observed camera displacement before lock, after release, and between all three final reads is zero in this acquisition. The controller still does not explicitly restore initial coordinates: this point result promises no absence of drift on a later return to Edge. Controller-owned sources, DLL, and protected files are unchanged during capture.

| Real evidence | SHA-256 |
|---|---|
| Accepted capture (local evidence, not published), 27 912 370 bytes | `f387e96e312fbc0babef82e03b7683d4c934451468abef99cc74a06cb2db6649` |
| Analyzed report (local evidence, not published), 94 394 bytes | `4b696a62b6b5fbcbfbefefcd2745fa565b7794ba0a6de762f418143ca9f1b34a` |
| Two-replay evidence (local evidence, not published) | `8e73dd1f7a55338c4492ec07800a1f9c8fde9449ede910059d4e78f1d0ce5425` |
| Additional checks and request pairs (local evidence, not published) | `2bb68f954386fe0646eea9d70c43e3b5a4b2493e3f257a1da6791af4f2e78c7a` |
| Final audit (local evidence, not published) | `45295a9b29f8c89518f5a3d05d86dd020d26835491124afb29452b2d4545ec1f` |

Python seeds `0` and `8675309` produce the same report byte for byte. These are two analyses of the same raw data, not two acquisitions. Replay evidence retains source SHAs used, including controller `f457732bf39ffffd2b0a68f76b78a9fdb5211a8eeefc29f1729f88e52c7fa33f` and analyzer `0c1285da87bc2e0ea88cacc74e90fcbb0ea69ae7405b0335dd40b918a0a18d2e`.

To replay analysis offline from the project root, choose a new output name. Capture SHA is checked, version must explicitly be0.8.20, and an existing output file is not overwritten:

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe tools/research/analyze_observer_overhead.py `
  runtime/scenarios/observer-overhead-20261028T220047030270Z.json `
  --expected-version 0.8.20 `
  --expected-sha256 f387e96e312fbc0babef82e03b7683d4c934451468abef99cc74a06cb2db6649 `
  --output runtime/observer-0820-replay-new.json
```

The benchmark proves reduced construction work on tested snapshots; the real pilot confirms shorter aggregate than full service from the same DLL in pause. Scene differences from 0.8.19, absence of randomization, separate windows, and missing MCP CPU remain explicit. No FPS gain or general engine-CPU reduction is inferred from these results alone.
