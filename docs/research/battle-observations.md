<a id="préparation-de-bataille--observations-natives"></a>

# Battle preparation — native observations

Protocol 0.7.1 adds a sixteenth MCP tool, `prepare_battle_scene`, without a new system hook. It is restricted to the paused `KenshiProbe_test` copy loaded by the probe. The template must match an already loaded non-player `CHARACTER`. The player group is placed near Heng, streaming is allowed ten seconds at x1, then NPCs are created nearby. The command gives pairs mutual melee objectives; subsequent states are observed separately.

Signatures come from public headers `RootObjectFactory.h`, `Character.h`, `GameData.h`, `MedicalSystem.h`, `OptionsHolder.h`, and `InputHandler.h`. The creation path using world position and a non-player faction was also checked against [public KenshiCoop code](https://github.com/nhoral/KenshiCoop/blob/main/src/plugin/game/EngineSpawnCombat.cpp). The plugin calls SDK methods linked with v100 x64; it copies neither RVAs nor decompiled code.

The first 0.7.0 test, `runtime/scenarios/battle-20261028T012023Z.json`, was rejected before any creation: `findValidSpawnPos` returned a location beyond the permitted radius. Its signature alone does not document search conditions, so its result was not used. The copy reloaded successfully. In0.7.1, placement directly uses world positions bounded relative to the player, then checks the factory's actual returned position, which adjusts height to terrain. Out-of-bounds creation still requires a reload.

Test `battle-20261028T012417Z.json` created two `Samurai Conscript` actors, template `54292-rebirth.mod`, faction `Traders Guild`, in **1,2242 ms** on the main thread. Initial positions were four units apart. Both actors are found in each of twenty observations, approximately one second apart, over 20,422 seconds at x1. Both enter combat mode and move. No received-melee-attack state is captured; blood values remain 95,3399 and 96,9301, respectively. **Creation and objectives are confirmed; landed hits are not yet confirmed.** One-second sampling can miss a brief state, and blood alone does not detect all injuries.

The final 600-frame window has a mean of 8,4600 ms and p99 of 14,647 ms. Two global navigation requests, on a thread separate from GameWorld, return false:155,028 and 161,408 ms wall time,140,625 ms CPU each, output0→0. These calls carry no character identity; they are not attributed to the two NPCs. This window does not represent the entire test or constitute a heavy-battle benchmark.

The copy was reloaded after the test, same process PID26144, reference camera and normal mode restored, pause enabled, NPC tracking cleared. Edge scrolling is observed false during the scenario, then true after restoration. Source `quick.save` SHA-256 remains `04488b407bc57f8fdb1cbbdd8d1afc006d2b179f020ff89a9acf459df934fbeb`. The settings file retains Edge scrolling=1; its overall hash changed because of ordinary `autosaveindex` and `continue` fields, without an observed preference change.

Script `tools/research/live_battle.py` reloads the copy before and after, retains raw responses/errors, checks PID/camera/pause/speed, and measures overall CPU over the observed interval. Example:

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
.venv/Scripts/python.exe tools/research/live_battle.py 54292-rebirth.mod --town Heng --pairs 1 --seconds 60
```

Generation has no controlled seed; identical parameters do not guarantee identical equipment, stats, or progression. Before comparing x1/x5 or increasing actor counts, obtain evidence of actual combat and record injuries and tasks that really complete. Do not turn entering combat mode into a hit count or task throughput.

An initial 60-second extension, `battle-20261028T012604Z.json`, was interrupted after 12,234 seconds by `PermissionError` opening `runtime/state.json` during its Windows replacement. The game did not restart and restoration succeeded. This truncated interval is not counted as a60-second test. Shared reader `read_runtime_state` now retries up to four times at 25 ms intervals, without returning stale state or hiding persistent error; MCP and city/battle scripts use it. Two tests cover recovery and persistent rejection; full suite:76 tests passed in 3,87 s. The watchdog retains its separate write-side fix.

After correction, `battle-20261028T012803Z.json` completes **60,125 seconds**,59 observations, and full restoration. Both actors remain tracked, both in combat mode; no received-attack state or unconsciousness captured, blood never below initial 92,94994 and 90,31126. The final 600-frame window contains no ≥10 ms navigation call. This result does not justify increasing cohort size.

A separate hypothesis was then tested: earlier tests' camera stayed more than 2000 units from Heng. `--focus` calls `focus_town` **after** moving the players, in pause, then waits two seconds. In `battle-20261028T013021Z.json`, the free camera is effectively about **20,106 units from the NPCs**, with a stable position over 30,734 seconds and 30 observations. Blood remains unchanged again, both actors in combat mode, no received attack or unconsciousness captured. Observed camera proximity is therefore insufficient to obtain hits in this test. Because random generation is uncontrolled, these tests do not permit causal performance comparison. Camera mode, view, Edge scrolling, and pause restored again.

Next, examine the actual selected target and detailed health, then possibly use **already hostile** factions without changing relations. Public declarations located but not yet called by the plugin: `Character::getCombatClass`, `CombatClass::_getAttackTarget` (`combat/CombatClass.h`), `MedicalSystem::getPartCount/getPart(unsigned __int64)` and `HealthPartStatus::flesh/fleshStun`, `FactionRelations::isEnemy/getFactionRelation`. Current states establish neither absence of all blunt injury nor the reason for missing observed hits. Do not simply repeat20/60 seconds or start x1/x5 comparison before a new hypothesis and verified actual combat.

<a id="cibles-et-santé-détaillée--072"></a>

## Targets and detailed health — 0.7.2

These reads are now linked and observed natively. `battle-20261028T013705Z.json` contains **113 observations over 30,204 seconds**, requested interval0,25 second. All seven body parts are available and finite in every observation: initial `flesh` sums700 and 875, initial `fleshStun`0; no changes in these sums or blood. The template can generate different races/stats even within a pair.

For `KenshiProbeFight_1_0`, the target resolves the intended opponent in 72 observations and remains unresolved in 41; for `..._1`,46 and 67. No target outside the cohort is observed. SDK states include `CHOP_WEAPON` (0), but also `TARGET_PATHFINDING_STARTUP` (10) and `TARGET_PATHFINDING` (11), plus decision/startup states. A `CHOP_WEAPON` state still does not prove a landed hit. Reproducible analysis: `tools/research/analyze_battle.py`, result `runtime/battle-analysis-072.json`, raw SHA-256 retained. Medical differences are reported as raw values, without invented hit counts or attacker attribution; four tests cover blunt signal without blood loss, external target, absent actor/truncated health, and an older capture without health.

The selected faction this time is **United Cities**, versus Traders Guild in earlier tests of the same template. The old selection took the first matching template in the unordered list, so this parameter was not constant. These tests must not be pooled as identical repetitions. Since0.7.3, faction ambiguity is rejected unless selection by name is explicit. An opposing template may be supplied, but creation requires already mutually hostile factions; relations are not modified.

Including `combat/CombatClass.h` required adding `Include/kenshi` to the compiler path because this SDK header includes `Enums.h` without a prefix. v100 compilation and official linking then succeeded. No memory-layout fix or new hook. Initial0.7.2 telemetry also showed irrelevant numbers in null engine handles:0.7.3 now renders those handles `null` after `hand::isNull()` and does not attempt resolution.

<a id="combat-effectif-à-mongrel--073"></a>

## Actual combat at Mongrel — 0.7.3

The detailed Heng inventory showed only directional Outlaw→United Cities hostility among factions in its hundred rows; it was not used to force relations. At Mongrel, `enemy-candidates-Mongrel-073-ready.json` observes **Bloodraiders↔Mercenary Guild** already hostile in both directions. Selected templates: `16863-gamedata.base` and `1227-gamedata.base`, with factions explicitly chosen. Preparation responses confirm **−100 in each direction** before creation. No relation-modification method is called.

The first two Mongrel inventories were interrupted by a rejected control command during zone transition; restorations succeeded. The second test showed that waiting after `set_game_speed` did not protect that call immediately after unpausing. The script now uses x1 already established by `restore_test`, waits for stable readiness, and retries **only** the pause command's `world not ready` rejection, which occurs before mutation. Transport errors and NPC creation are never automatically retried. Four tests cover stability, deadline, and retry policy. The next Mongrel visit succeeded without changing the plugin.

| Test | Transport | NPCs created | Observation | Observed result |
|---|---|---:|---:|---|
| `battle-20261028T014952Z.json` | Local TCP | 2, creation 1,461 ms | 45,141 s /169 reads | Both actors injured, received attacks, Bloodraider unconscious observed at 33,657 s |
| `battle-20261028T015352Z.json` | **Actual MCP stdio** | 10, creation 3,517 ms | 45,125 s /165 reads | All ten actors injured, up to ten under attack and five unconscious; first KO observed at 10,187 s |

All ten members are found at each read; their seven body parts remain readable. The first five unconsciousness observations are at 10,187;10,734;14,875;28,750;43,750 seconds. These are observation bounds with a requested0,25-second interval, not exact timestamps of hits or completed AI tasks. Blood can increase slightly through regeneration: analysis now separates first change, first decrease, and first increase. One actor has negative blood in the SDK result; that raw value is not artificially truncated.

**Reinforcements intervene.** The two-actor test contains50 observations of an external `Shinobi Guard` target; the ten-actor test contains25 across all actors. NPCs can also target a member other than their initial partner. These tests describe an urban battle with reinforcements, not an isolated duel or exact attribution of injuries to an attacker. They establish actual combat; they do not alone prove that common faction membership was the sole cause of previous injury-free tests.

In the ten-actor test, update-list population varies from **136 to 305**. The final 600-frame window, IDs 83614..84213, yields a10,258 ms mean and 14,402 ms p99. `findPath` counts 300 calls on a thread other than GameWorld:299 true, one false. All eleven retained ≥10 ms calls, without truncation, include ten true calls of 10,210..11,632 ms with 92..98 output elements, and one false of **130,579 ms /125 ms CPU**, output **0→6**. A false return therefore does not imply empty output. Calls remain global, without character identity: no attribution to cohort NPCs or evidence of direct GameWorld blocking. Whole-process CPU reaches2,292 equivalent logical processors over the interval enclosing observation, including game-side command processing.

The final window does not measure the whole battle. Cohorts, generated stats, populations, combat phases, and transports differ: **no marginal per-NPC cost, optimization gain, or TCP/MCP overhead can be calculated by comparing these two tests**. The script now retains SHA-256 values of the installed DLL, mods.cfg, and settings.cfg; these fingerprints exist in the second test, not retroactively in the first. The test's stdio server was closed after restoration; its log is `runtime/mcp-battle.stderr.log`. This test still does not attest permanent MCP registration in the Codex client.

Both tests retained the same PID31284, then reloaded the copy and restored camera, normal mode, Edge scrolling, and pause. Before/after source SHA-256 values match the control. Analysis with fingerprints of all three captures: `runtime/battle-analysis-073.json`. Reproducing the second path:

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
.venv/Scripts/python.exe tools/research/live_battle.py 16863-gamedata.base --faction Bloodraiders --opponent-template 1227-gamedata.base --opponent-faction 'Mercenary Guild' --town Mongrel --focus --interval .25 --seconds 45 --pairs 5 --mcp
```

The next campaign must better fix initial actor state and quantify reinforcements before comparing speeds. The navigation-call audit must also explicitly accept this new capture format and retain the false return's partial output; do not introduce a boolean-result cache on this basis.
