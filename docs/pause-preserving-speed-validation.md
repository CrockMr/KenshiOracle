<a id="restauration-sans-reprise-intermédiaire--087"></a>

# Restoration without an intermediate resume — 0.8.7

KenshiProbe_test restoration now sets x1 while preserving pause in the same native command. The real check returns exactly **404,3333339691162 game hours**, as after initial loading, following two validation reloads and a third cleanup reload. The copy remains paused, saves and preferences intact. No performance gain or determinism of the entire NPC state is established.

<a id="changement"></a>

## Change

The old helper issued three separate requests: remove pause, set x1, then pause again. The game loop could advance between requests; the 0.8.5 stack campaign's final clock was thus slightly different from autoload time.

`set_game_speed(speed, preserve_pause=True)` uses methods declared in GameWorld.h: `isPaused()`, `setGameSpeed(float,bool)` and `userPause(bool)`. Both mutations finish on the main thread within the same command processing, before returning to originalLoop. The boolean parameter is checked before mutation; no direct access to a private engine field or new API is introduced.

The default remains `False`, preserving the existing protocol. The response adds `paused_before` and `preserve_pause`; `ping.set_game_speed_preserve_pause_available` advertises the capability. `restore_test` requires that capability and pause after loading, sets x1 while preserving it, then compares **game_total_hours** before/after. It no longer issues a resume request between these steps.

Preservation mode requires **0 < speed <= 5**. The zero-speed/pause-preservation combination is rejected before mutation by both MCP and plugin. Use the pause command to stop simulation. Tool count remains 17; the three system probes and their charsUpdateUT selection are unchanged.

<a id="validation-réelle"></a>

## Real validation

Source: `runtime/scenarios/restore-pause-20261028T105200176995Z.json`, completed=true, SHA-256 **da3d1dc9eae9bfa55e7e68a7ade9c57f5c62be715721effdc6790c975f89253d**. Stdio MCP transport; malformed requests are also tried directly over the native protocol to verify the plugin guard.

Game PID **28920**, Unix creation **1793184744.2008762**, verified executable `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe --norestart`. These identities apply only to this session.

| Case | Observed result |
|---|---|
| Initial loading | First observed readiness paused; time 404,3333339691162, unchanged across the next three reads. |
| x2, x5 and x1 settings while paused | Response paused_before=true, paused=true, effective multiplier 0; the next nine reads retain exactly the same game time. |
| Explicit resume after selecting x2 while paused | Effective multiplier 2, paused=false; speed selection retained for resumption. |
| x2, x5 and x1 settings during simulation | paused_before=false and paused=false, effective multiplier equals the request. |
| Positive speed without the new parameter | Resumes simulation as before. |
| Malformed native boolean | Rejected before mutation; pause and game time preserved. |
| Zero speed with preservation | MCP and native rejection; native rejection also verified during simulation, which remains at x1. |
| Two reloads, then cleanup | Pause and initial time exactly restored; normal camera, then temporary control released. |

Independent check `runtime/restore-087-final.json` confirms pause, multiplier 0, initial time, Edge=true, camera ownership false, 17 tools, seven SDK roles, three probes, fresh watchdog without error and inactive WPR. All **702/702/738 files** of source/copy/snapshot match protected manifests; settings.cfg is byte-identical to the pre-deployment state. No test controller remains active. Both watchdog helpers remain bounded by the existing deadline.

**v100 x64** compilation succeeded; **367 tests pass in 5,24 s**. Contract tests notably verify that the default retains the old request and invalid parameters are not sent. The engine validation above checks SDK-call behavior; the Python fixture does not claim to emulate it.

<a id="tentatives-conservées-et-limites"></a>

## Retained attempts and limits

The first 0.8.6 controller incorrectly added game_time_stamp stability. Attempt `restore-pause-20261028T104258395419Z.json` remains completed=false, with its sources retained under runtime. This raw counter continues while paused, as already documented in [clock measurements](research/simulation-clock-measurements.md). Independent check `runtime/pause-stamp-086.json` confirms progression of 2,4452879 s over 2,4452880 QPC s, across 339 frames, with **zero game-hour progression**. The guard was corrected to use the simulation clock; no discrepancy in that clock was tolerated. The camera was released after initial cleanup failed.

Intermediate 0.8.6 validation `restore-pause-20261028T104713355682Z.json` then succeeded. A check of previously unobserved boundaries revealed in `runtime/speed-boundaries-086.json` that zero with preservation of an unpaused state retained previous speed x5. This observation is preserved; 0.8.7 replaces this ambiguous behavior with explicit rejection in both interfaces.

A compound command is not an atomic transaction across all workers. Observations prove pause at boundaries and no simulated-hour progression in these scenarios; they do not prove absence of all asynchronous activity between the two SDK calls or complete NPC memory identity. The camera can scroll again after restoring its edge preference. No system security setting, administrator privilege or new ETW capture was needed.

Final deployment: `crashes/20261028T105221075324Z-deployment-087`, evidence `runtime/deploy-087.json`. Game and 0.8.6 helper identities were rechecked before stopping. Own symbols retained under `runtime/symbols/0.8.7`: DLL SHA-256 **eb6760d01e382efaddb0b3274349f6a30d506ee80a2fbc79e10a7f8c778abdba**, PDB **ff179bd209359ddc04d4d271e3b245e305328897e4c3e1a8fb2e883e6238e2ea**. No game binary or decompiled code added to the repository.
