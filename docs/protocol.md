<a id="protocole-kenshiprobe--oracle-095-état-et-scénario-01"></a>

# KenshiProbe protocol — oracle 0.9.5, state and scenario 0.1

<a id="transport-et-périmètre"></a>

## Transport and scope

The plugin retains the 0.8.20 architecture: TCP **127.0.0.1 only**, default port47800 (`KENSHI_PROBE_PORT` at startup), one UTF-8 JSON request per line and one JSON response per line with the same `id`. The client opens one connection per request. Network request/response sizes remain bounded to 64 KiB; complete state passes through a file, never an enlarged response.

```json
{"id":"req-1","command":"get_clock","params":{}}
{"id":"req-1","result":{"day":2,"hour":12,"elapsed_seconds":216000,"speed":0,"paused":true}}
```

Errors use `{"id":"req-1","error":{"code":"invalid_request","message":"..."}}`. Command, parameter, unavailable-state, timeout, existing-file, and unimplemented-API errors are explicit. Python rejects malformed, oversized, or mismatched-identifier responses. A mutation with an uncertain response is not automatically resent.

The network thread parses and queues commands under `CRITICAL_SECTION`. Existing GameWorld and Renderer SDK hooks execute them on the main thread; Renderer permits service in the menu. Heartbeat comes from a copy published under lock, readable even when no world is ready. State reads never leave the game thread; serialization/writing of their JSON copy may occur on the network thread. New log lines use the `[KenshiOracle]` prefix in the RE_Kenshi log; project, DLL, and MCP-server names remain KenshiProbe.

<a id="commandes-oracle"></a>

## Oracle commands

Other historical scene and telemetry commands are retained. The following are phase 1 commands; parameters below belong to the native protocol, followed by MCP differences.

| Native command | Parameters | Result and conditions |
| --- | --- | --- |
| `ping` | None | Plugin/game versions, `schema_version:"0.1"`, `instance_id`, `process_id`, availability and historical capabilities. `instance_id` identifies a launch, not a character. |
| `get_clock` | None | `{day,hour,elapsed_seconds,speed,paused}`. Ready world required. |
| `dump_state` | `filename`, simple ASCII name of 1 to 100 alphanumeric, `_` or `-` characters, followed by `.json` | `{path,schema_version,bytes,identity_source}`. Ready paused world, no active advancement, origins prepared. Destination under `KENSHI_ORACLE_OUTPUT`, otherwise `oracle-dumps/` in the working directory. Absolute path returned. Windows reserved names rejected, never overwrites. |
| `pause` | Boolean `paused` | Actual pause; explicit pause interrupts active advancement. |
| `set_game_speed` | `speed` from 0 to 5, optional `preserve_pause` | Historical contract retained. `preserve_pause:true` requires positive speed and preserves pause. |
| `run_until` | Absolute `target_seconds` on the game clock; real `timeout_seconds`, default120, native bounds 0,1 to 3600 | Immediately returns `{operation_id,status,target_seconds,clock}`. Requires a paused start and positive speed explicitly commanded since the last load. The hook watches the crossing, then pauses; it does not block the main loop. |
| `run_until_status` | `operation_id` | Status `running`, `completed`, `cancelled`, or `timed_out`, target and observed clock. Unknown identifier rejected. |
| `cancel_run_until` | `operation_id` | Cancels the identified active operation and pauses again. |
| `load_save` | `name`, optional `lock_edge` and `pause_on_ready` | Schedules loading an existing save. For the oracle, the client supplies `pause_on_ready:true` and waits for readiness; before that, `accepted` does not prove loading finished. |
| `issue_order` | `type:"move"` or `"attack"`; exactly one of `character_id`, `squad_id`; `position:[x,y,z]` for move, `target_id` for attack | Requires a paused checkpoint and loaded identities. Calls the public order API; does not teleport actors. Returns acceptance and affected-actor count, not evidence the action completed. |
| `get_frame_stats` | `n` from 1 to 3600; `detail:"aggregates"` by default or `"full"` | Retains compact0.8.20 implementation. Full details remain explicitly available to historical tools needing them. |
| `restore_scene_control` | `camera_center`, `camera_orientation:[w,x,y,z]`, signed `camera_zoom`, `free_camera`, `edge_scrolling`, `speed`, `paused`, nullable `camera_follow_id` | Applies controls from a prior `get_scene_state` and releases scrolling protection in the same command. A followed target must still be a loaded character. Pose/settings must be reread; acceptance alone does not validate restoration. |
| `prepare_scene_control` | Same camera/time parameters | Requires a ready, already paused world and no pending preparation. Validates target before mutation, applies mode/orientation/zoom/follow and speed selection, resets extra follow offset to zero, preserves pause, and locks scrolling. Returns `prepared:true`, `token`, and `camera_restore_token`. |
| `commit_scene_control` | Opaque preparation `token` | Checks instance/epoch, pause, lock, and prepared controls. Corrects all three axes using the actually observed center, then applies final settings and releases the lock. Returns `restored:true`, `prepared:false`, `camera_restore_token:null`. A stale token or concurrent change fails explicitly. |

`get_scene_state` adds `selected_game_speed`, `camera_orientation`, `camera_zoom`, `camera_node_position`, and `camera_follow_id` to historical fields. `camera_zoom` is the camera node's **signed local Z** coordinate, bounded to±1e7. It must be strictly negative in strategic mode; zero and positive values are allowed in free mode. Preserve the captured value. `camera_node_position:[x,y,z]` exposes this local position for diagnosis. Restoration applies final mode before pose, then passes quaternion and signed zoom together to the SDK API. The [Meitou saved-camera documentation](https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/camera.md#saved-camera) confirms this convention; calls use public declarations `CameraClass::getCameraNode` and `manuallySetOrientationAndZoom`.

These control data are outside the shared-state schema. Following a loaded character can be restored; an absent identity or another target type produces `not_found` before control mutation. Following a non-character object remains `TODO(ORACLE-CAMERA-NONCHARACTER)`, with no restoration claim.

In0.9.5, `get_scene_state` also exposes nullable `camera_restore_token` and diagnostic `camera_follow_offset`, `camera_follow_position`, `camera_follow_center_delta`. Public field `objectCurrentlyFollowingOffset` is an **additional** offset relative to the pivot calculated by the engine. It must not be filled with `center − character position`. After preparation stabilizes, commit calculates `new offset = current offset + requested center − observed center`. No constant height bias is assumed. Pending state contains only JSON parameters, complete identities, token, and epoch, never a retained actor pointer; loading or epoch change invalidates it.

MCP tool `restore_scene_control` orchestrates preparation, observation, commit, and strict verification; the historical same-named TCP command remains available with its original single-step application scope. For verified restoration, use the MCP tool or prepare/commit protocol followed by rereads. MCP result retains native control fields at top level and adds `response`, `scene`, `baseline`, `pose_verified_in_pause`, and `unpaused_after_verification`. If `paused:false` is requested, pose is first verified paused, then resumption is applied once and discrete settings reread; no immobility after resumption is promised.

Since 0.9.1, `selected_game_speed` locally tracks a positive value explicitly commanded to the probe, not an SDK getter. It is `null` at startup and after loading. Establish it with `set_game_speed(speed=1, preserve_pause=True)` before `run_until` or `run_scenario`; this preserves pause. The runner rejects unknown initial selection before any mutation. Selected speed before this setting remains unknown and is not presented as restorable; manual UI changes during the test are unsupported.

An unavailable API remains advertised in the protocol with `not_implemented` and a documented TODO; no address or function is invented. Parameters are typed data, not shell commands or executable code.

<a id="origines-sauvegardées-et-identités"></a>

## Saved origins and identities

| Native command and MCP tool | Parameters | Result |
| --- | --- | --- |
| `resolve_saved_handles` | `ids`,1 to 128 complete character or squad handles | Paused SDK resolution. `{resolutions:[{saved_id,current_id,loaded,resolved}]}`; `resolved` means non-null SDK return, `loaded` means membership in the inventory. `current_id` is supplied only in the latter case. |
| `begin_saved_origins` | `save_name`, `source_fingerprint:"sha256:…"`, integer `count` from 0 to 100 000 | Begins a pending registry for the explicitly loaded name in the current epoch; returns a `token`. Internal `current_save` does not prove the loaded directory. |
| `add_saved_origins` | `token`,1 to 128 `ids` | Entire batch validated before addition, without duplicates or count overflow. No partial registry published. |
| `commit_saved_origins` | `token` | Requires complete count, resolves bindings on a candidate, rejects ambiguities, then publishes atomically. |

Since 0.9.3, `ping` advertises `saved_origins_required:true`, `saved_origins_prepared`, `saved_origins` metadata, and `save_root` obtained through `SaveManager::getSavePath()`. MCP `load_save(wait=True)` reads complete identities from `quick.save` and only its indexed platoon files **before** loading. Its owned reader follows public type15 FCS, bounds sizes/counts, rejects unexpected paths, links, and ambiguities, then verifies the same hashes after world readiness. Other formats fail explicitly. A configured `save_root` option must match the SDK root; `null` or omission leaves that root authoritative. A relative SDK root resolves inside the game's working directory.

The server then automatically registers the manifest through the three commands above, in 128-entry batches. Reading, loading, and registration share `load_timeout`. Low-level tools are available to other clients, but manual invocation does not replace the automatic workflow's file checks. `wait=False` provides only native acceptance: perform the full load before a dump/scenario. Watchdog autoload alone does not prepare this registry.

Name, fingerprint, counts, and token are protocol metadata, never shared-state fields. The registry is revoked on the next load, reset, world change, or unavailable transition. Without a prepared registry, `dump_state` returns `origin_context_required`. An old token cannot continue preparation in another epoch or instance.

An origin's five uint32 components reconstruct the public `hand`; `getCharacter()` or `getPlatoon()` must identify an object in the loaded inventory. Full current equality may also retain a dead object whose resolver is no longer available. Bindings are bijective and retained only while the complete current HAND remains loaded. A collision fails with `origin_identity_ambiguous`. No name, rank, position, definition, or index/serial pair serves as identity.

The probe replaces proven current handles with saved identities in IDs, squad membership, task subject, members, and leader, then resorts lists. Conversion precedes native writing; MCP does not normalize identities afterward. Without verified origin, the current HAND is retained without automatically concluding generation. Separate control metadata `camera_follow_id` also uses the canonical cache after commit; orders and follow resolve those entries to loaded actors before mutation. Shared schema remains 0.1, independent of C++.

`identity_source` accompanies the file result: `save_name`, `source_fingerprint`, `count`, `matched_count`, `remapped_characters`, `remapped_squads`. MCP checks and retains it in reports. Scenario repetitions must preserve the same source fingerprint. See [coverage](state-coverage.md) and [delivery](oracle-phase1-delivery.md).

<a id="état-commun-et-octets-canoniques"></a>

## Shared state and canonical bytes

[state.schema.json](../schema/state.schema.json), version `0.1`, defines `clock`, `characters`, `squads`, `factions`, and `relations`. All fields are present; explicitly unknown fields permit `null`. A known empty collection is `[]`, not an unknown value. [Field-by-field coverage](state-coverage.md) details accesses and the meaning of each value.

`elapsed_seconds` represents **world calendar seconds**: `getTotalHours() * 3600`. One simulated second is 33 calendar seconds per MeitouClient's constant; see [time units](#time-units). `day` is zero-based, `hour` is hour within the day, and `speed` the effective multiplier, zero while paused. No wall time, frame counter, PID, or address appears in this state. Characters come from the union of update list, retained dead characters, and active-squad members; factions come from the live manager. An unloaded zone is not captured.

Character/squad identities are opaque `hand:TYPE:C:CS:I:S` strings, of saved origin when the binding above is proven. Races/factions use their `GameData.stringID`; medical parts append side to this identity. Lists sort lexically by `id`, squad members by identity, and relations by `(source_id,target_id)`. Relations are directional. Task is the immediate current action identified by its lowercase public name; a target may be absent from the snapshot. Position is exposed only for `move_cus_ordered`, `move_on_free_will`, and `move_on_free_will_fast` when valid; other tasks have `position:null`.

Objects have sorted keys. For a finite binary64 number with absolute value at most1e9, calculate `floor(abs(x)*1e6+0.5)`, then reapply sign; half units therefore round away from zero. Negative zero becomes zero. Decimal output without exponent, at most six fractional digits, no unnecessary trailing zeros; UTF-8 without BOM, JSON control escaping, no presentation whitespace, one LF terminator. This choice is reproduced in C++ v100 and Python and remains reproducible in C#. No locale-dependent rounding.

State-file size is bounded to 64 MiB. Python validation rejects duplicate keys, non-finite numbers, invalid Unicode, unexpected properties, and duplicate identities. MCP checks the returned path under `oracle_output`, validates schema, then writes canonical bytes. Byte identity for the same state does not promise engine determinism.

<a id="outils-mcp-et-délais"></a>

## MCP tools and timeouts

Official `mcp`/FastMCP SDK, Python 3.11+, stdio. `timeout` bounds one TCP exchange, default **10 seconds**. `load_timeout` and `run_until_timeout` bound their complete operations, default **120 seconds**; `scenario_timeout` bounds a scenario campaign, default **1800 seconds**. A long wait consists of small bounded calls and does not prevent watchdog heartbeat.

MCP `dump_state()` accepts no arbitrary path: it chooses a unique name, requests native capture, validates, then publishes under `runs/dumps/`. Its result adds `source_path`, `sha256`, `clock`, and collection counts to the final path. `load_save(name, lock_edge=False, wait=True)` waits by default for a ready paused world; `wait=False` returns acceptance only. `run_until(target_seconds, timeout_seconds=120)` waits for terminal state; status/cancellation tools remain independently accessible.

`game_status`, `restart_game`, and `read_log` retain behavior. The watchdog restarts only its own launched process; restart acknowledgment does not prove a save loaded. A different `instance_id` during a scenario invalidates that execution instead of silently continuing. Tool `restore_scenario(save=None)` recovers a scene from the interruption journal; it does not resume an interrupted execution. Without parameters, it reloads the journal's save. If captured controls belong to another **known** save, specify, for example, `restore_scenario(save="copie-originale-connue")`. No save is guessed: name is validated, controls remain strictly verified, and `restore_required` stays true until success. The used save is returned and recorded in `recovery_save`.

<a id="supervision-et-commandes-de-redémarrage"></a>

## Supervision and restart commands

The watchdog monitors only the process it launched. Exit or frozen heartbeat beyond `heartbeat_timeout` triggers stopping if needed, an archive attempt, and restart, with documented startup/loading grace periods. Copies of recent `.dmp` files are optional; absence is not a protocol failure.

Archiving is best effort: creation/read/copy errors do not block restart. `game_status` exposes `archive_path` and `archive_errors` from the last attempt; successful copies remain retained. Publication/diagnostic failure does not stop supervision.

The MCP request uses a restart token. Reading `restart.request` is bounded to 129 bytes for a1-to 128-character printable ASCII token. Read/consumption errors are exposed in `restart_request_error` and `restart_request_failures` without preventing recovery of a dead/frozen process. After requested restart, acknowledgment remains published even if request removal fails; the same persistent token does not trigger a restart loop. The watchdog preserves a different token observed during consumption.

<a id="time-units"></a>

## Time units: calendar seconds and simulated seconds

Scenario `at` values, checkpoint `requested_at`/`actual_at`/`overshoot_seconds`, `run_until` `target_seconds` and state `clock.elapsed_seconds` all use the same unit on **both targets**: **game calendar seconds**, that is in-game hours × 3600. The "2 min" and "10 min" checkpoints of the examples are two and ten minutes of the in-game calendar, not two and ten minutes of simulated or real time.

| Statement | Status and source |
| --- | --- |
| Original target: `elapsed_seconds = getTotalHours() * 3600`. | **Verified** in [`plugin/OracleState.h`](../plugin/OracleState.h) (`gameSeconds`, line 54). |
| MeitouClient adapter: `elapsed_seconds = session.Clock.TotalHours * 3600`. | **Verified** in `src/Meitou.Game/GameHost.Oracle.cs` (`OracleSeconds`), a file added by this repository's [adapter patch](../integrations/meitou/0002-opt-in-oracle-adapter.patch), not by upstream MeitouClient. |
| MeitouClient defines 1 in-game hour = `1200/11` ≈ **109.09 simulated seconds**, and advances its game clock by `Simulation.TickSeconds` simulated seconds per tick. | **Verified** in code (at upstream `100c6cae`): MeitouClient `src/Meitou.Engine/Time/GameClock.cs:13` and `src/Meitou.Simulation/World.cs:202` (`SecondsPerGameHour = 1200.0 / 11`), `src/Meitou.Simulation/World.cs:51` (`TickSeconds = 1f / 30`), `src/Meitou.Engine/WorldSession.cs:222` (`SimulationTick`, `Clock.Advance(Simulation.TickSeconds)`). |
| Hence **1 simulated second = 33 calendar seconds** (3600 / (1200/11) = 33): 120 calendar s ≈ 3.6 simulated s, 600 calendar s ≈ 18.2 simulated s, 3600 calendar s ≈ 109.1 simulated s. | Arithmetic from the constant above. On MeitouClient the ratio does not depend on game speed (**Verified**: `GameClock.cs:6-8` at upstream `100c6cae`, speed only changes how many ticks run). On the original, the engine reports the same hour length (**Verified**, next row) and the calendar advances about 33.00 calendar seconds per real second at x1 (**Observed**); no engine time accumulator is read, so simulated time itself is not measured there. |
| Original target: same hour length. | **Verified** engine value: `getLengthOfHourInRealSeconds()` returns 109.0909 (the single-precision value of 1200/11) in every recorded probe sample. **Observed** rate: at x1 the calendar advanced about 32.94 to 33.00 calendar seconds per real second (about 33.00 over intervals of 30 s or more); see also the [clock measurements](research/simulation-clock-measurements.md). That real seconds at x1 equal simulated seconds is argued, not measured: no engine time accumulator is read. |
| Measured simulated seconds per in-game hour. | MeitouClient: **Verified** in code (previous rows); checkpoint stops on whole ticks of 1.1 calendar seconds are **Observed** and consistent with it, one tick being 1/30 simulated second (for example 120 → 121.0, 300 → 300.3, 600 → 600.6). Original: see the previous row; a direct simulated-time counter remains **Unknown**. |

Reports remain expressed in calendar seconds; a simulated-time column is a conversion of these values, not a separate measurement.

<a id="scénarios-et-rapports"></a>

## Scenarios and reports

[scenario.schema.json](../schema/scenario.schema.json) requires `{schema_version,name,save,speed,repeat,actions,checkpoints}`. `at` is **calendar seconds relative to the first paused state after reload**, not real duration or an absolute deadline. One simulated second is 33 calendar seconds (**Verified** in MeitouClient's code; on the original the same hour length is read from the engine); see [time units](#time-units). `repeat` is 1 to 100; tool `run_scenario(path, repeat=None)` may override it. Only `pause`, `set_game_speed`, `issue_order` actions are allowed, with validated parameters.

Each repetition reloads the save and checks paused readiness. Instants are processed in order; at equal times, actions preserve declared order and precede every checkpoint. Execution remains physically paused during this group; a resume order becomes effective when advancing toward the next instant. Persistent pause without same-instant resume makes a later deadline unreachable and is rejected. Checkpoints record `requested_at`, `actual_at`, and `overshoot_seconds`: the first observed crossing may exceed target, particularly at high speed.

Before `run_scenario`, explicitly load the save named by its `save` field, wait for pause, then establish known selected speed. Paused start is required before any scenario mutation. Initial controls must belong to that save: the runner finishes on it and does not automatically restore a different previous save. A camera from another region may be constrained by the reloaded world; restoration comparison then fails and retains the recovery journal.

The current Python runner calls `wait_stable_controls` before arming the recovery journal. It observes at least three scene reads on distinct frames spanning at least **0,5 real second** measured by a monotonic clock, within a wait bounded to **10 seconds**. Every scene is bracketed by two `ping` calls checking the same instance and a ready world. Pause, game clock, and controls must remain stable through this window; unavailability or pose discrepancy resets it. The last pose in the window becomes the recorded reference. It stays fixed after journal arming: no later observed pose replaces it to make restoration pass. Initial reads appear in `report.json.control_capture_observations`. Missing initial pause or unknown selected speed causes rejection before arming/mutation.

Snapshots are stored under `runs/<name>/<horodatage-unique>/<exécution>/<checkpoint>.json`, with validated scenario, action results, and `report.json`/`report.md` reports. Fields compare by entity identity with explicit presence/absence. The report separates stable paths from variable observations; a single execution cannot assess repeatability. This report concerns Kenshi repetitions, not comparison with MeitouClient.

An OS lock `runtime/oracle-scenario.lock` excludes concurrent runners using this runtime. Journal `runtime/oracle-restoration.json` is written before mutation. At the end, including after errors, the runner attempts cancellation and reloads the starting save. It prepares captured controls only once, observes a stable locked baseline with the exact token, then validates requested mode, orientation, zoom, follow, and selection before one commit. This first window is bounded to 10 seconds, at least three distinct frames over 0,5 real second. After commit and scrolling release, a second window with the same bounds checks the fixed reference. Only reads repeat; no restoration mutation is replayed.

Tolerances remain **0,05** for center, camera position, and zoom, **0,0001** for quaternion with `q`/`-q` equivalence, and **0,000001** for selected speed. Camera mode, pause, scrolling, and followed target must match; temporary protection must be released. Checked numeric values must be finite and selection known. Every accepted pose is compared with the recorded reference and its window's first pose, with unchanged game clock. A stable but incorrect pose fails at deadline. `restoration.observations` retains reads and discrepancies; `restoration.verified` becomes true only after the complete window. The runner does not reconstruct an initially unsaved game. If restoration fails, the report remains failed, `restore_required` stays true, and a new test is rejected until recovery.

`restore_scenario` uses the same procedure on journal controls without changing their reference. Preparation reads are retained in `baseline_observations`, post-commit reads in `observations`, and any error in `recovery_attempt`. The journal becomes `restore_required:false` only after success. Scrolling stays disabled during preparation, then is checked after release. User input is not neutralized, and no later immobility is guaranteed. Historical evidence retains its versions and initial scope.

Examples under `scenarios/` contain names/identifiers to adapt to local saves. No game file is included. Fake game `tests/fake_probe.py` covers oracle protocol, clock, and synthetic captures; `tests/fake_plugin.py` retains historical fixtures. Real captures, repetitions, and restoration checks are detailed in the [phase 1 validation report](oracle-phase1-validation.md).

<a id="référence-historique-0820-et-versions-précédentes"></a>

## Historical reference 0.8.20 and earlier versions

The sections below retain earlier telemetry details and guarantees. Tool counts, the `full` default, log prefixes, and historical loading restrictions describe those versions; oracle sections above are authoritative for0.9.5.

**0.8.19** adds optional `detail="aggregates"` mode to the existing `get_frame_stats` getter. Still17 tools, same systems and limits. See the contract below; historical outputs remain readable.

Since **0.8.9**, `KENSHI_PROBE_FUNCTION_TARGET=medicalPeriodicUpdate` selects `MedicalSystem::periodicUpdate`, resolved through its non-virtual SDK entry `_NV_periodicUpdate`. Original and wrapper are typed `MedicalSystem*` without an additional argument; AI*,float is not used. Ping adds `medical_periodic_update_profiling`. Selected function and series retain generic names; ZoneManager/AI/charsUpdateUT/physics flags inactive for this target. Still one selected hook, at most three system probes,17 tools. This probe measures the resolved implementation, not every medical operation or every possible derived variant.

Since **0.8.8**, KENSHI_PROBE_FUNCTION_TARGET also accepts `zoneRendertimeThread`, resolved through `GetRealAddress(&ZoneManager::updateRendertimeThread)`. Wrapper and original have the exact SDK prototype `ZoneManager*, const Ogre::Vector3&`. This selection replaces the single profiled function without adding a probe: still at most three and 17 tools. Ping exposes `zone_rendertime_thread_profiling` and generic name `ZoneManager::updateRendertimeThread`. AI, charsUpdateUT, and physics aliases remain null/false for this target. Generic series and TLS identity remain available when per-call CPU reads are disabled. Check installation flags before assuming a measurement is available.

Since **0.8.6**, `set_game_speed(speed, preserve_pause=True)` preserves pause state: `setGameSpeed` and `userPause` finish in the same main-thread command before it returns to the game loop. `ping.set_game_speed_preserve_pause_available` advertises this capability. The response adds `preserve_pause` and `paused_before` and retains `paused` and `frame_speed_multiplier`. Default `False` retains existing SDK behavior, which removes pause for positive speed; the server then omits the new wire parameter. Clients requesting preservation must verify capability before mutation.

Since **0.8.7**, `speed=0, preserve_pause=True` is rejected before mutation by both MCP server and native plugin. Zero speed requests pause from the SDK and conflicts with preserving an unpaused state; preservation mode therefore requires `0 < speed <= 5`. Use `pause(paused=True)` to stop simulation. The restoration helper requires this new capability and verifies identical simulated time while setting x1. Raw game_time_stamp continues in pause and is not used for this check.

Since **0.8.5**, nonempty KENSHI_PROBE_FUNCTION_TARGET takes precedence over AI_TARGET and selects periodicUpdate/update4Frame/charsUpdateUT; nonempty FUNCTION_THREAD_CPU takes precedence over AI_THREAD_CPU. Invalid/oversized target: selected probe disabled. Ping exposes function_profiling/profiled_function/function_probe_target_valid/function_target_source and function_thread_*; check the installation flag. systems.profiled_function and function_ms/calls/nested_entries_skipped series carry the actual name; AI aliases are null when charsUpdateUT is selected, and charsUpdateUT fields then carry its measurement. One selected hook with its exact prototype, at most three probes and 17 tools. function_diagnostics.py and analyze_profiled_function.py also validate aliases and old AI data. See chars-update-ut-measurements.md.

Since **0.8.4**, load_save pauses exact name KenshiProbe_test before publishing world_ready=true, as for owned snapshots. Its pause_on_ready response is true for this copy; other saves do not receive this rule. ping.test_save_pause_on_ready_available advertises capability, ping.load_pause_pending the pending wait. No new tool/hook. See autoload-pause-validation.md for real startup/restart without a controller pause command.

Since **0.8.3**, AI-probe identity is independent of CPU mode: creation FILETIME in TLS, one read per thread lifetime, failure retained as unknown/null. ping.ai_thread_identity_mode and systems.ai_profiled_function.thread_identity_mode equal tls_creation_once, ping.ai_thread_identity_independent_of_cpu=true. Per-call CPU disabled: CPU counters null and zero available calls, identity usable for an exact OS join. This cache retains no game handle or pointer. set_camera_free also accepts native omission of lock_edge. See ai-identity-measurements.md for real validation; still three probes and 17 tools.

Since **0.8.2**, load_save(name,lock_edge=false) can preserve scrolling lock **across loading**, only for KenshiProbe_test or an owned snapshot. Original value is retained and response adds camera_edge_locked; false default remains compatible. set_camera_free accepts release_edge=false to explicitly restore the captured preference; simultaneous lock_edge=true and release_edge=true are rejected. These options require booleans and native disposable-save protection; they do not directly modify files. Loading/protection still concern17 tools/three probes. ping.camera_load_edge_lock_available indicates capability. See etw-camera-validation.md for real drift, stability evidence, and autosave metadata distinct from preferences.

Since **0.8.1**, KENSHI_PROBE_AI_TARGET in the watchdog environment selects periodicUpdate (default) or update4Frame at startup, with one AI hook. Unknown/oversized value: AI probe not installed, ai_probe_target_valid=false, no silent choice. Ping adds ai_profiling, ai_profiled_function (selected name), ai_probe_target_valid, and ai_update4_frame_profiling; check installation flag before interpreting the name. get_frame_stats.systems.ai_profiled_function is the generic object with explicit function. systems.ai_periodicUpdate and its series are an identical alias only in periodic mode, null in update4Frame mode; do not sum this alias twice. Generic series ai_function_ms/calls/nested_entries_skipped. Canonical analysis analyze_ai_function.py rejects contradictory aliases/mixed functions/inconsistent initial selection; old entry analyze_ai_periodic.py is retained. Still17 tools/three probes maximum. See ai-target-selection-measurements.md for update4Frame evidence/limitations.

Since **0.8.0**, AI::_NV_periodicUpdate(float) replaces the physics probe. Ping exposes ai_periodic_update_profiling, ai_thread_cpu_enabled, and ai_thread_cpu_startup_read_mean_us; physics_back_thread_profiling=false, physics_thread_cpu_enabled=false. get_frame_stats.systems.ai_periodicUpdate contains the same bounded TID/creation counters as the previous physics probe, plus nested_entries_skipped_total and scope: only completed outer calls are measured, nested entries not timed separately. KENSHI_PROBE_AI_THREAD_CPU=1 enables optional CPU. Object physics_backThreadUpdate and its series are null, charsUpdateUT remains null; still three probes and 17 tools. The per_frame ai_periodicUpdate_ms/calls/nested_entries_skipped fields describe end-of-call buckets, not tasks executed exclusively inside that frame. Quantized CPU and separate OS windows prohibit deriving exclusive coverage by simple division. See ai-periodic-measurements.md.

Since **0.7.9**, three additional optional paused roles are provided: resource_loader (ResourceLoader::getInstance), save_file_system (SaveFileSystem::getSingleton), navmesh_generator (world->navmesh->generator). ThreadClass inheritance and public accesses verified in SDK headers, compiler conversions and getters linked then observed in-game. An object may exist without usable identity (SaveFileSystem threadID=0 observed): available=true/identity_verified=false implies no presumed CPU. The three initial roles remain mandatory for analysis; older recordings compatible. At most seven roles in this version, still 17 tools and three probes. Analysis adds known_sdk_thread_cpu for the sum of verified unique identities only, never exclusive function cost.

Since **0.7.8**, optional fourth row `world_physics_interface` describes `world->physics` itself, without a new hook. Analysis still requires the three previous roles; this additional role may be absent in older recordings. It is observed as an alias of physics_backthread in tested scenes. Presence at one boundary alone cannot join CPU; deduplicate any shared identity. The DLL now also accepts native thread_details omission as false (fixing missing field under 0.7.7). Omission, false, and rejection of a mistyped string verified in-game.

Since 0.7.7, `get_scene_state(thread_details=false)` accepts an optional boolean. When true, it requires pause, a ready world, and no pending save/load, then adds `sdk_threads`: process_id, frame, observed_qpc_ms, and three roles rows (`world_ai_non_render`, `world_navmesh`, `physics_backthread`). Accesses are GameWorld::AINonRenderThread(), GameWorld::navmesh, and PhysicsInterface::getBackthread(), inheriting ThreadClass in SDK headers. By default, no additional role read occurs; tool count stays17 and all three system probes are unchanged.

Each role has available and identity_verified; if the object exists, sdk_thread_id is copied. A duplicated handle is queried with limited rights: kernel_thread_id, kernel_process_id, and created_filetime (exact decimal string) are validated only if SDK/kernel/PID agree. Handle errors and missing objects stay explicit and provide no presumed valid identity. The borrowed handle is never closed; its duplicate is released on return; no pointer or handle is serialized. Field name is not read, and no work state changes. identity_verified does not prove current execution or exclusive function. Several roles may share a thread: do not sum their CPU without deduplicating TID and creation time. See sdk-thread-roles-measurements.md.

Since 0.7.6, all three system probes are **GameWorld::charsUpdate, NavMesh::findPath, and PhysicsActual::_NV_backThreadUpdate(float,bool)**. The charsUpdateUT probe is no longer installed; historical fields `charsUpdateUT_mean_ms` and `per_frame.charsUpdateUT_ms` are **null**, not zero. GameWorld/Renderer service callbacks remain separate from these three systems. The server retains17 tools.

`ping` adds charsUpdate_profiling, charsUpdateUT_profiling=false, physics_back_thread_profiling, physics_thread_cpu_enabled, and system_hook_count (successfully installed system probes, at most three). Physics fields are null when the hook is unavailable; an object with zero counters instead means an available probe without a completed call in this window.

`systems.physics_backThreadUpdate` contains calls_total, mean_ms (inclusive-duration sum divided by frames, not calls), max_call_ms, and cpu_enabled. Environment variable **KENSHI_PROBE_PHYSICS_THREAD_CPU=1** enables two GetThreadTimes reads per call at startup; disabled by default. cpu_available_calls and cpu_unavailable_calls partition all calls. cpu_user_total_ms/cpu_kernel_total_ms sum only readable calls, or are null if mode disabled. Unavailable includes a disabled probe; do not automatically interpret it as an API error. Values are quantized, zero does not prove absence of work, and CPU deltas above wall time are not artificially capped.

The threads table retains at most **eight identities (thread_id, created_filetime)**; FILETIME is an exact decimal string, or null if the creation read is unavailable. A reused TID does not merge different creation times. Every row has the total's same counters/durations. `unlisted` accumulates calls without table space; `threads_truncated` is true if its call count is nonzero. The aggregate remains complete even when some identities are no longer detailed. Call/time/CPU partitions and maxima reconcile with threads + unlisted. CPU sum is partial when reads are missing. Creation time may remain known if the final CPU read fails.

Calls are assigned to their end bucket under the same lock as frame publication; a call may start before the returned window. `per_frame` adds physics_backThreadUpdate_ms and physics_backThreadUpdate_calls over at most the last hundred frames. Values/identities are copied; no PhysicsActual pointer persists between reads. Original body receives exactly the same arguments; it is not replaced. The non-virtual signature is public in PhysicsActual.h and its v100 linkage verified. CPU reads add work around wall duration; comparing instrumented versions does not demonstrate engine gain.

Since 0.7.5, `save_scene_snapshot(name)` requests a **new** save of a paused test battle, only under prefix `KenshiProbe_test_scene_` and a safe1..40-character ASCII suffix. Any existing target is rejected. Server now exposes17 tools. `accepted` does not confirm writing finished; `ping.save_signal`, file presence, and stabilization must be checked. `load_save` returns `battle_tracking_restored` and `pause_on_ready`: for snapshots created in the same plugin session, name tracking is recovered and pause applied before loading=false. Plugin restart loses this in-memory association. `set_camera_free` also accepts `lock_edge` to request temporary scrolling protection on the copy or managed snapshot. See scene-snapshot-measurements.md for guarantees and observed discrepancies.

Since 0.7.2, every `battle` member exposes `health` and `attack_target`. `health.parts_flesh_stun_max` contains at most eight raw SDK triplets `[flesh, fleshStun, _maxHealth]`, with actual part count, sampled count, sums, and `complete` indicator. Non-finite value or null pointer invalidates completeness. Sums cover sampled parts only; do not extrapolate when `complete=false`. Indices are not persistent anatomical identities. `attack_target` contains resolved target and its name/faction/position, cohort membership, numeric `swordStateEnum`, and a copied handle `[type, container, containerSerial, index, serial]`. Since 0.7.3, a null handle is rendered `null` without copying irrelevant numeric fields. No target handle or pointer persists between reads.

Since 0.7.3, template selection rejects multiple possible factions unless `faction_name` disambiguates them. `opponent_template_id` and `opponent_faction_name` permit a pair of distinct templates, but both factions must be **already hostile in both directions**, checked with `FactionRelations::isEnemy` before creation. Both numeric relations are retained in the response. No relation-modification call occurs. With `details=true`, `list_characters.faction_relations` lists enemies among at most sixteen factions in the actually returned characters, sorted by name; it is not a world-wide faction inventory. `truncated` indicates the limit.

Since 0.7.1, `get_scene_state` also exposes `edge_scrolling`, `scene_camera_control_owned`, raw SDK fields `input.mPos/mPosAbs` and camera directions, plus `battle`. These input coordinates are read unchanged, without inferring physical pointer position outside the window. `prepare_town_scene` and `prepare_battle_scene` temporarily disable Edge scrolling in memory; the next accepted `load_save` restores the captured value and clears battle tracking. No settings file is written. Other user input may still move the camera: the stability guard remains necessary.

`prepare_battle_scene` uses `RootObjectFactory::createRandomCharacter`, then `separateIntoMyOwnSquad(true)`, `clearAllAIGoals`, and mutual `UNPROVOKED_FOCUSED_MELEE_ATTACK` objectives. No faction relation changes. The three-second preparation budget is checked **between** creations; a single call may exceed it. Partial preparation requires reload, without automatic retry. Engine generation is unseeded: identical parameters/save do not guarantee identical stats/equipment. `prepared=true` confirms creation/objectives, not actual landed hits.

Comparable scene preparation on both engines uses the separate `setup_*` commands of the [scene setup contract](scene-setup.md); `prepare_battle_scene` is unchanged.

`battle` identifies actors by a unique name prefix without retaining pointers between frames; it exposes members still present in the update list, combat/received-attack/dead/unconscious states, and SDK blood. An actor absent from this list is not presumed dead. Counts are instantaneous observations, not an exhaustive event journal.

TCP IPv4, 127.0.0.1 only. Port47800, configurable with KENSHI_PROBE_PORT in the game-process environment; also set `port` in config.json. Compact UTF-8 JSON, one LF-terminated line per message.65536-byte limit including LF. Maximum JSON depth16, duplicate keys and non-finite numbers rejected. No authentication: any local process may call the plugin.

The list_characters row limit (500, or 100 with details) is independent of response size. Native networking replaces any response above65536 bytes with `response too large; reduce n or limit`. Truncated inventory does not become exhaustive because its response fits the budget; compare received count with total_update_list. The412-row urban case passes natively, without a guarantee for all strings/populations. See heavy-inventory-measurements.md.

```json
{"id":"request-1","command":"ping","params":{}}
{"id":"request-1","result":{"plugin_version":"0.1.0","game_version":"1.0.65 Steam","frame":124,"timestamp_ms":123456}}
```

Every request requires `id` (1-to 64-byte string), `command` (string), `params` (object). Response: `id` and exactly one of `result` or `error`. An error contains `code` and `message`; if the identifier is unreadable, `id` is null. Current plugin errors use generic `invalid_request`, including unknown command, unsupported function, and saturation. The client never automatically retries a mutation.

| Command | Parameters | Result |
| --- | --- | --- |
| ping | {} | Plugin/game versions, frame, timestamp_ms. From 0.11.0 also `capabilities` (`["scene_setup"]`), `world_readiness`, `world_mutated`, `build_commit` and `state_schema_version` ([scene setup](scene-setup.md#changes-to-existing-commands)) |
| heartbeat | {} | Last frame and timestamp_ms published by the hook, accessible in the menu |
| get_frame_stats | Integer n1..3600 | count, mean_ms, median_ms, p95_ms, p99_ms, max_ms, systems, per_frame |
| pause | Boolean paused | Observed paused |
| set_game_speed | Number speed 0..5; optional boolean preserve_pause (default false), requires speed >0 if true | requested_speed, paused_before, preserve_pause, paused, frame_speed_multiplier |
| list_characters | Integer limit 1..500, optional boolean details | characters:name,faction,position[x,y,z]; total_update_list. With details=true, limit 100, adds template_id, template_type, character_template, is_player, dead, unconscious, age |
| get_scene_state | {thread_details?: boolean = false} | camera_center, camera_position, free_camera, loaded_character_count, active_town_count, frame, paused, frame_speed_multiplier; optional paused SDK roles |
| list_towns | Integer limit 1..500, name_filter string 0..128 UTF-8 bytes | towns:name,faction,position; total_town_count, active_town_count |
| focus_town | name string 1..128 UTF-8 bytes, exact unique name | before, after, town, target_position; requires pause |
| set_camera_free | Boolean enabled, optional boolean lock_edge | before, free_camera, scene_camera_control_owned; requires pause. lock_edge=true restricted to the copy or a managed snapshot |
| save_scene_snapshot | name string KenshiProbe_test_scene_ +1..40 safe ASCII characters | accepted, name, save_root, battle_before; requires battle on paused copy, rejects every existing target. End of writing must be checked separately. From 0.11.0, refused with `not_allowed` / `the world was changed by scene setup; reload it before saving` while `world_mutated` is true, checked before the `world not ready` refusal. See [scene setup](scene-setup.md#changes-to-existing-commands) |
| prepare_battle_scene | template_id string 1..128 bytes, integer pairs 1..20; optional faction_name, opponent_template_id, opponent_faction_name strings≤128 bytes | On loaded paused KenshiProbe_test, creates2×pairs NPCs near the first player. Already loaded non-player CHARACTER templates; ambiguous faction rejected. Distinct opponent accepted only with already mutually hostile factions. prepared, prefix, faction, mutual_enemies_verified, relations if opponent, requested_entities, spawned_entities, setup_ms, members with templates/factions/ages. Reload after every test, including partial |
| setup_info | {} | gate, current_save, probe_loaded_save, world_mutated, autosave_enabled, autosave_configured, player_save_requests_blocked, squad_size; needs a ready world only. See [scene setup](scene-setup.md#setup_info) |
| setup_area_census | center [x,y,z], number radius 0.1..20000, integer limit 1..100 | characters sorted by distance_xz then id, count, truncated, alive/dead/unconscious/player counts, gate, world. Read-only, paused or running, after a probe `load_save` with allow_setup=true |
| setup_spawn_squad | template_id and faction_id strings 1..128 bytes, position [x,y,z], integer max_count 1..16, optional boolean permanent | returned_squad_id, returned_members, new_loaded_count, new_loaded_truncated, rng_key and the common mutation keys. Refuses the player faction and a position more than 2000 units (X/Z) from every living player character |
| setup_set_relation | source_id and target_id strings 1..128 bytes, number value -100..100 | One direction; source_to_target and target_to_source before/after, changes (at most 100), changed_cells, changes_truncated, faction_count. Never writes the war flag |
| setup_heal | character_id string 1..200 bytes | before and after: parts (id, flesh, stun, max), blood, dead, unconscious. Refuses a dead or unloaded character |
| prepare_town_scene | name string 1..128 UTF-8 bytes, exact unique name | town, target_position, players(before/destination/after), scene before/after |
| load_save | name string,1..128 UTF-8 bytes, simple name; from 0.11.0 optional boolean allow_setup (default false) | accepted and name after scheduling, allow_setup echoed; error if absent or operation pending |

Scene commands require a ready world and execute on the GameWorld thread. Town filter is a case-sensitive substring. focus_town rejects ambiguous names. This command stops camera following, enables free mode, and calls teleport at the town's actual position; it moves no character. To restore the view, restore initial free mode with set_camera_free **before** reloading KenshiProbe_test: loading does not restore this boolean, and changing it after load changes the view. tests/live_restore.py applies the in-game-verified order and leaves the copy paused. Immediately returned position may precede subsequent-frame adjustments: reread get_scene_state. loaded_character_count counts the update list without guaranteeing completeness of loaded entities; town inventory does not prove residents loaded.

prepare_town_scene is restricted to testing: the probe's last accepted load must have requested KenshiProbe_test, loading must be complete, and the world paused. This safeguard does not detect a later UI load; do not combine this command with manual loading. It requires1..32 player characters grouped within 1000 units of the first, validates every pointer/position before mutation, then uses getMovement, halt, and _setPositionDirectionAndTeleport. Group x/z offsets are preserved, altitude comes from town definition, orientation fixed to identity for this scenario. Camera returns to normal mode and points toward town. This guarantees neither walkable ground nor loaded residents; observe positions after several frames before measurement. Engine failure can be partial: restore by reloading the copy. This command saves no scenario.

Series `per_frame` contains at most the last 100 frames; `series_truncated` indicates this. Aggregates cover the last N available frames in a3600-entry buffer. At startup without an interval, count=0 and mean_ms=null. Median: mean of the two central values. p95/p99: upper rank, index ceil(p*N)-1. Durations are real milliseconds, including pauses/render waits. The first interval is not recorded.

Since 0.4.0, first_frame and last_frame identify the whole window; every per_frame entry also carries frame. The number corresponds to the completed interval, recorded on the next GameWorld-hook entry. The collector verifies frame-count consistency and rejects window overlaps when these identifiers are available.

`systems` provides charsUpdate_mean_ms and charsUpdateUT_mean_ms. Each per_frame entry provides frame_ms, charsUpdate_ms, charsUpdateUT_ms. Hooks are inclusive; do not add their durations to estimate total cost. A call crossing a frame boundary is assigned to its end frame. If both hooks are not installed, system measurements are null.

The third and last system hook is NavMesh::findPath. systems adds navmesh_findPath_mean_ms (duration sum divided by frame count), navmesh_findPath_calls_total, and navmesh_findPath_max_call_ms (longest call completed in the window). per_frame adds navmesh_findPath_ms and navmesh_findPath_calls. ping.navmesh_profiling indicates hook installation; fields are null if missing. Zero calls with an active hook means no observed call, not proof all navigation is free. Wall durations include waits and may overlap across threads; they do not measure exclusive CPU.

Since 0.6.1, systems.navmesh_findPath_threads partitions totals into game_thread, other_threads, and unclassified, each with calls_total, mean_ms, and max_call_ms. Classification compares GetCurrentThreadId with GameWorld identity captured at call start; unclassified means that identity was not yet known. other_threads does not identify the thread's exact role.

get_frame_stats adds navmesh_slow_calls for calls lasting at least navmesh_slow_calls_threshold_ms=10 ms. Fixed global buffer of navmesh_slow_calls_capacity=32 entries, without allocation on the hook path. Every entry exposes start_frame/completion_frame, thread_id/game_thread_id_at_start/thread_kind, started_qpc_ms/elapsed_ms, start_key/goal_key/radius/water/hierarchical, and result. Only calls with completion_frame inside the returned window are selected; calls may have started before it. Keys are opaque SDK arguments, not character identities. Non-finite floats become null in these diagnostics.

navmesh_slow_calls_total counts all above-threshold calls in the window's buckets; navmesh_slow_calls_retention_truncated indicates whether the buffer fails to retain all of them. An empty list therefore does not exclude a slow call when this flag is true. Transfer of the previous bucket and publication of the next frame now use the same lock, so concurrent calls receive the identifier of the bucket counting them. completion_frame is accounting time under lock; elapsed_ms excludes diagnostic-added locks. Diagnostics still add hook work: do not interpret cross-version comparison as engine gain. The collector verifies counter/duration/maximum partitions, identities, and retained-call consistency.

Since 0.6.2, every retained slow call adds start_vector and goal_vector, four floats copied before the call from hkVector4f::m_quad, declared public in Havok.h. First three components retained without transformation; fourth not interpreted as a spatial coordinate. Non-finite components become null. No Havok constructor or new engine function is called for this copy.

Environment variable KENSHI_PROBE_NAV_THREAD_CPU=1 enables two GetThreadTimes reads per findPath call at startup. This CPU probe is inactive by default. Ping exposes nav_thread_cpu_enabled and nav_thread_cpu_startup_read_mean_us: mean of 200 reads on the startup thread, a local-cost indicator without guarantee for the navigation thread. Slow entries add thread_cpu_user_ms and thread_cpu_kernel_ms, both null if disabled/unavailable; otherwise nonnegative deltas of the calling thread. The CPU bracket encompasses slightly more work than elapsed_ms, and reads have their own overhead. FILETIME units are 100 ns, which does not guarantee effective100 ns resolution; retain quantized values without artificially capping them at wall time. API and units: [Microsoft GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes).

Since 0.6.3, systems.navmesh_findPath_results partitions **all calls completed in the window** into true and false: calls_total, mean_ms (sum divided by frames), max_call_ms, hierarchical_calls_total. This partition reconciles with totals independently of slow-call retention threshold. A false return still exposes no reason code. Slow entries add output_size_before/output_size_after, copied from public member hkArrayBase::m_size; empty, unchanged, or partial size does not prove failure cause.

get_scene_state adds game_total_hours through GameWorld::getTimeStamp_inGameHours().getTotalHours(), game_time_stamp through getTimeStamp(), game_hour_real_seconds through getLengthOfHourInRealSeconds(), and observed_qpc_ms. Non-finite values become null. **Raw timer game_time_stamp continues advancing in pause on the observed installation**: it is not used to measure simulation. In contrast, game_total_hours was observed stationary in pause while QPC advanced. Methods are declared in GameWorld.h and util/TimeOfDay.h and linked through the official SDK library.

The counter advances in the hook, and its QPC timestamp is published alongside it under lock. `heartbeat` is served by networking from this telemetry copy without game-state access. Before the first hook, frame and timestamp_ms are zero. `ping` executes on the main thread and adds paused and frame_speed_multiplier (getFrameSpeedMultiplier); set_game_speed also returns both after mutation. QPC has a system-specific origin; the watchdog adds received_at in Unix time. Mutations and character reads require a ready world. The list covers GameWorld's update list; completeness among all loaded characters remains to be observed.

Renderer::_NV_update adds service_frame, service_timestamp_ms, service_thread, and game_thread to heartbeat. It provides menu progression and serves only ping, load_save and get_rekenshi_settings; other commands remain handled by GameWorld hook. From 0.11.0, while the world is not ready it answers every setup_* command itself with `world_not_ready` (gate G1); once the world is ready those commands run on the game loop only. See [scene setup](scene-setup.md#shared-command-rules). The watchdog prefers nonzero service_frame, otherwise falls back to frame. A plugin responding with both counters zero is awaiting_gameplay. Ogre FrameListener callbacks, not invoked in the observed game, were removed.

Ping adds current_save through SaveManager::getCurrentGame and world_ready (world initialized, no reset/loading). current_save is internal metadata: it may retain the original save name when its directory is copied. load_save checks existence through SaveManager and schedules load(name); accepted does not mean loading completed. Wait for loading=false, world_ready, and frame progression; do not require internal-name/copied-directory-name equality. The network thread reads/modifies no save file.

loading is published under lock when load_save is accepted, then reset false when the world is ready and SaveManager has no signal. The watchdog then allows loading_timeout (default120 s) before treating lack of progression as a freeze. Grace starts on the first received loading=true and is not renewed with every poll. Process exit is still detected immediately. UI-initiated loads do not yet have this explicit guarantee.

Maximum queue 64 entries, at most8 commands processed per hook. Networking handles one connection at a time, multiple sequential lines possible. Receive/send bounded to 1 s inactivity; command wait bounded to 9 s. MCP client opens one connection per call and bounds complete exchange to 10 s by default. A command still queued at expiry is canceled. An already started command may have taken effect: expiry does not guarantee cancellation. Oversized responses: error requesting smaller n or limit.

<a id="contrôle-du-watchdog"></a>

## Watchdog control

config.json is read by Python; relative paths resolve against its directory. The watchdog atomically writes runtime/state.json: running, pid, updated_at, frame, heartbeat, reason, and restart_ack. A request writes a UUID token into restart.request; the watchdog confirms the same token after restart. restart_game waits up to timeout seconds for confirmation. State older than five seconds is stale, and MCP treats running as unknown.

State writing tolerates temporary Windows locks: up to four attempts,25 ms apart after access denial. If all fail, supervision continues and previous state may become stale; publication failure no longer closes the game. state_publication_failures counts publications exhausting retries and appears on the next successful publication. Identical errors are logged to stderr only once while unchanged. The native test kept a reader refusing replacement open for four seconds: three failed publications, then recovery with the same PID/creation time and advanced frames. Local evidence runtime/state-lock-validation.json.

One watchdog and one simultaneous restart requester are supported. The managed process is the one launched by the watchdog; no pre-existing Kenshi process is searched for or adopted. `working_directory` allows launching the compatibility executable from the game root, separate from the executable's own directory.


<a id="télémétrie-optionnelle-du-service-des-commandes-0811"></a>

## Optional command-service telemetry (0.8.11)

`KENSHI_PROBE_COMMAND_TIMING=1` enables measurement at startup in existing GameWorld/Renderer callbacks, without a new system hook. Disabled by default. `ping` exposes `command_service_timing_available` and `command_service_timing_enabled`. Successful object results add `_probe_service`; errors and network-served `heartbeat` do not add this structure. A result without metadata means measurement absent, never zero cost.

Name `menu_service` denotes the Renderer callback's restricted service path, **not proof that the menu is displayed**: this callback may also serve ping during ready gameplay. Scene/statistics reads use GameWorld; ping may use either. Analyses retain/count this flag without rejecting a render ping during gameplay.

Schema 1: `command`, `menu_service`, `thread_id`, `created_filetime` as exact decimal string or null, `identity_verified`, `frame`, `queued_qpc_ms`, `started_qpc_ms`, `finished_qpc_ms`, `queue_wait_ms`, `service_ms`, `scope`. Identity comes from GetThreadTimes, cached once in TLS independently of CPU probing. Waiting starts under queue lock just before insertion; it excludes network read, parsing, and initial lock acquisition. Service starts after dequeue and TLS creation resolution. Service includes execute, result assignment, and DebugLog; excludes its own metadata insertion, SetEvent, JSON serialization/network sending, Python client, and MCP. QPC is wall time, not exclusive CPU.

Service frame is the current callback's frame. The interval with the same number will be published at the next callback; individual series retain only their final rows. Missing corresponding frame in this series does not mean zero cost. Command time can overlap other instrumented systems, and subtraction gives no exclusive total. Instrumentation itself adds clock reads, fields, and allocations; its own overhead is not isolated by this protocol. The64 KiB response limit remains unchanged, so these fields may reduce admissible statistics-read size.

`command_service.py` validates contract, clocks, and identity; `tools/research/live_command_service.py` retains requests/results and three distinct clocks in two paused scenes. Offline replay requiring fingerprint is `analyze_command_service.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER`. This protocol promises neither transport attribution, exclusive CPU, marginal per-actor cost, nor explanation of another battle's p99.


<a id="écriture-json0812"></a>

## JSON writing0.8.12

The native serializer now writes into one buffer instead of composing streams/strings for every subtree. Key order, escaping, non-finite values as null, classic locale, and numeric precision16 retained; no field or transport bound changed. The owned0.8.11 oracle remains in tests/json_legacy_serializer.h, and compatibility is compared byte for byte. [Measurements and limitations](research/json-serialization-measurements.md): local synthetic gain, no FPS or exclusive engine-CPU guarantee. Metadata _probe_service retains its scope, excluding network serialization.


<a id="ownership-des-réponses0813"></a>

## Response ownership0.8.13

Final payload, execute return, and post-event response are transferred by Value::swap instead of explicit copies. Schema,key order,types,errors,and 0.8.12 serializer retained. Queue,timeouts,cancellations,and shared_ptr unchanged; networking consumes only after successful wait,and service no longer touches the response after signaling. Scope _probe_service still includes logical response assignment,now by ownership exchange;literal scope retained. [Tests,measurements,and limitations](research/json-ownership-measurements.md); no global latency/FPS gain inferred from the microbenchmark.


## charsUpdate split0.8.15

0.8.14 was not retained for cadence validation; see [evidence and A/B](research/chars-split-measurements.md).0.8.15 retains `charsUpdate_mean_ms` and `per_frame.charsUpdate_ms` with historical scope up to Guard acquisition. `systems.charsUpdate_split` adds function/scope,calls_total,call_wall_total_ms/post_call_to_lock_total_ms/legacy_total_ms,per-frame means and maxima,threads/unlisted/threads_truncated/capacity 8,exact TID/TLS-creation identities,and disabled/null CPU. `per_frame` adds charsUpdate_call_wall_ms and charsUpdate_calls. Post includes clock/scheduling:not exclusive CPU or pure contention.

Completed,inclusive,potentially nested calls are admitted into the bucket when the lock is acquired; original spans may cross a boundary. Legacy=call+post for each measurement,but maxima do not add because they may come from different calls. Zero duration does not mean no calls. Values cannot be subtracted from concurrent systems or OS CPU. Chars history is fixed/tagged3600,missing tag=error never zero;Sample remains 696 bytes,chars history 2523600. Ping exposes chars_update_split_profiling,chars_update_bucket_bytes,telemetry_sample_bytes,chars_update_history_bytes.64K limit unchanged:retain getter-reduction plans and actually retained windows.

<a id="original-mainloop-via-le-hook-de-service-0816"></a>

## Original MainLoop through the service hook (0.8.16)

`KENSHI_PROBE_FUNCTION_TARGET=mainLoopGPUSensitive` selects `GameWorld::mainLoop_GPUSensitiveStuff`. Original is called once with the same pointer and float after collection/initial service. No second detour is installed at this address, and Havok is inactive in this mode.

`ping` adds `main_loop_gpu_sensitive_profiling`, `function_hook_reuses_service`, `dedicated_system_hook_count`, `service_hook_count`, and `installed_hook_count`. Here: three profiled boundaries (historical `system_hook_count`), two dedicated system detours and two service detours, therefore four effective installations. Counters distinguish measured scopes from installations.

`systems.profiled_function` reports `hook_source=existing_main_service_hook`, `leading_service_excluded=true`, and exact scope: `Completed outermost original main-loop calls; leading pause protection/command draining excluded. Any service callbacks reached inside the original remain included; inclusive wall, not exclusive CPU.` Initial service excluded; callbacks reached inside remain included. Completed outermost calls, identities, and bucket limits follow the existing generic contract. Optional CPU disabled for the campaign; no implicit GPU measurement. Sample 696 bytes and chars history 2523600 unchanged. [Measurements and replay](research/main-loop-measurements.md).

<a id="original-renderer-via-le-hook-de-service-0817"></a>

## Original Renderer through the service hook (0.8.17)

`KENSHI_PROBE_FUNCTION_TARGET=rendererUpdate` selects `Renderer::update` through supplied non-virtual binding `_NV_update()`. Existing service hook reused; successful installation required for `function_profiling`. MainLoop/Havok inactive in this mode. `renderer_update_profiling=true`, `main_loop_gpu_sensitive_profiling=false`, `function_hook_reuses_service=true`. Two dedicated +two service detours =four effective installations and three profiled boundaries.

`systems.profiled_function` reports `hook_source=existing_renderer_service_hook`, `leading_service_excluded=true`, and exact scope: `Completed outermost original renderer-update calls; leading heartbeat/pause protection/command draining/load-state service excluded. Any callbacks reached inside the original remain included; inclusive wall, not GPU or exclusive CPU.` Original receives the same pointer once; initial heartbeat/pause/commands/loading service excluded,internal callbacks included. Native durations in milliseconds,even for very short entries. This name implies neither complete rendering nor GPU time. Sample/chars history and 64 KiB limit unchanged. [Measurements and limitations](research/renderer-measurements.md).

<a id="consolidation-hors-jeu"></a>

## Offline consolidation

`analyze_performance_cohorts.py` is a local CLI separate from the MCP protocol:no tool added or native 64K limit changed. Its version 1 manifest fixes captures/SHA/version/selection; every specialized analysis is replayed. JSON/Markdown retain independent cohorts,CPU windows,omissions,and TID/creation joins,without causal comparison or exclusive coverage. Missing older splits remain null. [Reproduction and limitations](research/performance-diagnostic.md).

<a id="root-sans-argument-par-export-chargé-0818"></a>

## Argument-free Root through a loaded export (0.8.18)

`KENSHI_PROBE_FUNCTION_TARGET=ogreRenderOneFrame` selects `Ogre::Root::renderOneFrame`, exact export `?renderOneFrame@Root@Ogre@@QEAA_NXZ` from already loaded OgreMain_x64.dll. No GetRealAddress on this export, LoadLibrary, or manual RVA. Original called once,pointer and returned bool preserved. `ogre_render_one_frame_profiling=true`, Renderer/MainLoop/Havok selections false, `function_hook_reuses_service=false`: three dedicated detours +two services =five installations,three profiled systems.

Ping adds `function_binding_source=loaded_module_export`, `function_binding_module_path`, `function_binding_symbol`, `function_binding_address` (exact hex string,classic locale); null for other targets. Root statistics report `hook_source=loaded_ogre_export`, `leading_service_excluded=false`, module/symbol/path/address, and exact scope: `Completed outermost zero-argument Ogre::Root::renderOneFrame calls; inclusive work, waits and nested probe/service callbacks included. Not exclusive CPU or GPU time. Bucket admission on completed-call recording; spans may cross frame boundaries.` CPU disabled for0.8.18 campaign,fields null. Sample 696/chars history 2523600/limit 64K unchanged. [Evidence and limitations](research/root-frame-measurements.md).


<a id="mode-cpu-root-observé-même-0818"></a>

## Observed Root CPU mode, same0.8.18

`KENSHI_PROBE_FUNCTION_THREAD_CPU=1` enables existing GetThreadTimes counters at startup. Current mode enabled after an archived restart,without DLL reinstallation. Earlier CPU-disabled recordings remain separate; Root analyzer accepts explicit boolean `expected_cpu`,false by default. `analyze_root_cpu.py` requires CPU-enabled declaration and complete available coverage. Sums include reads around the original and intermediate measurement code;100ns unit does not mean 100ns precision. No clamping of quantized deltas,no exclusive/GPU attribution,no new MCP API or hook. [Calibration and measurements](research/root-cpu-measurements.md).


<a id="analyse-hors-jeu-du-combat-root-cpu"></a>

## Offline analysis of Root CPU combat

`analyze_root_battle.py` reuses bounded battle analysis and requires40 NPCs,explicit CPU mode,verified Root export/module,identical source fingerprints,complete CPU availability for retained calls,and TID/creation joins. Consolidator adapter `root_battle` retains four windows,actors,and size-reduction attempts. No new MCP tool,native field,or hook. Status completed does not guarantee complete temporal coverage when a tail was shortened. [Measurements](research/root-battle-measurements.md).

<a id="statistiques-compactes0819"></a>

## Compact statistics0.8.19

`get_frame_stats(n=300, detail="full")` accepts integer n1..3600 and detail exactly `full` or `aggregates`. The wrapper omits the field for default/explicit full,preserving previous behavior; native also accepts explicit full. Null,bool,and other detail values are rejected. Ping advertises `frame_stats_aggregates_available=true`.

In `aggregates` mode,the old full response is built,then projected. All aggregates,identities,bounds,and retention flags stay identical for the same input. `per_frame` and `navmesh_slow_calls` become **null**, with `statistics_detail={mode:"aggregates", per_frame_rows_omitted:N, navmesh_slow_rows_omitted:M}`. N/M count rows present in lists before omission,not all calls since startup. `series_truncated` and `navmesh_slow_calls_retention_truncated` retain native-retention meaning,separate from detail omission. Empty buffer produces count 0/mean_msnull,two nulls,and omissions0/0;n0 is not an accepted request.

Validators check this contract before skipping optional validation of absent rows; no detail is fabricated. `statistics_aggregate_budget.collect` makes one request across all N and fails explicitly if it fails,without reducing the range. Historical captures still use their adaptive collector. Projection reduces payload; it does not eliminate prior detail construction or establish CPU/FPS gain. [Native and real validation](research/aggregate-statistics-measurements.md).
