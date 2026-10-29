<a id="diagnostic-de-performances-reproductible"></a>

# Reproducible performance diagnostic

**Current state 0.8.20: nine historical cohorts/thirty windows and three separate collection series.** The [randomized confirmation](randomized-observer-measurements.md) preregisters order, seed, protocol and sources before 36 blocks/660 requests, with no skips. MCP server CPU is identified and measured over its separate intervals. At 10 Hz, all six paired aggregates−full differences for service and client latency are negative, medians −1,93242 ms and −3,58830 ms. Server CPU has three positive and three negative differences: gain undetermined, no FPS/GPU or exclusive CPU gain demonstrated. The 110 locked points retain 78 characters/1 town versus 106/1 in the preceding pilot, despite the same DLL and game; do not merge the series as an identical-scene A/B. **1143 Python tests pass**, byte-identical replay under two seeds; copy left paused and protected files compliant. Following paragraphs are historical.

**Historical reference 0.8.20: direct aggregate construction.** [Direct construction](direct-aggregate-statistics-measurements.md) preserves JSON across 198 native snapshots and completes 36 blocks/660 requests, with restoration and audit. At 10 Hz in this paused series, compact service is 88,18 % shorter in paired median reduction than full service; no FPS/GPU or exclusive CPU conclusion. Reload presents 106 characters versus 78 in the 0.8.19 pilot: these series are not an identical-scene A/B. 1023 Python tests, 2266 native assertions and 61 bootstrap assertions passed at this milestone. Historical captures and metrics remain unchanged.

**Current state: nine cohorts and thirty windows**, with [compact statistics 0.8.19](aggregate-statistics-measurements.md). All requested N in the new campaign are retained in one request each; details explicitly null with omission counters. 892 tests pass in 23,21 s. Earlier campaigns retain their own metrics and limitations, without causal cross-version performance comparison.

**Current state: eight cohorts and twenty-six windows**, including [combat40 Root CPU](root-battle-measurements.md). 837 tests pass in 24,81 s, same 0.8.18 DLL. Two series in this battle are tails shortened by the response budget; their p99 values do not cover omitted initial peaks. New reports are byte-identical under two seeds and the previous seven cohorts strictly preserved. Seven/six/five-cohort extensions below are historical.

**Current extension: seven cohorts and twenty-two windows**, with [Root CPU mode measured and calibrated](root-cpu-measurements.md). Same 0.8.18 DLL retained; 796 tests pass in 23,70 s. Six- then five-cohort paragraphs below are historical. Old metrics unchanged; their Root analyzer source SHA changes when expected CPU mode becomes explicit. New seven-cohort reports byte-identical under two Python seeds, without causal mode comparison.

**Six cohorts and nineteen windows can now be replayed offline**, with fingerprints and specialized analyzers, through the Root manifest added at the end. Historical five-cohort/sixteen-window manifest unchanged and its report remains byte-identical. Both Python seeds produce the same reports. **778 tests pass in 24,00 s**. Current plugin **0.8.18/v100 x64**, with **17 MCP tools and three profiled boundaries**; consolidation itself launches no game measurement.

<a id="reproduire-le-manifeste-historique-sans-lancer-le-jeu"></a>

## Reproduce the historical manifest without launching the game

From the project root, five local captures under runtime must be available. They remain Git-ignored; no save or game data is distributed by the manifest. CLI connects to neither MCP nor watchdog and calls no capture tool. It rejects a manifest/raw file with a different SHA, incomplete captures, cohorts repeating the same raw file and existing outputs.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_performance_cohorts.py docs\research\performance-cohorts.json --expected-manifest-sha256 895a59dc6fca89d6fd22897c767fff12c4eb4d9ea71db7eea006f8c6b99208a7 --root . --output runtime\nouveau-diagnostic.json --markdown runtime\nouveau-diagnostic.md
```

Version 1 manifest: `docs/research/performance-cohorts.json`. Accepted report: **runtime/performance-cohorts-v2.json**, SHA256 **2cc2069553f320d91fa0a4474997cdc42a7ca99f7b1055820565b9e2050d3312**; full table **runtime/performance-cohorts-v2.md**, SHA256 **a679c78028f5d87a40112b273a52c2e12f36d2c5d8f1532d5ec9402b6759144d**. Evidence for five specialized rereads and seeds 0/8675309: **runtime/performance-cohorts-replay-proof.json**. First v1 prototype retained; v2 adds explicit SDK/CPU joins, without new acquisition.

The manifest fixes native version, selection, relative path and SHA of every capture. Scenarios are declarative labels; actual scenes and towns present are retained separately. CLI reruns every specialized analysis from raw data, rather than copying a cached summary. PID/creation, TID/FILETIME, scene windows, buckets and OS counters stay separate. Creation FILETIMEs remain exact strings; no merging cohorts because TIDs match.

<a id="cohortes-indépendantes-pas-un-benchmark-entre-versions"></a>

## Independent cohorts, not a cross-version benchmark

| Cohort | Retained conditions | Fact observed in this cohort | Main limitation |
|---|---|---|---|
| Heng/Havok0.8.10 | Pause/x5/pause, 3221/2832/2825 frames | 528882 active Havok calls, 0,037101 ms wall/frame | Inclusive function on a worker; not all its CPU |
| Mongrel/combat0.8.10 | 40 NPCs, four requested 5/5/10/10 s windows | 36 actors with injury signals; first interval p99 66,3855 ms | Observed population 176..295 initially, then reinforcements; not marginal per-NPC cost |
| Heng/chars0.8.15 | Pause/x5/pause, 1982/1855/1922 frames | Active chars call 0,296559 ms/frame; post-call 0,000073529 ms/frame | Post includes timer/scheduling, not pure contention |
| Heng/MainLoop0.8.16 | Pause/x5/pause, 2021/1549/1565 frames | Active original 1,363674 ms/frame; interval 8,121418 ms | Initial service excluded, internal callbacks included; not the whole frame |
| Heng/Renderer0.8.17 | Pause/x5/pause, 2032/1783/1886 frames | Active original entry 0,000819574 ms/frame; interval 7,056608 ms | Not all rendering/GPU; timer/trampoline not isolated at this scale |

The full table retains **every pause and window**, observed populations and OS durations. Values are not combined into an overall mean, improvement ratio or “simulation cost” difference. Sessions differ in state, time, population and scope. A callback interval is not a guaranteed measurement of displayed FPS; subtracting inclusive probes does not locate remaining work.

<a id="cpu-et-portées-disponibles"></a>

## Available CPU and scopes

For each window, JSON retains user/kernel/process, OS monotonic duration, logical processors, every calculable thread, **signed** residuals and omissions. Selection/SDK-role joins require TID **and** creation; a changed role is not assigned by TID alone. Two SDK roles may point to the same thread: their CPU is not additive. These numbers cover whole threads, not just visible functions.

Example: the active Renderer cohort consumes 2,264008 logical processors at process level, with selected thread 10,171875 s CPU over 12,609 s OS. Another thread is absent at the final endpoint: omitted, without invented consumption. The Renderer entry's 0,000819574 ms wall/frame is a separate scope and does not become this thread's CPU fraction. The first two cohorts lack charsUpdate_split: **null means unavailable**, not a false zero. Their historical chars field remains labeled as ending at lock acquisition.

Two historical adaptations were needed: absent chars-split fields before 0.8.15 and absent root-level process identity in the old Havok controller. In the latter case, identity comes from the first CPU endpoint and is checked across all phases; this provenance is stated. Historical raw data/reports unchanged. No partial battle failure is included as a complete repetition.

<a id="priorités-fondées-sur-les-preuves"></a>

## Evidence-based priorities

1. **Locate work outside already timed main-thread entries.** The [startup→Ogre route](main-thread-loop-route.md) is observed/statically linked, without CPU percentage. King::mainloop was [ruled out before instrumentation](king-mainloop-candidate.md); startup and Renderer::go reach a long-lived loop. Supplied SDK contains another finite candidate: **Ogre::Root::renderOneFrame(void)**, plus a time-argument overload, in Include/ogre/OgreRoot.h. OgreMain_x64.lib already linked by the project. **Historical question since resolved by the Root 0.8.18 campaign**, see [verified export/binding/bool return](root-frame-measurements.md). Initial declaration evidence remains runtime/root-frame-header-candidate.json; instrumentation replaces Renderer. Do not confuse this method with Renderer::renderOneFrame marked no_addr, invent an export or paste an RVA. Still three systems maximum.
2. **Distinguish navigation bursts from steady operation before optimization.** The [earlier x5 campaign](heng-x5-adaptive-measurements.md), complementary to the manifest's five cohorts, contains seven slow false-return searches at different coordinates. This demonstrates neither cacheable repetition nor failure cause; do not add a failure cache on this evidence alone.
3. **Quantify before replacing a worker.** The [observed BirdManager object](worker-object-validation.md) and stack matching identify a route, not exclusive CPU for its computation. No BirdManager API name absent from the SDK is invented. A new capture must answer a precise question; failed clone 1450, identical RIPs and cold REA import are not repeated without a new condition.

Owned [serialization](json-serialization-measurements.md) and [ownership](json-ownership-measurements.md) optimizations are documented separately. Local synthetic gains are not converted to FPS or engine gains. This consolidator does not change Kenshi's algorithm.

<a id="validation-et-limites-pratiques"></a>

## Validation and practical limitations

The 28 new tests cover fingerprints/version/selection, duplicate/existing-output rejection, partial or contradictory captures, historical split/identity absence, FILETIME beyond a float's integer precision, SDK role with changed creation, battle windows and CLI determinism. All five earlier specialized replays have the same canonical digest; both seeds give byte-identical reports. No new native test or unnecessary build: all previous plugin files unchanged.

Exclusive/weighted CPU capture remains absent. Populations are observations, not deterministic NPC state. REA was actually attempted, then cleaned after the **450 s client** deadline before its 900 s budget; no function dossier obtained, see route report. Replay checks recorded data, **not the machine's current state**: separate live audit remains necessary after a real change. Future scenario launches retain authorization/deadline checks; offline replay removes none of these safeguards.

<a id="extension-root-validée"></a>

## Validated Root extension

Historical five-cohort manifest unchanged. `docs/research/performance-cohorts-root.json` adds the [Root 0.8.18 campaign](root-frame-measurements.md): six cohorts/nineteen windows, byte-identical under two seeds and byte-identical older diagnostic. Root 7,064655 ms wall/active frame, interval 7,067360 ms; callbacks/services/waits included, not exclusive CPU/GPU. Same CLI accepts this manifest with explicit SHA. 778 tests pass; 17 MCP tools unchanged.

Reproduce the current extension:

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_performance_cohorts.py docs\research\performance-cohorts-root.json --expected-manifest-sha256 bbff14d3734e95c916f20b8fd74d7f51de600b99afd8cb030daaa427d34ebb2e --root . --output runtime\nouveau-diagnostic-root.json --markdown runtime\nouveau-diagnostic-root.md
```

<a id="extension-root-avec-compteurs-cpu-optionnels"></a>

## Root extension with optional CPU counters

Manifest `docs/research/performance-cohorts-root-cpu.json` adds an independent cohort on the identical DLL, after an archived restart and enabling the existing CPU mode. SHA256 **eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675**. Seven cohorts/twenty-two windows retain their own identities and conditions. Quantized per-call counters represent neither exclusive CPU nor per-frame precision.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_performance_cohorts.py docs\research\performance-cohorts-root-cpu.json --expected-manifest-sha256 eb76130e2a69eb4abdba04b911e850d684f05fd86a34c3fdf652930ae75d1675 --root . --output runtime\nouveau-diagnostic-root-cpu.json --markdown runtime\nouveau-diagnostic-root-cpu.md
```

Accepted report `runtime/performance-cohorts-root-cpu-v1.json`, SHA256 **e66f64669f9bc060cbd1e0f12f208b659ad3e277185b66a6d438f5b3c6884896**; same-named Markdown SHA256 **9b1b8c93d87fdd7451beba1a84b14e1a6c1c1bbb92567286ca0ea49ed300b583**. Evidence `runtime/root-cpu-cohorts-replay-proof.json`: byte-identical under two seeds, identical canonical specialized result, six earlier metrics identical; only their Root source SHA changes, historical reports retained. See [calibration, campaign and limitations](root-cpu-measurements.md).

<a id="extension-combat-root-cpu"></a>

## Root CPU battle extension

Manifest `docs/research/performance-cohorts-root-battle.json`, SHA256 **6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594**. Report `runtime/performance-cohorts-root-battle-v1.json`, SHA256 **ad8c1c5bee25acec1fe826bbfbfed8f1d6a364dbf9c5ca6dc7aeb8fe48081a89**; evidence `runtime/root-battle-cohorts-replay-proof.json`.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_performance_cohorts.py docs\research\performance-cohorts-root-battle.json --expected-manifest-sha256 6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594 --root . --output runtime\nouveau-diagnostic-root-combat.json --markdown runtime\nouveau-diagnostic-root-combat.md
```

Four windows retain 40 actors and 111 observations. Retained statistics 346→173 and 1065→532 are explicitly shortened; OS CPU retains its broader windows. [Protocol, results and limitations](root-battle-measurements.md). Current limitations/questions documented in [open questions](open-questions.md).

<a id="extension-agrégats-compacts0819"></a>

## Compact aggregate extension 0.8.19

Manifest `docs/research/performance-cohorts-aggregates.json`, SHA256 **d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9**. Report `runtime/performance-cohorts-aggregates-v1.json`, SHA256 **05c42fde3ee3315b0c38608b21ab7b9afe68544713ecf348c3596790b72433e7**; evidence `runtime/aggregate-cohorts-replay-proof.json`.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_performance_cohorts.py docs\research\performance-cohorts-aggregates.json --expected-manifest-sha256 d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9 --root . --output runtime\nouveau-diagnostic-aggregates.json --markdown runtime\nouveau-diagnostic-aggregates.md
```

Both seeds produce the same new reports; eight earlier metrics remain strictly equal. The only old provenance change is the root_battle analyzer source SHA, now parameterized by expected version (0.8.18 default, 0.8.19 explicit). Historical files preserved. A range of N callbacks remains distinct from scene and OS CPU endpoints; no exclusive precision or exactly 5/10 s coverage inferred.

<a id="compléments-hors-consolidation--navigation-et-coût-de-collecte"></a>

## Additions outside consolidation: navigation and collection cost

The [navigation timeline](navigation-timeline-measurements.md) replays two existing SHA-verified captures. The 7 and 8 slow active calls cluster in the first quarter of frames, without detailed truncation at the 10 ms threshold. Context and window deduplicated; distinct coordinates do not justify caching. This does not become two new acquisitions.

The [collection pilot](observer-overhead-measurements.md) uses the same 0.8.19 while paused: 36 blocks, 660 requests, 1/10 Hz frequencies, six balanced orders per frequency. Two attempts excluded and retained: camera drift before locking; then 72 early wakeups detected during replay. Corrected series uses QPC and rechecked deadlines. 992 tests pass and both replay seeds produce the same report.

Client aggregates−full latency decreases at 10 Hz in all six pairs (median −0,890 ms), while native service increases (+0,04975 ms). Game CPU varies; no engine/FPS gain established. Pilot remains separate from nine cohorts/thirty windows; pause, navigation and battle data are not pooled into a causal comparison. Historical consolidation files unchanged.
