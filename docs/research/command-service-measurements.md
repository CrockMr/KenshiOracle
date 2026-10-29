<a id="coût-mural-des-lectures-mcp-en-pause--28-octobre-2026"></a>

# Wall-time cost of paused MCP reads — 28 October 2026

**96 reads through actual MCP completed in two paused scenes.** For the 40-NPC scene, `get_scene_state` without thread details averages **3,036792 ms inside the native service block**, with **4,205825 ms waiting in the queue** and **16,029792 ms for the complete MCP call**. These clocks describe different scopes. No exclusive CPU, engine gain, or cause of the previous combat p99 is established.

<a id="instrumentation-et-protocole"></a>

## Instrumentation and protocol

Plugin **0.8.11/v100 x64**, still 17 tools and three system probes charsUpdate/findPath/Havok. `KENSHI_PROBE_COMMAND_TIMING=1` enables optional metadata in the existing service callbacks; disabled by default. Other selections remain FUNCTION_TARGET=havokCharacterUpdate,FUNCTION_THREAD_CPU=0,AI_THREAD_CPU=0,NAV_THREAD_CPU=1. No new Game/SDK call, fourth hook, or engine algorithm change.

The measured block includes execute, result assignment, and DebugLog logging. It excludes its own metadata, event signaling, network JSON serialization, sending, and Python/MCP clients. Waiting starts under the lock just before queue insertion; parsing/reception/initial lock acquisition are excluded. MCP duration is measured around the public call. Do not convert differences between these durations into CPU or exclusive transport attribution. Telemetry's own cost is not isolated.

`tools/research/live_command_service.py` reloads KenshiProbe_test with pause protection and Edge lock. First phase: copy without tracked battle. Second: prepare Mongrel, ten seconds at x1 and stable readiness, pause, focus, then create 20 pairs/40 NPCs once. Templates16863-gamedata.base/Bloodraiders and 1227-gamedata.base/Mercenary Guild; mutual hostility verified before creation, without changing relations. The second phase stays **paused**; no active combat is measured there.

Each phase contains 12 reads from each of the four groups below, rotating order and a requested 0,1 s pause between calls. The first read is retained, with no discarded warmup. All scenes are paused, game clock stationary, camera stable, and cohort completely found. Phases also differ in city, camera, and world state: their difference is not a causal marginal per-NPC cost. Preparation is unseeded; no causal comparison with the old x5 combat.

<a id="résultats-retenus"></a>

## Retained results

Durations in milliseconds; each row comprises 12 requests. “Service” = inclusive native wall-time block. “Queue” = waiting before that block. “MCP” = complete controller-side call.

| Scene | Read | Mean service | Service min..max | Mean queue | Mean MCP |
|---|---|---:|---:|---:|---:|
| Copy without battle | ping |0,226133|0,184300..0,303400|3,134567|7,944033|
| Copy without battle | scene |0,092708|0,068300..0,125000|11,185083|15,757383|
| Copy without battle | scene + roles |0,255083|0,206700..0,347700|4,371133|9,360667|
| Copy without battle | statistics n60 |2,169892|1,951600..2,717100|4,149000|14,040442|
| Paused Mongrel40 | ping |0,223400|0,186300..0,285100|5,307075|10,157258|
| Paused Mongrel40 | scene |3,036792|2,862200..3,330000|4,205825|16,029792|
| Paused Mongrel40 | scene + roles |3,169233|2,996300..3,388800|3,131433|15,143408|
| Paused Mongrel40 | statistics n60 |2,202092|1,951900..2,561700|2,485217|12,603625|

The copy's first scene read has **69,785200 ms waiting**, **0,125000 ms service**, and **75,563500 ms complete MCP call time**. This large wait does not establish a long getter execution. Streaming, scheduling, the preceding callback, and other possible causes are not separated here.

Re-encoded compact JSON result sizes: no-battle scene1287..1302 bytes, 40-NPC scene21594..21598, 40-NPC scene with roles22927..22929; n60 statistics approximately 30254..30766 bytes. The paused scene has neither the size nor medical state of the previous active combat's31 KiB. No size reduction was required during these 96 reads; the final audit also accepted n3600 in 49293 bytes.

All services join **T13900/creation FILETIME134376742378013332**. Owner and creation time are verified independently by Windows before/after each phase, in game **PID34260/Unix creation 1793200637.801332**. No old process's TID is reused as a stable identity. `menu_service=true` means service through the restricted Renderer callback, **not menu display**: 2 then 3 ping calls out of 12 take this path while the world is ready. All other reads use GameWorld.

<a id="échec-conservé-preuves-et-restauration"></a>

## Retained failure, evidence, and restoration

The first test `runtime/scenarios/command-service-20261028T151852385261Z.json`, SHA **6ca18fe130af78a5cbca164011b4ed0faedf88763b3d2900b535c4ecac60b86e**, remains completed=false. 48 copy reads, then rejection of the second phase's first ping by the incorrect assumption “Renderer service implies menu.” The response triggering rejection had not yet been added to the raw data; the message corresponds to that controller guard, not detailed evidence of the response contents. The controller now retains the result before validation and accepts/counts Renderer ping calls; regression test added. This correction needs no native modification or new DLL. Restoration/saves/settings of the rejected test compliant.

Accepted test: **`runtime/scenarios/command-service-20261028T152117109875Z.json`**, SHA **5f0bee2a0fc7d8d4971edbe0d8ad99ea6cb25b519d95a9a455cf8ee63fd1e6a2**. Report **runtime/command-service-0811-analysis.json**. Replay:

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_command_service.py runtime\scenarios\command-service-20261028T152117109875Z.json --expected-sha256 5f0bee2a0fc7d8d4971edbe0d8ad99ea6cb25b519d95a9a455cf8ee63fd1e6a2 --output runtime\new-report-service.json
```

The analysis verifies the exact plan and order, monotonic/finite/reconciled clocks, phase-specific frames, thread identity at both boundaries, recalculated compact JSON sizes, paused cohort, derived summary, and restoration. Compact bytes are re-encoded from the result, not an exact TCP/MCP wire measurement. Errors and direct network heartbeat have no such metadata; absence never means zero.

Independent audit **runtime/command-service-0811-final.json**: same PID, pause/multiplier0, **404,3333339691162 h**, normal camera/temporary control released/Edge=true, no tracked battle; **702/702 files** from protected/copy saves and **738 files** from the older snapshot identical. Settings byte-identical to the predeployment state, guards false; fresh watchdog/zero errors, WPR inactive, no remaining scenario controller. Helpers10192 and 29024 require fresh verification before stopping.

Archive **crashes/20261028T151709989767Z-deployment-0811**, evidence runtime/deploy-0811.json; previous separate 0.8.10 binary retained. DLL 0.8.11 **281088 bytes/SHA26452b71822a70e07c0c7cd4cade56c242884bebcef5d0d30e571c3a37d2a730**, separate PDB under runtime/symbols/0.8.11. Initial sandbox compilation C1902, then authorized local compilation succeeded; no Windows administrator privileges added. **609 Python tests pass in 21,17 s**, native v100 tests pass (disabled mode, exact identity, unchanged errors, invalid/non-finite clocks rejected), actual MCP smoke test and strict analysis pass.

<a id="prochaine-amélioration-à-évaluer"></a>

## Next improvement to evaluate

The rich getter's cost warrants limiting detailed reads during acquisitions and retaining statistics after the windows. Before modifying the engine, measure JSON-tree construction/copies and serialization outside the game with owned fixtures. Any demonstrated copy optimization must preserve the contract and be revalidated; none is implemented yet. Also measure commands in a targeted active phase if the question requires that regime. These paused measurements cannot explain the previous combat's p99 66,3855 ms or calculate per-actor CPU cost.

Autonomous deadline unchanged: 28 October22 h15 UTC/23 h15 Paris. No user/administrator intervention expected.
