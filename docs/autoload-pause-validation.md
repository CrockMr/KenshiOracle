<a id="reprise-de-la-copie-en-pause--084"></a>

# Resuming the copy paused — 0.8.4

The plugin now pauses the KenshiProbe_test copy before world_ready becomes true. A post-deployment startup and a real MCP restart confirmed that the first observed ready state was paused, without the controller sending a pause command.

<a id="correction"></a>

## Fix

The old pause-before-readiness behavior applied only to snapshots owned in memory. The 0.8.3 precheck therefore found the automatically loaded copy unpaused; this observation remains in runtime/identity-083-startup.json.

load_save now schedules pause for the exact name KenshiProbe_test or an owned snapshot. Existing GameWorld/Renderer callbacks wait for an initialized world, no reset/loading and a null save-manager signal, then call GameWorld::userPause(true). world_ready remains false while this pause is pending. Other save names do not activate this new rule; no trial loads the protected validation save.

Declarations userPause(bool), isPaused(), isLoadingFromASaveGame(), initialized/gameResetting and SaveManager::load/signal were reread in SDK headers. No new offset, hook or engine algorithm. Still v100 x64, three system probes and 17 MCP tools. The 0.8.3 TLS cache and AI_THREAD_CPU=0 mode are retained.

ping.test_save_pause_on_ready_available advertises the capability; ping.load_pause_pending describes waiting. load_save(...).pause_on_ready is now also true for KenshiProbe_test. The watchdog can briefly publish loading=true after the first ready ping because its file updates separately; the final check verifies its return to false.

<a id="observations-réelles"></a>

## Real observations

Script tests/live_autoload_pause.py uses stdio MCP. Its normal path sends no pause command, changes no speed, prepares no scene and writes no save. The first observer started before the watchdog. The second freshly verifies game path, command and creation before one restart_game request.

| Trial | PID | First observed ready ping | Following scenes |
|---|---:|---|---|
| Post-deployment startup |33948|frame544, pause=true, speed0, pending=false|frames545..970, 3,041826 s|
| Requested restart |35336|frame418, pause=true, speed0, pending=false|frames419..825, 3,050325 s|

All four scenes in each trial have exactly 404,3333339691162 game hours. While waiting, 65 then 50 observations carry load_pause_pending=true and world_ready=false. The record counts 74 then 59 pings in total. There is no fallback_pause or error. Observations do not cover every engine frame and do not prove determinism of the entire character state.

Evidence:

- runtime/scenarios/autoload-pause-20261028T090504090106Z.json, completed=true, SHA-256 **54c958e1f7ef8a4527b1dc42395f8063ab2f0157b3ce6747b4645aa3ee175687**.
- runtime/scenarios/autoload-pause-20261028T090725294145Z.json, completed=true, SHA-256 **90954d4f15b508f6461abafba2a62911b414cc5d9d773b83a0f5da115952e208**.
- runtime/autoload-084-validation.json recalculates invariants from both raw captures. The second has acknowledgment and archive **crashes/20261028T090726.287883Z**, reason requested, with log retained. PID/creation actually changed from 33948/1793178313.279526 to 35336/1793178451.3026247.

<a id="état-laissé-et-limites"></a>

## State left behind and limits

**291 pytest tests pass in 4,53 s**, v100 x64 compilation/linking succeeded. Both real trials verify the new native policy; fake tests do not constitute this evidence.

Deployment archive: crashes/20261028T090445969777Z-deployment-084, old DLL0.8.3/log/config/settings. WPR inactive and game33512/watchdogs28140/33880 identities checked before stopping only project processes. Own 0.8.4 symbols are retained in runtime/symbols/0.8.4, without adding a game binary to Git.

runtime/autoload-084-final.json verifies game35336 paused/normal mode, camera control released and Edge=true, watchdog fresh without error/autoload successful, seven SDK roles and 17 tools. All **702/702/738 files** of source/copy/old snapshot and settings.cfg bytes match this deployment's prior state. Both preference guards are false, WPR inactive and no test controller remains active. Helpers27108/38500 at the last reading; identities must be reread before any action. Config/activation boundary1793225700 unchanged.

The camera can still respond to edge scrolling when its preference is restored; this validation concerns pause and clock, not permanent camera stillness. current_save retains a sticky internal name and still does not prove the loaded folder. Old snapshot ownership is not reconstructed after restarting.

The administrator Heng capture remains deferred without intervention requested now. The next performance diagnosis should target the remaining worker, for example GameWorld::charsUpdateUT with its real prototype replacing the AI probe; no engine optimization gain is established here.
