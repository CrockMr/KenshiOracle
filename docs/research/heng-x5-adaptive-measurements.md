<a id="heng-à-x5-avec-fenêtres-bornées--28-octobre-2026"></a>

# Heng x5 with bounded windows — 28 October 2026

**Pause/x5/pause** scenario completed through real MCP. Native speed stays 5 during active observations, clock advances **0,933923721 simulated h in 20,378680 s**, then copy restored paused. Function windows selected from frames actually completed within each phase; no preceding-phase frame reused.

Plugin remains **0.8.9/v100 x64**, 17 tools/three probes charsUpdate/findPath/MedicalSystem. No engine algorithm or binary changed, no gain claimed. Descriptive capture: population, streaming and external load not made deterministic.

<a id="contrôleur-et-vérifications"></a>

## Controller and checks

Command used: `tools/research/live_pause_cpu.py --speed 5 --adaptive-tail --tail-max 3600`. Speed option accepts integers1 and 5, checks effective value at every observation and retains label running_x5. Historical no-option mode retains x1 and 600 fixed frames.

After twenty requested seconds, another scene supplies frame counter. Requested count `min(3600, frame_observée − frame_entrée − 1)`. Phase with no completed frame strictly after entry rejected. Raw retains cap, scene and requested count; analysis recomputes selection then checks continuity/actual bounds. CPU-window duration does not thereby become identical function window. Calls attributed at completion and may start before window.

**536 tests pass in 21,07 s**, including wrong/unadvertised speed, booleans, phase order, insufficient new frames, contradictory window count/boundary. Historical Medical0.8.9 and Zone0.8.8 reports strictly identical; retained fields of three RIP analyses unchanged. Evidence: `runtime/x5-legacy-compatibility.json`. No test/build during measurement.

Raw: `runtime/scenarios/pause-cpu-x5-adaptive-20261028T133051Z.json`, completed=true, SHA-256 **f1d846061c4f8f905481b82d54303e9e9c7a1d87605d315879ab666a5a0667c3**. Reproducible analysis: `tools/research/analyze_profiled_function.py INPUT --output NOUVEAU_FICHIER`, retained result `runtime/heng-x5-adaptive-analysis.json`. Game39204/Unix creation 1793190312.050583, path/command verified.

<a id="cpu-horloge-et-frames"></a>

## CPU, clock and frames

| Phase | Process CPU interval | Process CPU | Mean logical processors | Simulated progression | Inventory population |
|---|---:|---:|---:|---:|---:|
| Pause before |20,390 s|36,187500 s|1,774767|0 h|403→403|
| x5 |20,375 s|46,140625 s|2,264571|+0,933924 h|435→453|
| Pause after |20,328 s|36,218750 s|1,781717|0 h|448→448|

Inventories complete and counts agree with bracketing scenes. Intermediate active observations nevertheless cover 421..453 characters; reads asynchronous, population evolving. Active phase not accepted as full-roster comparison at fixed clock. Signed process/thread residuals **−0,046875/−0,125000/−0,015625 s**, no identity omission; retained without clamping/system attribution.

| Phase | Selected frames | Count | Measured mean interval | Interval p99 |
|---|---|---:|---:|---:|
| Pause before |498191..500990|2800|7,276961 ms|11,1295 ms|
| x5 |501422..504179|2758|7,376880 ms|13,2390 ms|
| Pause after |504609..507284|2676|7,587717 ms|11,4859 ms|

All three counts below cap 3600 and actually adapted. Callback intervals do not guarantee displayed FPS. Separate 3600-frame context may overlap another phase. Observed compact function responses 48568/56923/48571 bytes, contexts49578/56955/49033: below 64 KiB here, without universal guarantee.

<a id="fonctions-et-threads"></a>

## Functions and threads

MedicalSystem::periodicUpdate: **27501 calls**, inclusive wall total **94,668745 ms**, mean 0,034325 ms/frame/max call 0,149400 ms in x5 window. All on **TID13132/creation FILETIME 134376639240828501**, joined to non-render SDK role. Per-call CPU disabled:27501 unavailable, totals null, no nested entries omitted or thread truncation. Zero completed medical calls in pause windows.

Whole thread 13132 consumes 5,90625 s CPU at x5; does not isolate medical function. GameWorld/Renderer share **35744/creation134376639120505844**, whole CPU16,25/15,921875/15,84375 s. Normalization over threads' own endpoints about0,796334/0,781442/0,778831 logical processor; not exclusive rendering attribution. Worker 32156 consumes 2,90625 s CPU at x5, function still unattributed; no historical BirdManager-name transfer.

CharsUpdate mean 0,335819 ms/frame at x5. FindPath: **778 calls on other threads**, 706 true/72 false; inclusive wall total **1314,563797 ms**, maximum 172,785000 ms. Pause windows have zero completed findPath calls. Inclusive times are not an exclusive breakdown to add to OS CPU.

**Seven retained calls ≥10 ms** all hierarchical and false: **162,406900..172,785000 ms wall**, sum1179,923200 ms; quantized per-call CPU **140,625..171,875 ms**, sum1078,125 ms. Cost therefore not primarily a simple wait in these samples. Received start/goal XYZ form seven distinct pairs, radius/water/hierarchical parameters retained. Fourth vector component not treated as a spatial coordinate in this comparison. Neither false-return cause, character identity nor complete cache key/invalidation established.

Calls carry **TID 11156**, creation 134376639239445460 identical at CPU endpoints; whole thread consumes 1,28125 s CPU over 20,375 s. Calls cluster between frames 501493 and 501771 at phase start, while CPU heartbeats span501420 to 504182. Cost not uniformly distributed over twenty seconds. Do not calculate exclusive CPU coverage between retained calls alone and whole thread. Derived detail retained in `runtime/heng-x5-navigation-detail.json`; numbers directly verifiable from seven raw navmesh_slow_calls rows, without counting again in expanded context.

<a id="restitution-et-suite"></a>

## Restoration and continuation

`runtime/heng-x5-adaptive-final.json` confirms copy paused/multiplier0 at **404,3333339691162 h**, normal camera/temporary control released/Edge=true. 702/702/738 source/copy/snapshot files compliant, settings byte-identical to pre-deployment0.8.9, guards false. Fresh watchdog without error, WPR inactive, no remaining scenario controller. Session/bootstrap still bounded to 28 October 22 h15 UTC; no administrator intervention expected.

Useful continuation: distinguish navigation bursts from steady operation and complete non-render-worker attribution using verified SDK symbols. Distinct slow queries do not justify exact-repeat failure caching; sample durations do not demonstrate a global bottleneck. A future x1/x5 comparison must retain initial-state limitations and its own windows; older campaigns are neither causal comparison nor engine gain.
