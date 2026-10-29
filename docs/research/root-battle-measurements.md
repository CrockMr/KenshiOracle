<a id="combat-de-40-pnj--root-et-compteurs-cpu-0818"></a>

# 40-NPC battle: Root and CPU counters, 0.8.18

A Mongrel campaign at x5 speed tracked **40 NPCs over 111 observations**. **36 actors show a wound signal**, up to 12 are unconscious in the observations; no death or target outside the group is observed. All four windows completed and the copy is restored paused. Root identities and counters are available in every retained series.

**Two series were shortened by the native 64 KiB ceiling.** Their means and p99 describe the ends of the windows without guaranteeing coverage of early peaks. This limit matters as much as measured times. The campaign demonstrates neither engine gains, marginal cost per NPC, exclusive CPU nor GPU time.

<a id="conditions-et-vérifications"></a>

## Conditions and checks

Same process as the Heng CPU-enabled campaign: PID37556, Unix creation1793217991.454578, same DLL0.8.18 SHA256 **24ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**. No restart, build or native change during this campaign. **17 MCP tools, v100 x64, three profiled systems**, three dedicated detours plus two services. Root replaces other selections; Root CPU enabled, TLS identity and navigation modes unchanged.

Before mutation, controller `tools/research/live_root_battle.py` checks executable/creation, save hashes, plugin DLL, loaded Ogre module, its no-argument export and resolved address. It reloads KenshiProbe_test under temporary camera lock, prepares Mongrel and waits until ready, then creates twenty Bloodraiders/Mercenary Guild pairs with verified mutual hostility. The GetThreadTimes calibration reference remains the [Root CPU report](root-cpu-measurements.md), with companion-report SHA. It guarantees no per-frame CPU precision.

Four windows requested for **5/5/10/10 seconds**, observations every requested 0,25 s, complete before/after inventories with limit500. Simulated time advances in each. NPC seed and full state are uncontrolled. Heng captures and the old Havok battle remain separate cohorts, without causal comparison.

**837 tests pass in 24,81 s before acquisition**, including checks for the new Root battle analyzer, compatibility with the old battle, quantized counters, identities and the consolidator adapter. An independent controller review found no blocking defect; final attestations were strengthened to include time, inactive battle, normal camera and source SHA. No test or build during acquisition.

<a id="séries-effectivement-retenues"></a>

## Series actually retained

| Window | Requested duration s | Frames requested → retained | Mean Root wall ms/frame | Mean interval ms | p99 interval ms | Max Root call ms |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 346 → 173 | 9,904946 | 9,908775 | 15,2745 | 17,793500 |
| 2 | 5 | 585 → 585 | 8,966793 | 8,971941 | 14,1192 | 15,529700 |
| 3 | 10 | 1065 → 532 | 9,415041 | 9,424072 | 16,6824 | 25,363300 |
| 4 | 10 | 1073 → 1073 | 9,544408 | 9,549954 | 15,0027 | 30,994700 |

Aggregate Root call counts match retained frames without proving a call in every undisplayed frame. Per-frame statistics retain only the final 100 rows. No truncated/unknown Root identity, no call with unavailable CPU. Times include original work, nested callbacks/services and waits; their reading points differ from CPU and callback-interval boundaries.

Compact main responses: **64367/63148/63046/63806 bytes**. Windows 1 and 3 needed a second request after size rejection. Diagnostic contexts requested at 3600 were reduced to **225/450/900/1800**, with 5/4/3/2 attempts respectively. All attempts are retained. These bytes come from compact re-encoding, not exact TCP wire counts.

A new request also moves forward in time: reductions are not simple slices of an immutable snapshot. Scenes bracket retained buckets, but the p99 values above do not summarize entire OS windows, especially windows 1 and 3. Commands and retries form part of collection load; this campaign does not isolate their effect.

<a id="cpu-et-populations"></a>

## CPU and populations

| Window | Root user CPU ms | Root kernel CPU ms | Root CPU sum ms | Whole-thread CPU s | OS window s | Process CPU s | Logical processors |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1218,750 | 187,500 | 1406,250 | 3,859375 | 5,266 | 10,609375 | 2,014693 |
| 2 | 3343,750 | 546,875 | 3890,625 | 3,937500 | 5,281 | 12,390625 | 2,346265 |
| 3 | 3250,000 | 484,375 | 3734,375 | 7,984375 | 10,375 | 22,703125 | 2,188253 |
| 4 | 6265,625 | 1218,750 | 7484,375 | 7,546875 | 10,282 | 23,875000 | 2,322019 |

Root joins **T18372 / creation FILETIME134376915914545795**, both CPU endpoints and game_thread/service_thread TIDs from bracketing heartbeats. Root sums cover retained calls only; thread/process columns cover broader OS windows. **No subtraction or exclusive-coverage fraction is calculated.** Counters around calls are quantized and include measurement code; zeros or deltas exceeding wall time are not clamped.

Signed process-minus-computable-thread residuals: **−0,109375/−0,015625/−0,046875/−0,109375s**. The seven SDK-role rows represent five unique identities; both physics roles alias and SaveFileSystem remains unverified. No omitted identity at CPU endpoints; residuals remain signed, with no invented consumption. Observed populations **169..295 / 289..289 / 289..331 / 309..344**. game_total_hours progression **+0,226564 / +0,241835 / +0,475594 / +0,471228h**. Population and wound changes are observed without exclusively attributing times to those changes.

<a id="preuves-et-rejeu"></a>

## Evidence and replay

Capture **runtime/scenarios/root-battle-20261028T202347708754Z.json**, SHA256 **59e8a609a75a4cd32606d83fc3bdd6ab40ef6f1e323f851afe597d27b5258ecc**, completed=true, no acquisition/restoration errors. Analysis `runtime/root-battle-0818-analysis.json` and summary `runtime/root-battle-0818-summary.json`. From the root:

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_root_battle.py runtime\scenarios\root-battle-20261028T202347708754Z.json --expected-sha256 59e8a609a75a4cd32606d83fc3bdd6ab40ef6f1e323f851afe597d27b5258ecc --output runtime\new-report-root-combat.json
```

New manifest **docs/research/performance-cohorts-root-battle.json**, SHA256 **6798e0f00eca3da90f22a7c43090b546e6920b3fea26ad68e0f00f9cef29f594**: **eight cohorts and twenty-six windows**. Report `runtime/performance-cohorts-root-battle-v1.json`, SHA256 **ad8c1c5bee25acec1fe826bbfbfed8f1d6a364dbf9c5ca6dc7aeb8fe48081a89**; same-named Markdown SHA256 **3b9d23d6ce7c87fe3e84236095b5b58127088f7e76561d31a2a76eed35f2ae54**. Evidence `runtime/root-battle-cohorts-replay-proof.json`: two Python seeds byte-identical, canonical specialized analysis identical, seven prior cohorts strictly identical. No historical raw capture or manifest changed.

Independent audit **runtime/root-battle-0818-final.json**: same process, pause/multiplier0 at **404,3333339691162h**, normal camera and temporary control released, Edge restored, battle inactive. **702/702/738 files** of source/copy/old snapshot conform; settings unchanged, restoration guards false, watchdog fresh without error, WPR inactive, no remaining test controller. Both helpers remain 5948/41992, with creation times from the previous CPU report; recheck all their identities before stopping.

<a id="amélioration-maintenant-étayée"></a>

## Improvement now supported by evidence

The response ceiling did remove part of the first measurement windows. The next tool improvement is a compact statistics response retaining aggregates over the entire requested range, with optional large details and explicit omissions. It can remain in the existing MCP tool. Criteria: same aggregates as the full response on own fixtures, clearly defined temporal selection, response below the ceiling and real validation under load. Collection cost will need checking; arbitrarily increasing the ceiling or comparing truncated p99 values with old campaigns does not address this limit.
