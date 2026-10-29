<a id="collecte-0820--confirmation-randomisée-avec-cpu-du-serveur-mcp"></a>

# Collection0.8.20: randomized confirmation with MCP-server CPU

**The reduction in MCP-server CPU remains undetermined.** At10 Hz, `aggregates − full` yields three positive and three negative CPU differences; at 1 Hz, the median difference in CPU seconds is zero. Native service and client latency, however, decrease in all six pairs at each frequency. At10 Hz, their median differences are **−1,93242 ms** and **−3,58830 ms**, respectively.

This randomized confirmation is accepted: **36 blocks,660 reads,330 control wakeups,no skipped slots**. It complements the [0.8.20 pilot](direct-aggregate-statistics-measurements.md) with MCP-server-only CPU. It retains the DLL and game process but observes78 loaded characters versus 106 previously, with another camera position. Concurrent activity may also vary. No FPS gain is demonstrated.

<a id="préenregistrement-vérifié"></a>

## Verified preregistration

[Preregistration](../../runtime/observer-randomized-20261028T222552055152Z/registration.json) is fixed before capture, SHA-256 **`fc972fefec0fbe94c659256aea7dced759ae0c81703cc13be729f6cf2f643103`**. It retains:

- integer randomization seed **`4337799577124482768`**, from a single64-bit draw before acquisition;
- full36-block plan, protocol `observer-overhead-randomized-v2`, version 0.8.20, and SHAs of 20 sources;
- [preregistered protocol](randomized-observer-protocol.md), SHA-256 `0402cc30da4a523b26aff2393b6a04d9afc8edf7dfa5c3b84d14351a72223f96`;
- DLL `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e` and symbol manifest `7305c48a0a7b9466c6780bbb276e973ff0d068f5017b270fa7d6039d8ee54e62`;
- Python 3.12.14, MCP 1.30.0, and psutil 7.2.2, versions recorded for this run.

The suite before preregistration reports **1143 tests passed in 41,98 s**. This validates tested software checks, not game performance. The protocol document remains unchanged after preregistration.

<a id="plan-exécuté-et-portées"></a>

## Executed plan and scopes

Each block targets5 s after a1 s neutral wait and common checks. Conditions are `baseline` without a getter, `get_frame_stats(n=60, detail='full')`, and `detail='aggregates'` at 1 or 10 Hz. All six permutations occur once per frequency; `make_plan(seed)` shuffles the 12 triads without changing internal order. Preregistration precedes the controller-declared experiment start by about 21,19 s. Replay confirms the exact plan,660 reads,330 wakeups,no catch-up/overlap,identities,bounds,and restoration. Maximum request-start lateness is **16,893 ms**.

Comparison units are the **six block pairs at one frequency**. For requests, medians are first calculated within each block, then subtracted across conditions of the same triad. Levels show the median and range of six block medians; paired comparisons retain all six differences, their median, range, and signs. Requests are not pooled as independent experiments.

Native service and MCP latency remain separate wall durations. Bytes correspond to compact result re-encoding without a transport envelope. Callback means, game-process CPU, Root, and controller remain separate diagnostics; native service is not treated as exclusive CPU.

<a id="périmètre-du-cpu-serveur"></a>

## Server-CPU scope

The MCP server persists throughout the series. Its recorded identity contains PID, creation time, executable, arguments, parent PID, and launch token. The server is **PID17160**, creation `1793226372.3372936`, through venv launcher **25292**, creation `1793226372.3123753`, child of controller **1888**, creation `1793226371.4070983`. Paths, arguments, token, and parent chain match observations. Only CPU of **the identified server process** is retained; launcher and recursive child sums are excluded.

Every block has before/after user/kernel counters, associated with server-specific QPC bounds enclosing the request window. Deltas are normalized by their own duration. Server CPU is added neither to controller CPU nor game CPU as though bounds were identical.

Quantized values and zeros are retained. A zero CPU delta does not prove no execution; no relative reduction is calculated by dividing by a zero reference. Primary comparisons favor signed differences in CPU seconds and logical-processor equivalents. Missing threads and signed game residuals remain visible without clamping or invented attribution.

<a id="cpu-serveur--niveaux-et-différences-signées"></a>

## Server CPU: levels and signed differences

Levels are the **median [minimum; maximum] of the six blocks** in each condition. CPU time is user + kernel for the server alone; logical equivalent divides each delta by that block's own interval.

| Hz | Condition | Server CPU per block, s | Logical-processor equivalent | Blocks with zero CPU delta |
|---:|---|---:|---:|---:|
| 1 | baseline | 0 [0 ; 0] | 0 [0 ; 0] | 6/6 |
| 1 | full | 0,015625 [0 ; 0,031250] | 0,003016 [0 ; 0,006043] | 2/6 |
| 1 | aggregates | 0,015625 [0,015625 ; 0,031250] | 0,003007 [0,002992 ; 0,006052] | 0/6 |
| 10 | baseline | 0 [0 ; 0] | 0 [0 ; 0] | 6/6 |
| 10 | full | 0,156250 [0,078125 ; 0,375000] | 0,030156 [0,015099 ; 0,072066] | 0/6 |
| 10 | aggregates | 0,140625 [0,093750 ; 0,171875] | 0,027128 [0,018098 ; 0,032986] | 0/6 |

Primary `aggregates − full` comparisons are:

| Hz | Server CPU delta, median [min; max], s | Negative / zero / positive signs | Logical-equivalent delta, median [min; max] |
|---:|---:|---:|---:|
| 1 | 0 [−0,015625 ; +0,031250] | 2 / 2 / 2 | −0,00001506 [−0,00303856 ; +0,00605177] |
| 10 | −0,015625 [−0,250000 ; +0,046875] | 3 / 0 / 3 | −0,00302509 [−0,04792787 ; +0,00899465] |

At1 Hz, in triad order1/2/4/6/8/10, all six deltas are **+0,031250; +0,031250; −0,015625; 0; −0,015625; 0 s**. At10 Hz, for triads 0/3/5/7/9/11, they are **+0,031250; −0,046875; −0,250000; −0,156250; +0,046875; +0,015625 s**. The highest full-response case contributes to the wide10 Hz range; signs do not support a uniform reduction.

Observed CPU deltas are quantized in multiples of **15,625 ms**. All twelve controls and two full-response1 Hz blocks have a zero delta at this resolution. This is not evidence of zero cost. Two1 Hz pairs have exactly equal CPU deltas in both conditions but slightly negative logical-equivalent differences because observation durations differ: normalization does not create a demonstrated CPU saving. No ratio using a zero control is presented.

Secondary comparisons against the control reflect the same values: at 1 Hz, `full − baseline` is positive in four pairs and zero in two, `aggregates − baseline` positive in all six. At10 Hz, both treatments are positive in all six pairs. Server measurement is now available, but reproducibly lower CPU with `aggregates` remains **undetermined in this series**.

<a id="service-client-et-volume"></a>

## Service, client, and volume

Each cell is the **median [minimum; maximum] of six block medians**. Internal medians cover five requests at 1 Hz and fifty at 10 Hz.

| Hz and response | JSON bytes per result | Native service, ms | MCP client latency, ms |
|---|---:|---:|---:|
| 1, full | 35 985 [35 971 ; 35 990] | 2,19970 [2,17190 ; 2,39420] | 11,82005 [9,96630 ; 13,73510] |
| 1, aggregates | 3 946 [3 944 ; 3 949] | 0,22715 [0,22500 ; 0,23600] | 9,03490 [7,01520 ; 10,53880] |
| 10, full | 35 986,75 [35 985 ; 35 989] | 2,16445 [2,13840 ; 2,20900] | 11,52673 [10,67140 ; 11,74630] |
| 10, aggregates | 3 945 [3 944 ; 3 947] | 0,23005 [0,22760 ; 0,24355] | 7,82847 [7,27945 ; 8,85880] |

All six `aggregates − full` differences are negative for service, client latency, and bytes at both frequencies:

| Hz | Service, median [min; max], ms | Client, median [min; max], ms | Bytes, median [min; max] |
|---:|---:|---:|---:|
| 1 | −1,97385 [−2,15820 ; −1,94170] | −2,59050 [−6,71990 ; −0,65860] | −32 038 [−32 046 ; −32 025] |
| 10 | −1,93242 [−1,98120 ; −1,90640] | −3,58830 [−4,29400 ; −1,93815] | −32 041,5 [−32 044 ; −32 039] |

Paired service reduction has a median of **89,733 % [89,216;90,143]** at 1 Hz and **89,283 % [88,961;89,688]** at 10 Hz. These are medians of six per-pair ratios, not ratios of level medians. Queue waiting varies in both directions: median difference+0,66520 ms at 1 Hz,+0,02422 ms at 10 Hz. Observed latency benefit therefore cannot be attributed exclusively to queue waiting, server CPU, or native service.

<a id="callbacks-et-cpu-du-jeu--diagnostics-distincts"></a>

## Callbacks and game CPU: separate diagnostics

Cells show **median [minimum; maximum]; positive differences out of six**. All three CPU columns are logical equivalents calculated with their respective intervals. Positive means above the indicated control.

| Hz | Treatment − reference | Game CPU | Root CPU | Controller CPU | Mean callback, ms |
|---:|---|---:|---:|---:|---:|
| 1 | full − baseline | +0,00328 [−0,13697 ; +0,25619] ; 3/6 | −0,02417 [−0,05687 ; +0,01650] ; 1/6 | −0,00136 [−0,00587 ; +0,00602] ; 3/6 | +0,01704 [−0,18684 ; +0,05138] ; 4/6 |
| 1 | aggregates − baseline | +0,06383 [−0,12909 ; +0,21813] ; 4/6 | −0,01980 [−0,06062 ; +0,02533] ; 2/6 | +0,00136 [−0,00300 ; +0,00567] ; 3/6 | +0,05464 [−0,14526 ; +0,19286] ; 4/6 |
| 1 | aggregates − full | +0,03816 [−0,28579 ; +0,35510] ; 4/6 | +0,01841 [−0,04835 ; +0,03308] ; 5/6 | +0,00134 [−0,00569 ; +0,00861] ; 3/6 | +0,09153 [−0,11550 ; +0,16230] ; 4/6 |
| 10 | full − baseline | −0,03379 [−0,10782 ; +0,14207] ; 2/6 | −0,01052 [−0,04683 ; +0,02936] ; 3/6 | +0,00901 [−0,00614 ; +0,02104] ; 4/6 | +0,16595 [+0,01911 ; +0,29687] ; 6/6 |
| 10 | aggregates − baseline | −0,08238 [−0,15657 ; +0,29956] ; 2/6 | +0,00616 [−0,04603 ; +0,04928] ; 4/6 | +0,00898 [−0,00618 ; +0,01511] ; 5/6 | +0,02283 [−0,05453 ; +0,14071] ; 3/6 |
| 10 | aggregates − full | −0,02837 [−0,18488 ; +0,31476] ; 2/6 | +0,00655 [−0,02046 ; +0,03102] ; 4/6 | −0,00002 [−0,02085 ; +0,01182] ; 3/6 | −0,13727 [−0,25105 ; −0,04645] ; 0/6 |

At10 Hz, all six pairs show a shorter mean callback with `aggregates` than `full`, while `full` exceeds the control in all six. Other CPU measurements and the 1 Hz result remain mixed. Callbacks are telemetry intervals; no conversion to displayed FPS or exclusive CPU attribution is made.

Controls themselves vary: their callback means span 6,78910–6,99519 ms at 1 Hz and 6,70610–6,93866 ms at 10 Hz. Their process CPU spans 1,56355–1,68457 and 1,50874–1,82943 logical equivalent, respectively. Pause, time, and stable inventories do not prove constant internal load. Randomization removes neither machine noise nor persistent effects between blocks; this single series provides no significance or equivalence test.

<a id="fenêtres-identités-et-restitution"></a>

## Windows, identities, and restoration

| Window | Minimum, s | Median, s | Maximum, s |
|---|---:|---:|---:|
| Requests | 5,00040 | 5,00605 | 5,01592 |
| Game CPU | 5,06206 | 5,07445 | 5,10272 |
| Root-thread CPU | 5,06684 | 5,08012 | 5,10532 |
| MCP-server CPU | 5,16076 | 5,18388 | 5,22590 |
| Controller CPU | 5,16076 | 5,18389 | 5,22592 |

Server and controller intervals are close but distinct; they are not merged. Final statistics contain **732–778 callbacks** per block, obtained in one request with n retained and within the 3600 budget. Their accumulated intervals cover5,19534–5,26985 s, with bounds different from OS counters. Final checks and re-encoding lie outside the game-CPU window; effects on the next block remain possible.

The game remains **28932 / creation `1793224737.4120193`**. Root retains **T23968 / FILETIME `134376983374120248`**, with the same export binding and service identity in every response. All110 locked scenes —108 block reads plus reference and prerelease—retain **78 loaded characters,one active city**, pause, zero multiplier, and time `404.3333339691162`. The earlier0.8.20 pilot observed106 characters: the same PID and DLL cannot make the two scenes identical.

Two OS threads, T40144 and T41080, are not observed at the final endpoint of block index5; they remain omitted. Signed process-minus-computable-thread residual ranges from **−0,375000 to+0,203125 s**, median−0,015625 s. It is retained without clamping and does not represent consumption assignable to a function.

The independent audit confirms the copy paused at the same time, camera control released, `free_camera=false`, Edge restored, settings unchanged, inactive guards, and **702/702/738 compliant files** for validation/copy/snapshot. Watchdog and helpers21020/40676 remain active under continuation authorization. MCP cleanup used no fallback (`cleanup_events=[]`); the final scene is read through direct TCP. Sources and DLL are unchanged.

The camera moved about **12,561 units before the locked reference**, then **10,786 units after release**. Stability during measurement does not mean restoration of initial coordinates. The transport audit separately records termination of server **17160**, launcher **25292**, and controller **1888**; it terminates no process. The game watchdog is not confused with these measurement processes.

<a id="preuves-et-rejeu"></a>

## Evidence and replay

| Evidence | SHA-256 |
|---|---|
| [Accepted capture](../../runtime/scenarios/observer-randomized-20261028T222614566229Z.json), 28 002 828 bytes | `3c99c2e0ec9b0b64b9c95f4aedbd1fc6df5caa4894b8235f0c4023e45391873f` |
| [Analyzed report](../../runtime/randomized-observer-seed0.json), 142 152 bytes | `ba49c0ff37ce1b479c0a999266626a5973ffc385634d1944f79bc07edb0ac31d` |
| [Two-replay evidence](../../runtime/randomized-observer-replay-proof.json) | `4000a2f5e44c256795298dbc0459f978c3601be9a2610525ccd349d81c2d5f57` |
| [Final game/file audit](../../runtime/randomized-observer-final.json) | `30b7f7ed702c4cd187123af46bee8561e60b667272864ae7a6d679bdc91c335e` |
| [Transport termination audit](../../runtime/randomized-observer-transport-final.json) | `5ca086521ffb3ee381afc95e3ceadae2addeb1f2c1b0351c468630441a4b7caa` |

Python hash seeds `0` and `8675309` produce byte-identical reports. They check replay stability without changing the randomization seed or constituting two acquisitions. Evidence retains20 source SHAs; analyzer SHA `920a930faa286ffc3816259d5b07e17a1a1f9fc0e555871ce842b2813bfb0c2e`, controller `3be16ca2a9e88bf6c51171e912259ce324c3dba483d4bc86e002813a028cf530`.

Offline replay from the project root, using a new output name; capture SHA is required and an existing file rejected:

```powershell
$env:PYTHONHASHSEED='0'
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& .\.venv\Scripts\python.exe tools/research/analyze_observer_randomized.py `
  runtime/scenarios/observer-randomized-20261028T222614566229Z.json `
  --expected-version 0.8.20 `
  --expected-sha256 3c99c2e0ec9b0b64b9c95f4aedbd1fc6df5caa4894b8235f0c4023e45391873f `
  --output runtime/randomized-observer-replay-new.json
```

The levels and differences above come from `result.blocks`, `result.paired`, and `result.paired_request_comparisons`. The external preregistration hash is checked separately from its content declared inside the capture. The conclusion remains limited: shorter service and client latency in these pairs, no reliable server-CPU reduction demonstrated, no conclusion of FPS gain or general reduction in engine cost.
