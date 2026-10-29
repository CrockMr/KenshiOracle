<a id="transfert-de-propriété-des-réponses-json--0813"></a>

# JSON response ownership transfer — 0.8.13

**Three explicit response copies replaced by ownership swaps**, without changing data or protocol. On two synthetic 20,8/25,9 KiB fixtures, mean measured pipeline falls from 0,844577 to 0,344029 ms and from 1,096040 to 0,448945 ms. Across two real paused sessions, mean n60 statistics service falls from 2,111800 to 1,935500 ms, **but total MCP duration does not fall**. Launches and scheduling differ: no overall/FPS or exclusive CPU gain established.

<a id="ownership-et-synchronisation"></a>

## Ownership and synchronization

`json::Value::swap` swaps type,bool,double,string,map,vector, including inactive fields. Self-swap is neutral. Other operands must be independent objects, not a parent and its own descendant. Containers use the module's standard allocator; method swaps resources without cloning trees.

Success path uses this transfer at three boundaries: local payload to final envelope, execute return to Work.response, then Work.response to reply after successful WaitForSingleObject. Service no longer accesses response after SetEvent; its shared_ptr and the network's retain Work until their uses end. Timeout does not take the network-transfer path; cancellation rules and “exécution peut avoir commencé” message remain unchanged. Errors, network heartbeat, 0.8.12 serialization, Game accesses and hooks unchanged.

Windows signal/wait primitives use appropriate memory-ordering barriers; see [Microsoft documentation](https://learn.microsoft.com/en-us/windows/win32/sync/synchronization-and-multiprocessor-issues). This guarantee is combined with a review of our own accesses/lifetimes; it would not make additional post-signal access safe. No new SDK function or Game signature.

Native v100 tests cover 36 type pairs with every field, swap return/self-swap, −0 and hidden NaN payload, Unicode/id/consumed envelope, 200 post-event transfers and timeout without consumption followed by late completion. The latter tests an owned helper, not a new game suspension/restart or exhaustive evidence for every cancellation scenario. Older parser/serializer tests and byte comparisons also pass.

<a id="microbenchmark-propre"></a>

## Owned microbenchmark

`tools/research/benchmark_json_ownership.cpp` uses the textually identical deterministic generator from our previous benchmark. No SDK, game file or data. Three sizes 80/20806/25928 bytes; copy/transfer envelope and copy/transfer pipeline, rotating order, 7 repetitions×60 iterations in each of 3 native processes. MSVC2010/v100 x64, /O2 /EHsc /MD /W3; QPC wall time, destruction included.

**Both variants first clone the shared synthetic payload** to obtain a consumable local object. Pipeline models response assignments; it measures neither actual Game-scene construction, event/thread, serialization, sending nor MCP. Compiler may elide some returns; source assignment counts are not allocation counters. Variants paired in the same process/repetition, outputs compared byte-for-byte before measurement. Ambient load, caches, allocation and scheduling remain unisolated.

| Fixture | Copy envelope ms | Transfer ms | Median ratio | Copy pipeline ms | Transfer ms | Median ratio |
|---|---:|---:|---:|---:|---:|---:|
|80 bytes |0,002434|0,001846|1,294847|0,003853|0,002042|1,908250|
|20806 bytes |0,568893|0,350601|1,508115|0,844577|0,344029|2,422126|
|25928 bytes |0,677781|0,439740|1,559300|1,096040|0,448945|2,499459|

Times = means of 21 cells of 60 operations each. Mean paired pipeline differences: 0,001811/0,500548/0,647096 ms. Ratio min..max for two large pipelines: 2,266934..2,869197 and 2,246944..2,701178. Small object noisier: one envelope pair even gives 0,924052, so no universal promise for small responses.

Capture **runtime/json-ownership/20261028T155027902251Z/controller.json**, SHA **d78e0da25835f2121d291b6c529ad9da67b9572fa7b9d9d373ed882e85821401**; raw stdout and exact owned binary retained. Report **runtime/json-ownership-0813-analysis.json**. Replay checks controller/stdout/binary hashes, plan/compiler/architecture/order, durations/units, fixture fingerprints and consumed checksum 112560. Benchmark json.h header exactly matches the header built for 0.8.13.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_json_ownership.py runtime\json-ownership\20261028T155027902251Z\controller.json --expected-sha256 d78e0da25835f2121d291b6c529ad9da67b9572fa7b9d9d373ed882e85821401 --output runtime\new-report-ownership.json
```

<a id="lectures-mcp-réelles-en-pause"></a>

## Real paused MCP reads

`tools/research/live_json_copy_probe.py` mutates no scene or save. Two launches, 0.8.12 and 0.8.13, 12 rotating ping/scene/n60-statistics reads per launch, requested 0,1 s wait between calls. First read retained. Separate retained warmup requires 60-frame history entirely after phase entry; all retained statistics stay within this paused phase. Stable camera, identical game clock, no battle, temporary camera control released and service Windows identity independently checked before/after each series.

| Read | Version | Mean service ms | Mean wait ms | Mean MCP ms |
|---|---|---:|---:|---:|
| ping |0.8.12|0,234683|1,696108|6,164100|
| ping |0.8.13|0,195133|2,351417|6,838692|
| scene |0.8.12|0,093192|2,887450|7,349117|
| scene |0.8.13|0,067125|3,942208|8,186375|
| statistics60 |0.8.12|2,111800|3,369417|11,211783|
| statistics60 |0.8.13|1,935500|3,853992|11,541950|

Service includes execute/logical response assignment/debug log, excluding network serialization/client; scopes unchanged. **No subtraction of these clocks yields exclusive CPU.** Responses/frames and loaded worlds are not fully deterministic; these cross-launch means are descriptive, not a paired causal comparison like the microbenchmark. Stats service maximum 3,027200 ms after versus 2,342800 before. Waits increase in these captures, with higher mean MCP duration for all three groups; do not claim globally faster MCP.

Before: PID 24320, T23940/creation FILETIME 134376754273623707. After: PID 32476, T11724/creation134376767267123146. Identities verified within each process and **not joined across launches**. 1 then 2 ping/12 pass through Renderer; flag does not mean menu displayed.

Captures **runtime/json-copy-probe/0.8.12-20261028T155324459806Z.json**, SHA **19bad2babb59058856f7deff5920264f6bfba28e44a9df3e0b8ef41ce517c111**, and **runtime/json-copy-probe/0.8.13-20261028T160113516354Z.json**, SHA **6ef89c08e51e35942a459a4f1371d4955e63a951059490d282217e6700bd8489**. Report **runtime/json-copy-0813-analysis.json**. Replay with analyze_json_copy_probe.py AVANT APRES --before-sha256 SHA --after-sha256 SHA --output NOUVEAU_FICHIER. Analysis checks order/quantities/clocks/frames, recounted sizes, pause/camera, per-process Windows identities and derived summary, without exclusive attribution of differences.

<a id="déploiement-et-état-stable"></a>

## Deployment and stable state

**652 Python tests pass in 21,88 s**, including 28 new benchmark/probe checks; native JSON/ownership tests pass. First camera-analysis test expected ValueError but shared validator raised RuntimeError; analysis normalized the error, then full suite passed. Neither native failure nor invalid game capture.

Production changes only json.h (swap and algorithm include) and Probe.cpp (three transfers/comment/version). Serializer remains textually identical to 0.8.12; no other Game/file/hook change. DLL 0.8.13 **280576 bytes/SHA2d611c1323d7c581ead1bf28df056b8fee5fc07c099c69b9d29c2efd073a1c9c**, owned PDB **10341376 bytes/SHA f4057e5a4827a41bf5502cb37e026b91ba6f9de18522802fb8a2636ef0957050** under runtime/symbols/0.8.13. Archive **crashes/20261028T155839631284Z-deployment-0813**, evidence runtime/deploy-0813.json, old 0.8.12 DLL preserved; only project processes' identities freshly checked before stopping.

Real MCP smoke **runtime/json-ownership-0813-smoke.json**, 17 tools/three probes charsUpdate/findPath/Havok, correct metadata/SDK roles/pause. **runtime/json-ownership-0813-wire-1793203310150406700.json** validates four JSON/UTF8/duplicate/idUnicode errors and subsequent ping, without mutation. Independent audit **runtime/json-ownership-0813-final.json**: pause/game clock/camera/Edge restored, saves/snapshot/settings identical, fresh watchdog/zero error, WPR inactive and no remaining controller. No unnecessary new combat40 or real freeze replay.

<a id="prochaine-question-de-profilage"></a>

## Next profiling question

Source review shows the old charsUpdate timer computes `now()-t` **after Guard acquisition**. Its aggregate therefore includes any wait for the telemetry lock plus original call; it does not identify its thread. In old combat40 x5, charsUpdate_mean_ms is 0,557418/0,226448/0,203638/0,239164 ms for mean intervals 12,991564/10,222859/9,447618/9,826232 ms. Values do not locate remaining time and must not be subtracted from other potentially concurrent systems.

Next priority: verify this timer boundary and identify threads in **the existing hook**, separate call duration from post-call interval up to lock while retaining the historical field. Verify SDK signature/buckets before adding; still three probes maximum. Return to engine measurements rather than multiplying small-getter optimizations. No new engine measurement or timer correction yet performed under 0.8.13.

Autonomous deadline 22 h15 UTC/23 h15 Paris unchanged; no user/administrator intervention expected.
