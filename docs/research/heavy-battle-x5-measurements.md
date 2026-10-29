<a id="combat-urbain-de40-pnj-à-x5--28-octobre-2026"></a>

# Urban battle with 40 NPCs at x5 — 28 October 2026

Mongrel scenario completed four requested 5/5/10/10-second windows, with **40 tracked NPCs in 108 observations**, about 32,078 seconds of execution. **36 actors show a medical injury signal**, up to 35 observed under attack and 8 unconscious; no death observed. These are sampled states, not hit counts or attribution of injuries to an attacker.

Plugin remains **0.8.10/v100 x64**, 17 tools/three probes charsUpdate/findPath/Havok. No native change, new engine algorithm or performance gain claimed. Additions are a test controller, offline analysis and size-bounded statistics collector. **575 tests pass in 21,16 s**, including rejection of incomplete cohorts, contradictory CPU counters, wrong speed/camera, out-of-bounds windows and false size-reduction histories.

<a id="préparation-et-limite-de-transport-réellement-rencontrée"></a>

## Preparation and actual transport limit encountered

Existing native limit is 20 pairs. `tools/research/live_heavy_battle.py` loads only KenshiProbe_test, moves players near Mongrel, allows ten seconds x1 then waits for stable readiness, pauses and focuses camera. Templates **16863-gamedata.base/Bloodraiders** and **1227-gamedata.base/Mercenary Guild**; factions verified mutually hostile before creation, relations−100 in both directions. No relation changed. Command creates 40 nonplayer NPCs once; partial preparation requires reload, never repeated creation in the same scene.

First trial `runtime/scenarios/heavy-battle-20261028T143434395827Z.json`, SHA **d7ccdf1ce9364072ee8c40318bd292961ce5ff3e4eae9775720065436fa490c0**, remains **completed=false**. First two windows complete; third has counters/statistics but fails on 3600-frame context, native response too large. Copy restored, saves/settings intact. Neither engine crash nor complete trial to include as a repetition.

`tools/research/statistics_budget.py` now reduces **only get_frame_stats reads** after explicit `response too large; reduce n or limit` error. Count halved until success or 1, at most 12 calls. All attempts retained, including terminal failure; ordinary transport/readiness errors not retried. Actual retained counts remain bounded by phase, then analysis verifies provenance, continuity and bounds. No shorter window claimed to cover the entire CPU interval. Strategy applies to new battle controller; it does not retroactively make every old script adaptive.

All 40 actors retain full detailed health, unique names and tracking at every observation. Town inventories complete before/after, 179 then 395 rows, but population/reinforcements evolve. 500-row and 65536-byte limits remain independent. Largest scene re-encoded as compact JSON in this trial is 31158 bytes. No scenario save written; random generation unseeded.

<a id="campagne-admise-et-reproduction"></a>

## Accepted campaign and reproduction

Raw: `runtime/scenarios/heavy-battle-20261028T144427381931Z.json`, completed=true, SHA **8dcc9c57886b6789d7240740f44944a9e156db5ba90bfe237580e1a5a478a82c**. Final analysis: `runtime/heavy-battle-0810-analysis.json`. Offline reproduction:

`tools/research/analyze_heavy_battle.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER`

Analysis revalidates cohort, health, speed/camera, progression, statistics windows, size histories, endpoint native CPU counters and SDK/Windows identities. Output file must be new. File preservation is controller attestation in raw data; final audit separately recalculates actual manifests.

| Requested window | Process CPU/enclosing duration | Mean logical processors | Retained frames | Mean interval/p99 | Maximum unconscious |
|---|---|---:|---|---|---:|
|Initial 5 s|12,187500 s/5,187 s|2,349624|316103..316496,394|12,991564/66,3855 ms|1|
|Next 5 s|13,156250 s/5,172 s|2,543745|316528..317027,500|10,222859/19,3947 ms|3|
|Next 10 s|24,156250 s/10,156 s|2,378520|317079..318148,1070|9,447618/15,2917 ms|7|
|Final 10 s|22,781250 s/10,141 s|2,246450|318220..319247,1028|9,826232/17,3771 ms|8|

Intervals are instrumented callback intervals, without displayed-FPS guarantee. Initial p99 is higher in this scene, but simultaneous population 176→295, recent creation and streaming/reinforcements prevent attribution solely to 40 combatants. Window populations 176..295/295..301/301..332/318..399. Signed CPU residuals **+0,046875/−0,062500/−0,203125/−0,125000 s** retained without clamping; no thread identity omitted. Simulated clock +0,234432/+0,237024/+0,465406/+0,464598 h between each window's own scenes. CPU counters, clocks and frames have distinct boundaries; gaps between windows are not continuous CPU coverage of the 32 seconds.

Main windows admitted on first call: 394/500/1070/1028 frames, compact responses 56040/57555/55446/56806 bytes. Diagnostic contexts demonstrate actual limit recovery:

| Window | Counts attempted for context | Admitted count/compact bytes |
|---|---|---|
|1|3600|3600/64005|
|2|3600 rejected,1800 rejected,900 admitted|900/60322|
|3|3600 rejected,1800 admitted|1800/60589|
|4|3600 rejected,1800 admitted|1800/58445|

Contexts have different bounds and may overlap another window or preparation. They help identify navigation threads among retained slow calls; absence of a call in a shortened context does not mean zero navigation CPU.

<a id="combat-et-profilage"></a>

## Combat and profiling

**56 observations with targets outside the cohort** retained; not 56 distinct reinforcements. NPCs may choose another member instead of their paired partner. Medical changes used only as actual-combat signals, without attacker attribution or task throughput. The 36 actors with signals do not prove the remaining four suffered no attack between reads.

HavokCharacter::update joined to non-render role **TID39604/creation134376698083790089**: 11424/17578/32947/40733 window calls, inclusive means 0,037349/0,038842/0,043560/0,064338 ms/frame. Per-call CPU stays disabled, null/unavailable; no exclusive coverage computed. Whole thread consumes 1,46875/1,90625/3,453125/3,09375 s CPU in respective OS intervals. Main/render34996/creation134376697962686336: 3,921875/4,03125/7,71875/8,078125 s CPU. Identities verified by creation/bracketing SDK roles, without carrying identities from another process.

FindPath counts 410/305/1344/1208 calls in retained windows, globally in world without actor identity. Function durations are not exclusive costs to add to process CPU. Conditions, generated cohorts and populations differ from older 2/10-NPC battles and Heng towns: their comparison yields no marginal per-NPC cost, causal x1/x5 comparison or engine gain.

<a id="restitution-et-suite"></a>

## Restoration and continuation

`runtime/heavy-battle-0810-final.json` confirms same game19264/creation1793196196.268632, copy paused/multiplier0 at **404,3333339691162 h**, normal camera/temporary control released/Edge=true, cohort tracking cleared. **702/702/738 files** source/copy/snapshot compliant, settings byte-identical to pre-deployment0.8.10, guards false. Fresh watchdog without error, WPR inactive, no remaining scenario controller; 17 tools/seven roles/three probes. DLL 0.8.10 unchanged, deadline28 October 22 h15 UTC unchanged, no administrator intervention expected.

Next diagnostic can use retained temporal variation/SDK roles to describe the initial peak, separating cohort activity, population change and resource work. Cohort MCP reads' own cost is not isolated; quantifying it in existing service callbacks would help before attributing this peak to the engine. Another collection must address a new question with explicit bounds; repeating the same nondeterministic battle does not isolate its cause.
