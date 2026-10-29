<a id="original-mainloop--mesures-0816"></a>

# Original MainLoop — 0.8.16 measurements

Original `GameWorld::mainLoop_GPUSensitiveStuff` measures **1,36 ms wall/active frame** at Heng, for a mean **8,12 ms** callback interval. Entry does not cover whole frame. No exclusive CPU cost, GPU time or engine gain inferred.

<a id="hook-et-périmètre"></a>

## Hook and scope

Selection `mainLoopGPUSensitive` reuses existing service hook; Havok disabled. Three profiled boundaries remain: charsUpdate, findPath and MainLoop. Two dedicated system detours and two service detours give **four effective installations**, versus five with dedicated selection. No duplicate detour on same address.

Supplied SDK declares `void GameWorld::_NV_mainLoop_GPUSensitiveStuff(float time)` in GameWorld.h line 196. Symbol `?_NV_mainLoop_GPUSensitiveStuff@GameWorld@@QEAAXM@Z` and import verified in KenshiLib.lib. Header SHA256 `e1c5566b24df65a42d01e884ac8a45125a3b257298469a544ad557b7f43e802f`; library `d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d`. Local evidence `runtime/main-loop-sdk-0816.json`. No RVA or game code copied into plugin.

`OriginalLoopInvocation<GameWorld>` forwards pointer/float unchanged and calls original once. Native tests check five floats bit-for-bit, including −0, and call count. Timer starts after bucket collection, pause protection and initial command drain. **Initial service excluded; any callback reached inside original remains included**, along with waits, other mods and nested work. GPUSensitiveStuff name is not a GPU measurement.

Profiler retains completed outermost calls only, ends timing before recording lock. Scopes may cross bucket boundaries; mean divides their sum by retained frames. Optional CPU disabled, CPU fields null. Other probes may overlap entry: do not sum/subtract as exclusive costs. Sample 696 bytes and chars history2523600 bytes unchanged.

<a id="validation-et-méthode"></a>

## Validation and method

**705 Python tests pass in 21,44 s**, plus native v100 forwarding/bucket/depth tests. v100 x64 compilation linked. Real MCP smoke checks 17 tools, counters, aliases, sizes and actual data:60 original calls recorded. Paused cadence check observes77 new frames over 512,807 ms, tail10 mean **6,583510 ms**. No slowdown like rejected candidate 0.8.14; precise cause remains unknown.

`tools/research/live_main_loop.py` reloads KenshiProbe_test with pause protection/Edge lock, prepares Heng for10 s x1 then waits for readiness. Three requested 12 s windows follow, each after 3 s warmup: pause,x5,pause. Observations requested every 0,5 s, complete inventories limit 500 and endpoint OS identities. Copy then reloaded paused, camera control released. No build or other benchmark during acquisition.

| Phase | Frames/calls | Original mean ms/frame | Max call ms | Mean interval ms | Interval p99 ms |
|---|---:|---:|---:|---:|---:|
| Pause before | 2021/2021 | 1,084158 | 7,267700 | 6,176169 | 8,4886 |
| x5 | 1549/1549 | 1,363674 | 29,271500 | 8,121418 | 10,9988 |
| Pause after | 1565/1565 | 1,356870 | 7,643000 | 8,016632 | 12,1196 |

No skipped nesting, overflow or unknown thread in these windows. Equal aggregate calls/frames does not prove a call in every unshown frame: individual series retains only 100 final rows.

All selected calls join T26508/creation FILETIME `134376829972344393`, CPU identity present at both OS endpoints and same game_thread/service_thread at endpoint heartbeats. **Whole-thread** CPU:9,296875/9,609375/10,25 s over OS windows12,5/12,609/12,578 s. Not this function's CPU. Process CPU22,3125/29,953125/23,0625 s, or1,785/2,375535/1,833559 logical processors; signed residuals+0,125/+0,03125/−0,015625 s, no endpoint omission.

Original charsUpdate:0/0,394788/0 ms/frame. Populations388..388/439..456/456..456; game_total_hours progression0/+0,5779018402100178/0. Town, time and state evolve between phases: no causal comparison to pauses or earlier version. Callback intervals do not guarantee displayed FPS. OS windows and buckets differ; do not calculate “remaining CPU” by subtraction.

Main requests admitted without reduction:n2021/57137 bytes,n1549/62156,n1565/57079. Compact re-encoded JSON bytes, not exact TCP/MCP size. Native64 KiB limit unchanged, budget plans/strict bounding retained.

<a id="preuves-et-rejeu"></a>

## Evidence and replay

Complete capture `runtime/scenarios/main-loop-20261028T174602988613Z.json`, SHA256 **c66a4e7d0f8f638f0509d2dbc56610be0bc9411de9525a029f982c31e986427a**. Analysis `runtime/main-loop-0816-analysis.json`. Wrapper checks scope, reuse, counters, CPU and identity joins; chars analysis retains default0.8.15 behavior.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_main_loop.py runtime\scenarios\main-loop-20261028T174602988613Z.json --expected-sha256 c66a4e7d0f8f638f0509d2dbc56610be0bc9411de9525a029f982c31e986427a --output runtime\new-report-main-loop.json
```

DLL 302080 bytes, SHA256 `e401d956ee236034dd7feac7d9830140de0169a7bfa254bfbc2f69f353a45d8b`; owned PDB10374144 bytes, SHA256 `660a675987d25a40da7eca128242cff4cf91132893fb4ba16e530678ea6539b7`. Copies under `runtime/symbols/0.8.16`. Archive `crashes/20261028T174304038130Z-deployment-0816`, evidence `runtime/deploy-0816.json`. Only project processes' path, command and creation rechecked before stopping; old 0.8.15 preserved.

Audit `runtime/main-loop-0816-final.json`: same game PID32008/Unix creation 1793209397.234438, copy paused/multiplier0 at 404,3333339691162 h, normal camera, temporary control released, Edge=true, battle inactive. **702/702/738 files** source/copy/snapshot identical; settings identical to beforehand, guards false, fresh watchdog without error, WPR inactive, no remaining controller. Helpers5796/creation1793209394.2727556 and38020/creation1793209394.2255044: freshly recheck identities before stopping. Final stats n3600/57161 bytes.

Next proposed boundary: original Renderer::_NV_update through its existing hook, replacing MainLoop. Same limit of three profiled systems, forwarding/SDK signature verified, cadence checked before activation. No anticipated result or automatic GPU attribution. Autonomous deadline22 h15 UTC/23 h15 Paris unchanged; no manual intervention expected.
