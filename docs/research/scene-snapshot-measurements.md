<a id="sauvegardes-de-scénario-et-reprise-en-pause"></a>

# Scenario saves and resuming in pause

To reduce generation differences between experiments, `save_scene_snapshot` uses the public **SaveManager::save(const std::string&, bool)** method, declared in SaveManager.h, linked with v100 x64 and observed natively. Names must begin with `KenshiProbe_test_scene_`, followed by 1..40 ASCII letters, digits, hyphens or underscores. The plugin requires a paused test battle, refuses any existing target file or directory, and manages at most eight snapshots during its session. Overwriting is never offered.

The NPC name/prefix are retained without a game pointer. `load_save` restores this tracking only for a snapshot created by the **same plugin session**. After restarting the game, the folders remain available but the association is not recreated automatically. This initial implementation requires an ASCII save path; the plugin checks the directory and target absence through Win32 before asking the engine to write.

An `accepted` response means “write requested,” not “complete files.” The test waits for `ping.save_signal=0`, quick.save and two consecutive identical SHA-256 manifests before reloading. It also checks rejection of a second save with the same name and unchanged files during loading.

<a id="première-observation--074"></a>

## First observation — 0.7.4

`runtime/scenarios/snapshot-20261028T021855834633Z.json` describes a new snapshot of two hostile NPCs at Mongrel, containing 739 files. Two reloads through the real MCP stdio tools find exactly the same medical values and positions; snapshot files remain identical and overwriting is refused. However, the first ready pings report **paused=false**, and game times differ: 404,369667 then 404,368881. The client subsequently pauses the game, but that delay prevents describing initial readiness as a frozen resume.

<a id="pause-avant-publication--075"></a>

## Pause before publication — 0.7.5

Existing GameWorld/Renderer callbacks now apply `userPause(true)` as soon as a managed snapshot is ready and SaveManager has no pending signal. The heartbeat retains loading=true until this pause is applied. No hook is added. Ordinary KenshiProbe_test loading retains its existing path; this behavior applies to snapshots recognized within the session.

`snapshot-20261028T022539600581Z.json`, 738 files, confirms **paused=true at the first ready ping in both loads**, with an identical clock of 404,3666667938232 hours. Health and blood match. Nevertheless, the comparison guard reports a maximum vertical difference of **1,897339 units**, beyond its one-unit threshold; it retains `matches=false`. X/Z match. This result is not artificially reclassified as a completely controlled comparison.

A further targeted observation reloads the same snapshot without creating another: `snapshot-paused-settling-075.json`. Two loads are observed at approximately 0, 1, 3 and 5 seconds while paused. Clock, health and positions stay fixed throughout each series; both series match exactly, without file changes. This does not demonstrate that waiting five seconds resolves vertical variation: the preceding difference simply did not recur in these two series. Every future comparison must verify its initial state and retain rejected attempts, rather than relax the threshold.

`set_camera_free(enabled, lock_edge=true)` can protect edge scrolling after loading a managed snapshot. An already-applied enabled value does not invoke the mode change again, preserving the pose. lock_edge=false does not request this protection; existing temporary ownership is still released on the next load. Before writing a snapshot, the plugin restores the initial Edge scrolling setting because the engine may save its own preferences.

The test also backs up settings.cfg bytes and restores them at the end, then reloads the initial copy and checks camera, mode and pause. The 702 KenshiProbe_validation files and 702 KenshiProbe_test files still match the reference manifest. Guards `runtime/scene-snapshot-state.json` and `runtime/snapshot-settle-state.json` have restore_required=false. An interrupted attempt with restore_required=true must recover its recorded backup before another run; the test refuses to overwrite it.

`tools/research/live_scene_snapshot.py` runs through real MCP stdio. Offline tests check protected names and visible-state comparison: health, position, missing actor, incomplete reading and unconscious state. This step fixes an important part of visible state; it does not prove determinization of every AI state, equipment or reinforcement.
