<a id="statistiques-agrégées--validation-0819"></a>

# Aggregate statistics — 0.8.19 validation

**`aggregates` mode retains every requested frame while reducing response volume.** In a 40-NPC battle at Mongrel, all four windows and their 3600-frame contexts were each obtained in one request, with compact responses of about **4,7 kB**. This addresses the response ceiling that could require reducing the collected window.

The plugin still builds the complete response before removing two lists. The result demonstrates reduced transmitted volume and retention of requested windows; **statistics computation is unchanged, with no demonstrated engine CPU or FPS gain**. Measurements from successive battles with different populations do not constitute an A/B comparison between versions.

<a id="contrat-et-compatibilité"></a>

## Contract and compatibility

`get_frame_stats(n, detail='full')` retains its default behavior. Omitting `detail` and explicitly passing `full` follow the historical full path; no projection metadata is added. `aggregates` is optional; other values or types are rejected. MCP retains **17 tools**.

`plugin/StatisticsDetail.h` applies projection after constructing `stats(n)`. Arrays `per_frame` and `navmesh_slow_calls` explicitly become **null**, accompanied by:

```json
"statistics_detail": {
  "mode": "aggregates",
  "per_frame_rows_omitted": 100,
  "navmesh_slow_rows_omitted": 7
}
```

The numbers illustrate this campaign's first window. Aggregates, boundaries, identities and retention indicators remain those of the initial response. Requested omission is distinguished from native truncation: the individual series historically retains only the last 100 rows, and the slow-call registry has its own capacity. An omitted list means neither zero calls nor absence of work.

`tools/research/statistics_detail.py` checks counts, boundaries, indicators and explicit nulls, including an empty buffer. Analyzers can skip validation of unavailable rows without inventing those observations. Navigation aggregates remain available; roles depending on slow-call rows are not reconstructed in this mode. The campaign declares `navigation_detail_roles_available=false`.

**88 native v100 x64 assertions** notably check projection of the same input and exact preservation of aggregates. The final suite has **892 passing Python tests in 23,21 s**. A first run had nine failures due to synthetic fixtures missing navigation metadata required by the validator; only those fixtures were completed. This was not a defect observed in-game.

The real MCP smoke validates all three forms: default, `aggregates`, then explicit `full`. For n60, the observed full response is **36671 bytes**, the compact response **4701 bytes**. These adjacent requests cover frames 469–528, 471–530 and 472–531: they do not prove equal aggregates for the same frozen window. That equality on identical input comes from native tests. The pre-campaign cadence check observes **71 frames over 512,088 ms**, with a last-ten mean of **7,322660 ms**; it does not measure projection's isolated cost.

<a id="campagne-à-mongrel"></a>

## Mongrel campaign

The version remains **v100 x64**, three profiled systems charsUpdate/findPath/Root, with three dedicated detours and two services, **five effective installations** in total. Root uses the previously verified no-argument export, optional CPU enabled. No new hook or game algorithm.

The campaign reloads the protected KenshiProbe_test copy, prepares Mongrel and then 20 fighter pairs, and observes four windows of **5/5/10/10 s requested at x5 speed**. The context has a 3600-frame history before use. The camera remains controlled during measurement; final cleanup reloads the copy in pause and releases control.

| Window | Requested and received frames | Statistics bytes | Context frames | Context bytes | Individual rows omitted | Navigation rows omitted, statistics / context |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 221 | 4731 | 3600 | 4742 | 100 | 7 / 20 |
| 2 | 565 | 4705 | 3600 | 4744 | 100 | 0 / 20 |
| 3 | 1097 | 4713 | 3600 | 4759 | 100 | 0 / 20 |
| 4 | 1053 | 4711 | 3600 | 4741 | 100 | 0 / 20 |

Every request succeeds on its first attempt without reducing n. Sizes are the compact JSON re-encoded and checked by the analyzer, not exact TCP/MCP byte counts. The native 64 KiB ceiling is unchanged. The 3600-frame contexts are rolling windows broader than the four measurement periods; their entire contents must not be attributed to one period's battle.

All **40 actors** remain tracked over **110 observations**, with **34 actors showing a wound signal**, up to **nine unconscious**, no death observed in the windows and **35 external-target observations**. Medical changes give neither a hit count nor certain attribution to an attacker.

| Window | Mean Root wall ms/frame | Max Root ms | Mean interval ms | p99 interval ms | Root user CPU ms | Root kernel CPU ms | Observed population |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 23,292300 | 131,651900 | 23,267331 | 124,8890 | 2406,250 | 468,750 | 178–326 |
| 2 | 9,347930 | 25,375200 | 9,352127 | 14,1701 | 3515,625 | 546,875 | 322–336 |
| 3 | 9,331531 | 18,227700 | 9,336716 | 14,1052 | 6296,875 | 1078,125 | 325–375 |
| 4 | 9,665162 | 18,035200 | 9,670818 | 15,2680 | 6234,375 | 1437,500 | 335–401 |

Root counts 221/565/1097/1053 calls respectively, all with CPU counters available. CPU sums are **2875 / 4062,5 / 7375 / 7671,875 ms**. Here the large initial variation accompanies a growing population; its exclusive cause is not established. These values prove neither marginal cost per NPC nor acceleration compared with an earlier battle.

Root calls are inclusive: original work, measurement code and nested callbacks, probes or services. Admission of completed calls to buckets, scene snapshots and OS CPU endpoints have different boundaries. Mean Root can therefore slightly exceed the mean callback interval without implying waiting or inconsistency. No wall/CPU subtraction or exclusive-coverage fraction is interpreted.

<a id="cpu-identités-et-précision"></a>

## CPU, identities and precision

Root joins **T18784 / creation FILETIME134376935315380313**, present at both CPU endpoints and identified as the main/render-service thread at the boundaries. Whole-thread CPU is **2,9375 / 4,09375 / 7,40625 / 7,703125 s** over OS windows of **5,250 / 5,328 / 10,281 / 10,219 s**. These whole-thread counters are not counters for only the retained Root calls.

The process consumes **9,53125 / 12,671875 / 25,734375 / 22,609375 CPU s**, or **1,815476 / 2,378355 / 2,503100 / 2,212484 logical processors**. Signed process-minus-computable-thread residuals are **−0,109375 / +0,078125 / +0,078125 / −0,09375 s**. Two threads, T31840 and T43484, are not observed at the first window's final endpoint; T20104 is missing at the third's initial endpoint. They remain omitted, without invented consumption. Root identity is verified in all four windows.

Startup of this DLL observes **0,235001 µs per CPU read**. The own helper's [separate calibration](root-cpu-measurements.md) remains referenced in the capture with its SHA. It does not guarantee resolution or in-game hook cost. A 100 ns unit does not mean 100 ns precision; zeros and quantized deltas greater than a short call's wall time are retained without clamping.

<a id="provenance-et-reproduction"></a>

## Provenance and reproduction

Complete capture: **runtime/scenarios/aggregate-battle-20261028T204139893880Z.json**, SHA256 **8a69d77558235340f8d2cf51a875b6ab379d054f326ee0af58f50ec9f427662f**. Specialized analysis: `runtime/aggregate-0819-analysis.json`; summary: `runtime/aggregate-0819-summary.json`. Replay checks Root/CPU contracts, boundaries, battle and restoration, preservation of each requested n in one request, and recalculated compact sizes.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_aggregate_battle.py runtime\scenarios\aggregate-battle-20261028T204139893880Z.json --expected-sha256 8a69d77558235340f8d2cf51a875b6ab379d054f326ee0af58f50ec9f427662f --output runtime\new-report-aggregates.json
```

Manifest **docs/research/performance-cohorts-aggregates.json**, SHA256 **d12af2a277a0147ab3ce08fedaceeafb79b9e5d866fcd80c38b5182901cd35a9**, extends the diagnosis to **nine cohorts and thirty windows**. Report `runtime/performance-cohorts-aggregates-v1.json`, SHA256 **05c42fde3ee3315b0c38608b21ab7b9afe68544713ecf348c3596790b72433e7**; same-named Markdown SHA256 **7394cb0c27843b94b8396dfb8e272dea70e76c4d6405407a3548cd5e91795bbd**.

Evidence `runtime/aggregate-cohorts-replay-proof.json` retains two byte-identical replays under different seeds, equality of specialized analysis and all eight old metrics strictly identical. Only the SHA provenance of `analyze_root_battle.py` source evolves with its expected-version parameter, default 0.8.18 and explicit 0.8.19. The historical eight-cohort report is therefore not claimed byte-identical after this change; its captures and manifest are preserved.

<a id="déploiement-et-restitution"></a>

## Deployment and restoration

Deployment archived under **crashes/20261028T203850754003Z-deployment-0819**. Own DLL of **322560 bytes**, SHA256 **796872282880f8eefeb3493773fb46ce6c49b18ae58e33f3cfb581b5baeec8a3**; PDB of **10406912 bytes**, SHA256 **0d2b29b027345d0b0af8294cae87ae9d2c747d1d92c547a77ffcdb347f0c82de**. Binaries, captures and game files remain outside Git.

The independent **runtime/aggregate-0819-final.json** audit verifies game **32156 / Unix creation1793219931.5380297**, project executable and command. The copy is restored paused, zero multiplier, at **404,3333339691162 h**, normal camera, temporary control released, Edge restored and battle inactive. The **702/702/738 files** of validation/copy/old snapshot match references, settings unchanged, two restoration guards false, watchdog fresh without error and WPR inactive. The final n3600 aggregate read succeeds in one **3954-byte** request.

Observed helpers are **38176 / Unix creation1793219931.3160987** and **43920 / Unix creation1793219931.3597145**; their identities must be rechecked before stopping them. These findings describe this audit, not a guaranteed future state. The autonomous deadline remains **October 28 at 22:15 UTC / 23:15 Paris**.
