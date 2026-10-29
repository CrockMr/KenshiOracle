<a id="charsupdate--appel-intervalle-vers-le-verrou-et-identité-du-thread"></a>

# charsUpdate: call, interval to the lock and thread identity

**0.8.15 separates the historical timer's two intervals.** At Heng/x5, 1855 calls total **550,117199 ms for the original call** and **0,136396 ms after it until telemetry-lock acquisition**. The latter is **0,024788 %** of the historical 550,253596 ms total in this window. It includes clock/scheduling: neither CPU nor pure contention. No call admitted in either paused window.

Thread **28836/creation FILETIME 134376802586702846** matches game/Renderer-service IDs at both endpoints, with Windows creation independently verified by CPU endpoints. No join to a non-render SDK role found. This locates the instrumented entry; low time at this boundary does not exclude delegated or elsewhere-executed work. No engine/FPS gain claimed.

<a id="frontière-de-mesure-et-api"></a>

## Measurement boundary and API

The old hook took its end after `Guard`; `charsUpdate_mean_ms` therefore included the original call plus the interval up to this lock's acquisition. Under 0.8.15, GetCurrentThreadId and TLS creation are resolved before timing starts, end taken immediately after original, then a third clock after Guard acquisition. Original called once, lock outside original. Historical field retains “through lock acquisition” scope; added fields distinguish intervals.

SDK signature reread: **void GameWorld::charsUpdate()**, GameWorld.h line 216; supplied symbols **?charsUpdate@GameWorld@@QEAAXXZ** and corresponding KenshiLib.lib import. Header SHA **e1c5566b24df65a42d01e884ac8a45125a3b257298469a544ad557b7f43e802f**, library SHA **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Binding retains existing GetRealAddress/AddHook, no copied RVA. Existing service-hook signatures also reread: MainLoop_GPUSensitiveStuff(float), Renderer::_NV_update(). No new Game call, SDK layout or fourth system hook.

`systems.charsUpdate_split` exposes counts, totals/per-frame means/maxima for `call_wall`, `post_call_to_lock` and `legacy`, at most eight TID/creation identities, unattributed overflow and truncation flag. Means divide by retained frames, not calls. Every completed call counted, nested included if any; times inclusive and may overlap. CPU disabled/null, creation FILETIME exact string, initial failure stays unknown for TLS lifetime.

Bucket admission occurs **at lock acquisition**; call may have started or finished before its frame boundary. Statistics bounds are bucket bounds, not evidence that each original scope lies inside the CPU interval. Two per-frame fields add call_wall and calls; aggregate supplies post_call_to_lock separately. Quantized zero duration does not mean no call: count is still needed.

<a id="variante-lente-rejetée-et-contrôle-ab"></a>

## Rejected slow variant and A/B check

**0.8.14 is not validated.** It embedded the new bucket in every Sample, enlarging it from 696 to 1392 bytes. Smoke timed out after 120 s loading; same PID 12240 later became ready and paused, but tail10 measured **258,952410 ms/frame**, 9 new frames in 2328,671 ms and 2,453125 s process CPU, with zero charsUpdate calls. No active phase of this version launched.

Evidence: **runtime/chars-0814-slow-cadence.json**, protected audit **runtime/chars-0814-before-ab.json**. Exact owned source and manifest **runtime/source-checkpoint-0814-rejected.json**: 186 selected sources, snapshot **runtime/source-snapshots/0.8.14-rejected-cadence**, manifest SHA **d124cf3a5389848c38cb442264ebd248dd1d2b3e830e4c6b6905fec7b5ebaa23**. No game, SDK, save or binary in this source snapshot. The 691 tests and native helper passed: they did not replace real cadence validation.

Controlled return to owned 0.8.13 binary, identities freshly checked, archive **crashes/20261028T164443639055Z-diagnostic-ab-return-0813**, evidence runtime/deploy-chars-ab-0813.json. Check **runtime/chars-ab-0813-cadence.json** recovers **6,683460 ms/frame**, 73 new frames/514,344 ms. Protected files remain identical.

Candidate 0.8.15 keeps Sample at **696 bytes** and uses **preallocated/tagged CharsHistory of 2523600 bytes**, 3600 slots. Copy/reset under the same lock as legacy; no chars-specific allocation per frame, missing tag=error, never zero. Inactive bucket slots are not erased after clear; size=0 excludes them, each reuse writes identity/totals. Check **runtime/chars-0815-cadence.json** recovers **6,551690 ms/frame**, 78 new frames/513,947 ms, then complete campaign retains cadence. **The precise internal cause of variant 0.8.14 is not established**: do not invent an allocator, ABI or GPU defect from these storage/launch changes alone.

Raw maximum is now Sample 3600×696=2505600 bytes plus ring2523600, or **5029200 bytes**, excluding container/temporaries. Not an overall memory reduction against 0.8.14's 5011200 raw bytes; storage/allocation profile differs. Old 0.8.13 used 2505600 raw bytes for Samples alone.

<a id="vérifications-natives-et-coût-de-lobservateur"></a>

## Native checks and observer cost

`tests/test_chars_telemetry.cpp` covers bucket/merge/overflow, reused TID with different creation, unknown/reset, ring overwrite 1→3601 and missing-tag error. A helper deliberately holds the lock after the synthetic call; captures prove interval separation without acting on the game. First test build lacked NOMINMAX, then corrected; a ring test altered its frozen input before a 15-call assertion, fixture isolated then corrected. Neither rejection was a Game-call failure.

**runtime/chars-native-0815/controller.json**, SHA **247cc6a96445e42fdf567c9df0c430b95f845c7022d0a52ce886251a00ab7a69**, retains stdout/owned binaries, source fingerprints, SDK header/library and symbols. 0.8.14 evidence remains separate under runtime/chars-native-0814. v100/O2/x64 microbenchmark, single-threaded without contention, TLS creation warmed: 3 processes×7 pairs×100000 calls, mean complete timer/recording duration **0,067416 µs legacy versus 0,105523 µs split**, difference 0,038108 µs. Ambient load/quantization remain; excludes first GetThreadTimes, history copy/reset, Sample merge, JSON construction and actual overall probe cost.

**691 Python tests pass in 22,29 s**, 39 new checks; native v100 successful. Analysis checks calls/totals/means/maxima, legacy=call+post, threads/overflow, precise identities and truncated/complete series. CPU profiles remain separate OS endpoints, recomputed from raw counters with unbounded signed residuals.

<a id="campagne-réelle-heng"></a>

## Real Heng campaign

KenshiProbe_test copy reloaded with pause/Edge-lock protection, Heng prepared, 10 s x1 and stable readiness, then three requested 12 s phases, pause/x5/pause, each with 3 s warmup. Observations requested every 0,5 s, full inventories bounded to 500 at both ends, SDK roles copied paused before/after sequence. game_total_hours stationary while paused and advances **0,5752525329590412 h** in active phase; raw game_time_stamp is not used to measure simulation.

| Phase | Retained frames | Mean interval ms | p99 ms | Chars calls | Mean call/frame ms | Mean post/frame ms |
|---|---:|---:|---:|---:|---:|---:|
| Pause before |1982|6,324554|8,5173|0|0|0|
| x5 |1855|6,746956|8,8393|1855|0,296559|0,000073529|
| Pause after |1922|6,533679|9,0457|0|0|0|

Active: original call total 550,117199 ms, max 0,891700 ms; post total 0,136396 ms, max 0,001600 ms; legacy 550,253596 ms, mean 0,296633 ms/frame. No overflow or unverified chars thread in these windows. Thread 28836 joins GameWorld/Renderer IDs at both endpoint heartbeats and Windows creation at both OS endpoints; no bracketing SDK role has this identity. **Whole-thread CPU 9,859375 s**, not CPU for these calls.

Process CPU: 22,078125/31,3125/23,53125 s over 12,563/12,547/12,593 s, or **1,757393/2,495616/1,868598 logical processors**. Signed residuals **+0,1875/−0,03125/+0,03125 s**, no endpoint-identity omission. Observed populations 405..405/435..440/440..440; successive phases also change time/environment. **No causal comparison or subtraction of concurrent wall probes from CPU/frame time.** Instrumented intervals do not guarantee displayed FPS.

All three main requests admitted without reduction: n1982/**55058 bytes**, n1855/**62409**, n1922/**55063**, compactly re-encoded from results. These are not exact TCP wire sizes; native 64 KiB limit remains. Controller retains budget and any size errors, reducing only getters if needed; missing data never interpreted as zero.

Capture **runtime/scenarios/chars-split-20261028T170111506769Z.json**, completed=true, SHA **f553cfba8aab37bbf54824ab3b7a688be34a9c41b3f4de128970f7992ddb3b2a**. Report **runtime/chars-split-0815-analysis.json**. Replay:

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_chars_split.py runtime\scenarios\chars-split-20261028T170111506769Z.json --expected-sha256 f553cfba8aab37bbf54824ab3b7a688be34a9c41b3f4de128970f7992ddb3b2a --output runtime\new-report-chars.json
```

<a id="état-final"></a>

## Final state

DLL 0.8.15 **298496 bytes/SHA3a7f6f2839dcd8eedf4057b1532adb8854edb0c704d674b5e41d82c63115c45e**, owned PDB **10374144 bytes/SHA62b151b60e4243de0cd651d42884db7f4774ec7cc6fcf397c63a548a64763b32**, under runtime/symbols/0.8.15. Archive **crashes/20261028T165719366149Z-deployment-0815**, evidence runtime/deploy-0815.json; previous version and rejected-variant evidence retained. Still 17 tools, three probes charsUpdate/findPath/Havok, v100 x64; FUNCTION_THREAD_CPU=0, AI_THREAD_CPU=0, NAV_THREAD_CPU=1, COMMAND_TIMING=1. No engine algorithm changed.

Independent audit **runtime/chars-split-0815-final.json**: same game **15772/Unix creation 1793206658.6702836**, copy restored paused/multiplier0 at **404,3333339691162 h**, normal camera/temporary control released/Edge=true, battle inactive. **702/702/738 files** source/copy/snapshot compliant, settings byte-identical to pre-deployment, guards false, fresh watchdog/zero error, WPR inactive, no remaining controller. Helpers **34588/creation1793206656.1918323** and **35104/creation1793206656.1481395**, to freshly recheck before stopping. Last audit stats n3600 admitted in 55048 compact bytes.

Measurement shows a small post-call interval here; it does not locate the rest of a 6,75 ms frame or all character work. A next probe must address the main-thread question, reusing an existing service hook as selected target if needed **instead of Havok**, to retain three profiled systems and avoid a second installation at the same address. Verify prototypes/bindings and distinguish service/command from original before changing anything. No result of this future measurement claimed.

Autonomous deadline 22 h15 UTC/23 h15 Paris unchanged; no user/administrator intervention expected.
