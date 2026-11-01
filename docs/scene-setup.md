# Scene setup contract (probe and adapter 0.11.0, scenario-0.2)

Status: frozen interface. The native probe, the MeitouClient adapter and the
Python runner implement exactly these names, keys, ranges and refusal texts
(engine-internal safety failures excepted, see below). A change here is a
contract change: it needs a new version, not a rename in one implementation.
Implemented in probe 0.11.0 and the MeitouClient series on 88ae71a1; not yet run live. Statements about code are marked
**Verified** (read in source), **Observed** (seen in a run) or **Unknown**.

Scene setup prepares one controlled scene after a reload and before
checkpoint 0: spawn a squad, settle one simulated second, fully heal, then set
faction relations. It never saves. The state schema stays
[0.2](../schema/state-0.2.schema.json); the scenario format with a `setup`
block is `scenario-0.2` (a distinct name, never a bare `"0.2"`). Transport,
error envelope, time units and `issue_order` are those of the
[protocol](protocol.md).

## Shared command rules

- Command names are identical on both engines: `setup_info`,
  `setup_area_census`, `setup_spawn_squad`, `setup_set_relation`,
  `setup_heal`. `setup_teleport_character` is reserved (not in 0.11.0; both
  engines answer it like any unknown command).
- Native service path: while the world is not ready, the menu drain answers
  every `setup_*` command itself with G1, so the client never waits for the
  game loop during a load. Once the world is ready they run on the game loop
  only. The menu path otherwise keeps serving only `ping`, `load_save` and
  `get_rekenshi_settings`. (The private test build needed the same rule;
  **Verified**.)
- Parameters are a closed set per command. Validation order is fixed:
  1. unknown parameter keys;
  2. the gate (below);
  3. parameter values, in the order of each command table;
  4. lookups and semantic refusals, in the order of each refusal table;
  5. the engine call.
- Parameter errors use code `invalid_request` and exactly these texts on both
  engines (the native helper texts): `params must be object`,
  `unknown parameter: <key>`, `missing field: <key>`,
  `invalid number: <key>` (wrong type, non-finite or out of range),
  `invalid string: <key>` (wrong type, empty, too long in UTF-8 bytes, or
  NUL), `invalid boolean: <key>`, `<key> must have three numbers`,
  `invalid position coordinate` (non-finite or above 1e7 in absolute value),
  `<key> must be an integer`.
- Engine-internal safety failures (safety limits, duplicate identities, an
  invalid game clock or position, a faction list that changes or is ambiguous,
  more than 64 player characters, `origin_identity_ambiguous`) use the
  engine's own code and text, normally `state_unavailable`. The runner fails
  the step and never compares these texts.
- Ids are opaque strings, as in `dump_state`: character and squad ids are the
  canonical ids (native: `canonicalId(raw)` after a saved-origin refresh, so
  the saved origin when bound, else the current handle; MeitouClient: its
  state ids, `local:` for spawned characters). Faction and template ids are
  `GameData` string ids; part ids are `<record id>:<side>`.
- Echoed numbers (`center`, `position`, `value`) are the values applied,
  rounded to float32 on both engines; the runner compares them with
  `float32(request)`.
- Positions in replies are finite: a non-finite character position is an
  internal failure, never a silently skipped row.
- Every mutating reply carries `saved:false`, `world_mutated:true`, `gate`,
  `world_before` and `world_after` (each `{elapsed_seconds:number,
  paused:boolean}`).
- A reply may carry one extra key, `engine_detail` (object, free form,
  engine-specific, never compared). No other extra key is allowed.

## Gate

The gate is checked in this order; the first failing row is the refusal. Codes
and texts are identical on both engines.

| # | Applies to | Condition refused | Code | Message |
| --- | --- | --- | --- | --- |
| G1 | all five | world not ready | `world_not_ready` | `world is unavailable or a save is loading` |
| G2 | all but `setup_info` | the current world is not a completed probe `load_save` of the current epoch (see Load lifecycle) | `not_allowed` | `scene setup requires a world loaded by the probe's load_save` |
| G3 | all but `setup_info` | that load did not carry `allow_setup:true` | `not_allowed` | `scene setup was not enabled: load the save with allow_setup:true` |
| M1 | mutations | world not paused, or a `run_until` is active | `invalid_request` | `scene setup mutations require a paused world and no run_until` |
| M2 | mutations | autosave enabled or unreadable | `not_allowed` | `scene setup mutations are refused while autosave is enabled` |
| G4 | all but `setup_info` | no player object, or zero player characters | `state_unavailable` | `player unavailable` |
| G5 | census, spawn, heal | native only: saved origins not prepared for this epoch (MeitouClient always passes) | `origin_context_required` | `scene setup requires prepared saved origins` |

Mutations are `setup_spawn_squad`, `setup_set_relation` and `setup_heal`.
`setup_area_census` is read-only: it works paused or running, under G1-G3,
G4 and G5. `setup_info` needs only G1 and reports the rest.

**Load lifecycle (Q1).**
- A `load_save` refused before acceptance (invalid name, save not found, load
  pending, busy) changes nothing: gate, `allow_setup` and `world_mutated`
  keep their values.
- An accepted `load_save` records the requested save and its `allow_setup`,
  and closes the gate until the load completes.
- The load completes on the first ready frame where the epoch accepts the
  requested save, and natively also `SaveManager::getCurrentGame()` equals it
  (the private build's check, **Observed** equal in every receipt). Only then
  does `allow_setup` take effect and `world_mutated` become false.
- A failed load never completes: the gate stays closed and `world_mutated`
  keeps its value. MeitouClient detects failure (`OracleLoadFailed`). Natively
  a failed load is detected only through the current-save check; whether that
  check catches every failure is **Unknown**.
- Any other load (a UI load, or a `load_save` without `allow_setup:true`)
  clears the opt-in. A UI load does not clear `world_mutated`. There is no
  save-name allowlist in public code; the same rule holds on both engines.

**Epoch.** Native: `savedOriginEpoch.acceptsSaveName(lastRequestedSave)`
([OracleSavedOrigins.h](../plugin/OracleSavedOrigins.h)), which a UI load
revokes even when the world pointer is reused (**Verified**); on its own it
also accepts the requested name after a failed load if a world reads ready
again (**Verified**), hence the current-save term. MeitouClient: the save its
oracle `load_save` finished; oracle mode drops every player save/load request,
so a UI load cannot happen (**Verified** in the fork's test branch).

**`world_mutated`.** Set immediately before a mutating command's engine call,
even if the call then fails; cleared only when a probe load completes.

**Autosave (Q4).** Native `autosave_enabled` is `OptionsHolder::autosave`, or
null when the options object is absent (then M2 refuses); whether that flag is
the effective autosave state is **Unknown** (a run also saw
`pauseAutoSaveTimer` set). MeitouClient reports false under the oracle,
because its autosave returns early in oracle mode (**Verified**).
`autosave_configured` is the `settings.cfg` value each engine read (native:
the same options flag). The runner requires both to be `false` on either
target, so one install gives the same answer on both engines.

`gate` object (in `setup_info` and in every census and mutating reply):

| Key | Type | Meaning |
| --- | --- | --- |
| `open` | boolean | G1-G3 pass. Always true in a successful census or mutation reply. |
| `probe_loaded_save` | string or null | Save of the probe's completed `load_save` in this epoch. |
| `allow_setup` | boolean | The opt-in in effect for that load. |
| `epoch` | integer | Engine-local world epoch, opaque; compared only for equality within one `instance_id`. |
| `refusal` | null or `{code,message}` | What a read-only setup command would get now. |
| `mutation_refusal` | null or `{code,message}` | What a mutating command would get now (adds M1, M2). |

## Commands

### `setup_info`

No parameters. Gate G1 only.

| Key | Type |
| --- | --- |
| `gate` | gate object |
| `current_save` | string or null (engine metadata, see `ping`) |
| `probe_loaded_save` | string or null |
| `world_mutated` | boolean |
| `autosave_enabled`, `autosave_configured` | boolean or null |
| `player_save_requests_blocked` | boolean (MeitouClient true under the oracle; native false: the probe cannot block UI save keys) |
| `squad_size` | null on native (the runner reads it from preserved settings), else `{source:"settings.cfg" or "user_config" or "default", multiplier:number, line:string or null, sha256:string or null, path:"settings.cfg"}` |

`multiplier` is the value the engine actually passes to the squad plan
(MeitouClient may take it from its user config). Line selection, used by the
adapter and by the runner on preserved bytes alike: split the raw file bytes
on `\n`, strip one trailing `\r` and a UTF-8 BOM on the first line; a line
matches when the bytes before its first `=`, trimmed of ASCII whitespace and
ASCII case-folded, equal `squad size multiplier`. Exactly one match gives
`line` (those bytes, decoded UTF-8) and `sha256` (lowercase hex over those
bytes); zero or several give null, and the runner refuses. `path` is relative
to the install root. Only that file exists on the reference install; that the
original reads it is inferred, not **Verified**.

### `setup_area_census`

| Parameter | Type and range |
| --- | --- |
| `center` | `[x,y,z]`; distance is horizontal (X/Z), `y` is ignored but must be finite |
| `radius` | number 0.1..20000 |
| `limit` | integer 1..100 |

Characters: the same set as `dump_state` on each engine (native
`loadedObjects`: update list, death list and active-platoon members). A
character is in when `distance_xz <= radius` (inclusive).

| Key | Type |
| --- | --- |
| `center`, `radius` | echo |
| `characters` | array of rows `{id, template_id, faction_id, squad_id, position:[x,y,z], is_player, dead, unconscious, distance_xz}`, sorted by `distance_xz` then `id` (ordinal byte order), at most `limit` |
| `count` | integer, all matches |
| `truncated` | boolean, `count > len(characters)` |
| `alive_count`, `dead_count`, `unconscious_count`, `player_count` | integers over all matches (unconscious excludes dead; alive is neither) |
| `gate` | gate object |
| `world` | `{elapsed_seconds, paused}` |

Census rows carry no `medical` (response budget); see S6.

### `setup_spawn_squad`

| Parameter | Type and range |
| --- | --- |
| `template_id` | string 1..128 bytes, a SQUAD_TEMPLATE record |
| `faction_id` | string 1..128 bytes, exact faction id |
| `position` | `[x,y,z]` |
| `max_count` | integer 1..16 |
| `permanent` | optional boolean, default false |

The native probe passes size multiplier 1.0 and squad type roaming; whether
the engine also applies `settings.cfg` inside the call is **Unknown**.
MeitouClient spawns the template plan with the session multiplier, idle,
outside any town, on the ground (ignores `y`), and ignores `permanent`
(both reported in `engine_detail`).

| Refusal (in order) | Code | Message |
| --- | --- | --- |
| template absent | `not_found` | `template not found` |
| record is not a squad template | `invalid_request` | `template is not a SQUAD_TEMPLATE record` |
| faction absent | `not_found` | `faction not found` |
| player faction | `invalid_request` | `spawning into the player faction is refused` |
| more than 2000 units X/Z from every non-dead player character | `invalid_request` | `spawn position must be within 2000 units (horizontal) of a player character` |
| MeitouClient only: session multiplier is not 1 | `invalid_request` | `squad size multiplier must be 1` |
| MeitouClient only: the plan names a unique character (planned before any mutation; consumes no spawn serial, leaves `world_mutated` unchanged) | `invalid_request` | `the squad plan names a unique character` |
| after the call: a new character is a player character | `state_unavailable` | `unexpected player enlistment; reload the save` |

| Key | Type |
| --- | --- |
| `template_id`, `faction_id`, `position`, `max_count`, `permanent` | echo |
| `size_multiplier` | number (native 1.0; MeitouClient the session value, so 1) |
| `squad_type` | `"roaming"` on native, `null` on MeitouClient |
| `returned_squad_id` | string or null |
| `returned_members` | array of `{id, template_id, faction_id, squad_id, position, dead, unconscious, medical}` in engine order; `medical` is the `setup_heal` shape or null, with `max` number or null |
| `new_loaded_count` | integer, characters newly loaded by the call |
| `new_loaded_truncated` | boolean, true above 32; the runner requires false |
| `rng_key` | decimal string on MeitouClient (a function of `template_id` and the accepted-spawn serial since the last completed load), `null` on native |
| `saved`, `world_mutated`, `gate`, `world_before`, `world_after` | common |

An empty result is not a refusal: `returned_squad_id:null`,
`returned_members:[]`, and the runner fails the step.

### `setup_set_relation`

One direction per call. The probe calls only the relation setter and no
war-flag setter; whether the native setter changes a war state internally is
**Unknown**.

| Parameter | Type and range |
| --- | --- |
| `source_id` | string 1..128 bytes, exact faction id |
| `target_id` | string 1..128 bytes, exact faction id |
| `value` | number -100..100 |

| Refusal (in order) | Code | Message |
| --- | --- | --- |
| source or target absent | `not_found` | `faction not found` |
| source equals target | `invalid_request` | `source and target must differ` |
| relation table unavailable | `state_unavailable` | `faction relations unavailable` |

| Key | Type |
| --- | --- |
| `source_id`, `target_id`, `value` | echo |
| `source_to_target`, `target_to_source` | `{before:{relation, is_enemy, at_war}, after:{relation, is_enemy, at_war}}` |
| `changes` | array of `{source_id, target_id, relation_before, relation_after, is_enemy_before, is_enemy_after, at_war_before, at_war_after}`, diff of the whole matrix as read through the relation getter, at most 100 rows |
| `changed_cells` | integer, all changed cells |
| `changes_truncated` | boolean |
| `faction_count` | integer |
| `saved`, `world_mutated`, `gate`, `world_before`, `world_after` | common |

`at_war` is null on native until a war-flag reader is verified (reason in
`engine_detail`). One call may change both cells of the pair: natively a
single set changed both directions (**Observed**: 2 cells, then 0), and
MeitouClient stores a pair with the player faction in one cell read from both
sides (**Verified**: 2 cells, then 0). So per call `changed_cells` is at most
2 and every changed cell is `(a,b)` or `(b,a)`.

### `setup_heal`

| Parameter | Type and range |
| --- | --- |
| `character_id` | string 1..200 bytes |

| Refusal (in order) | Code | Message |
| --- | --- | --- |
| id malformed, unknown, not a character, or not loaded | `not_found` | `character is not loaded` |
| character dead | `invalid_request` | `character is dead` |
| no medical state, a part without data or side, or a negative or non-finite maximum | `state_unavailable` | `medical system unavailable` |

| Key | Type |
| --- | --- |
| `character_id` | echo |
| `before`, `after` | `{parts:[{id, flesh, stun, max}], blood, dead, unconscious}`; parts in body order (part index), unlike the state's id order |
| `saved`, `world_mutated`, `gate`, `world_before`, `world_after` | common |

`max` is the stored part maximum on the original and the calculated maximum on
MeitouClient; neither is assumed equal. MeitouClient's heal leaves the
unconscious flag until the next body tick (**Verified**); the original's
behaviour is **Unknown**. The runner therefore fails setup with
`unconscious before heal` when a character to heal is unconscious in the S3b
dump.

## Changes to existing commands

| Command | Change |
| --- | --- |
| `load_save` | Optional `allow_setup` boolean, default false, echoed in the result. The MCP tool `load_save(..., allow_setup=False)` sends the key only when true. |
| `ping` | Adds `capabilities:["scene_setup"]`, `world_readiness`, `world_mutated` (boolean), `build_commit`, `state_schema_version:"0.2"` next to the existing `schema_version`. `plugin_version` is `"0.11.0"` on both engines. |
| `save_scene_snapshot` | Native: while `world_mutated`, refused with `oracle::Error` `not_allowed` / `the world was changed by scene setup; reload it before saving`, checked before the existing `world not ready` refusal; its other texts are unchanged. MeitouClient has no such command and refuses every player save under the oracle. |
| `issue_order` | Unchanged and id-only; aliases never reach a probe. |
| `prepare_town_scene`, `prepare_battle_scene` | Unchanged (Q2). |

`world_readiness` (ping only; no `window` key): booleans or null
`world_present`, `initialized`, `game_resetting`, `loading_from_save`,
`load_pending`, `load_pause_pending`, `world_ready`, `paused`; strings or null
`loading_from_save_unavailable_reason`, `paused_unavailable_reason`,
`zone_manager_unavailable_reason`; `zone_manager_is_loading` number or null
(raw engine value, meaning **Unknown**); `frame` number. A term an engine does
not have is null with its reason (MeitouClient: no reset flag, no zone
manager). MeitouClient adds `covered`, `warming`, `sky_arrival`,
`overlay_exiting` and `load_error`. The runner reads only `world_ready` and
`paused`.

`build_commit` is the full 40-character lowercase commit the binary was built
from, or exactly `"unknown"` (no git, any git failure, or a tree with
uncommitted changes per `git status --porcelain`). Native: `build-v100.cmd`
runs `git rev-parse HEAD` and passes `/DKENSHI_PROBE_BUILD_COMMIT`, appended
to the project's preprocessor definitions. MeitouClient: a separate assembly
metadata item `OracleBuildCommit` computed the same way at build time and
checked against `^[0-9a-f]{40}$` at startup; the existing UI commit string is
left alone.

## Aliases

Aliases are resolved by the runner, never by a probe: spawned ids differ
between engines and MeitouClient reuses ids after each load.

| Form | Binds to | Bound at |
| --- | --- | --- |
| `player` | the player character, when the S0 census has exactly one (then no `player/<n>`) | S0 |
| `player/<n>` | with more than one, every player character sorted by id (ordinal), `n` from 1 (then no `player`) | S0 |
| `<spawn alias>` | the squad returned by that spawn | S2 |
| `<spawn alias>/<template>/<k>` | the `k`-th member (from 1) of that template in `returned_members` order | S2 |

- Spawn alias: `^[a-z][a-z0-9-]{0,31}$`, unique, never `player`.
- Full alias: `^[a-z][a-z0-9-]{0,31}(/[A-Za-z0-9][A-Za-z0-9._-]{0,127})*$`
  (template ids contain dots, so path segments allow `.`), and it must have
  one of the four forms above.
- In a scenario `issue_order`: `character_alias` and `target_alias` name a
  character form; `squad_alias` names a spawn alias. Exactly one actor among
  `character_id`, `squad_id`, `character_alias`, `squad_alias`; for an attack,
  exactly one of `target_id`, `target_alias`.
- The runner substitutes `character_id`, `squad_id`, `target_id` before the
  call. An alias not in `alias_map` raises `ScenarioError`. Each action result
  records `request` (as written), `resolved_params` and `result`.
- In `variability`, `flatten_state` and every comparator metric, an id in the
  execution's `alias_map` is replaced by `alias:<alias>`; member aliases are
  compared only as (spawn alias, template) aggregates. A spawned id never
  appears raw in a compared path. There is no leader alias.

## Scenario-0.2 `setup` block

Schema file `schema/scenario-0.2.schema.json` (added in W1; `$id`
`urn:kenshi-oracle:scenario:0.2`, `schema_version` const `"scenario-0.2"`).
[scenario.schema.json](../schema/scenario.schema.json) (0.1) is unchanged.
With `setup`, `speed` must be above 0. Every object has
`additionalProperties:false` and every key below is required.

```json
"setup": {
  "preflight": {
    "scene_center": [0, 0],
    "scene_radius": 1500,
    "squad_size_multiplier": 1,
    "player_faction_id": "<faction id>",
    "expect_absent_factions_in_scene": ["<faction id>"]
  },
  "moves": [],
  "spawns": [{
    "alias": "bandits",
    "squad_template": "<template id>",
    "count": 4,
    "faction_id": "<faction id>",
    "at": {"offset_from_player": [30, 0]},
    "expected_templates": {"<template id>": 1, "<template id 2>": 3}
  }],
  "settle": {"sim_seconds": 1},
  "heal": "all_scene_characters",
  "relations": [{"a": "<faction id>", "b": "<faction id>", "a_to_b": -60, "b_to_a": -60}]
}
```

| Key | Rule |
| --- | --- |
| `scene_center` | `[x,z]`; the census uses `[x,0,z]` |
| `scene_radius` | number above 0, at most 20000 |
| `squad_size_multiplier` | const 1 |
| `expect_absent_factions_in_scene` | none of them in the S0 census |
| `moves` | `maxItems:0` in scenario-0.2 |
| `spawns` | 1..4 items; `count` 1..16 is `max_count`; `expected_templates` counts must sum to `count` |
| `offset_from_player` | `[dx,dz]` from the single `player` paused position, at that player's Y; the point must lie within `scene_radius` of `scene_center` |
| `settle.sim_seconds` | const 1 (33 calendar seconds) |
| `heal` | const `"all_scene_characters"`: every player character bound at S0 (those within `scene_radius`) and every spawned member |
| `relations` | 1..4 items, `a != b`, both directions required, integer values -100..100; no war-flag field exists. `is_enemy` is read back and recorded, never asserted by the schema (MeitouClient's hostility threshold is -30, **Verified**; the native one is **Unknown**; -60 read hostile on both, **Observed**) |

The runner always executes spawn, settle, heal, relations, whatever the key
order. No pinned height appears in a scenario.

## Engine profile

A local JSON file named by the config key `engine_profile`, never committed;
schema file `schema/engine-profile.schema.json` (added in W6).

```json
{"profile_format": "engine-profile-0.1", "entries": [
  {"target": "original", "save": "oracle-base-nature", "source_fingerprint": "sha256:<64 hex>",
   "seed": null, "player": {"xz": [0, 0], "y_before_settle": 0, "y_after_settle": 0, "decimals": 3},
   "evidence": "<relative path or run id>"}
]}
```

- Lookup key: `target`, `save`, `source_fingerprint` (from the load's saved
  origins or source manifest), `seed` (decimal string on MeitouClient, `null`
  on the original).
- Pins exist for `oracle-base-nature` only (Q5). `seed` is `null` on the
  original, and `null` on MeitouClient when one pin applies to every seed
  (the initial entry: Y 736.593 was read with seeds 0 and 1, **Observed**);
  a decimal-string seed entry takes precedence over the `null` one. The pin is
  still checked on every repetition, so a seed whose height differs fails that
  repetition, it is never averaged or widened. Before the restoration guard is
  armed, the runner checks that every planned repetition resolves to exactly
  one entry; any other save, a missing entry or an ambiguous match fails
  closed before repetition 1.
- Check: `abs(observed - pin) <= 0.5 * 10**-decimals`, in Python on the reply
  floats. S0: player X/Z against `xz`, Y against `y_before_settle`; after S3:
  X/Z unchanged, Y against `y_after_settle`. Observed, pin and delta go to
  `receipt.settle`.

## Runner steps

Run between the speed preparation and the origin `get_clock`, so checkpoint 0
is the verified post-setup world. Before the restoration guard is armed, a
scenario with `setup` requires `"scene_setup"` in `ping.capabilities`, the
profile entries above and, on the original, `engine_facts` from the reference
launcher (none: fail before any mutation). The save is loaded with
`allow_setup:true` only for a scenario with `setup`; the runner requires
`accepted.allow_setup === true`, then after readiness `gate.allow_setup` true
and `gate.probe_loaded_save` equal to `scenario.save`.

Before and after every step: `ping` (same `instance_id`, `world_ready`,
`paused`, expected `world_mutated`, and `saved_origins_prepared` on the
original) and `setup_info` (`gate.open`, `gate.epoch` equal to its S0 value,
and `gate.mutation_refusal` null before a mutating step). Any failure raises
`ScenarioError` with no retry; the normal restoration runs. Step names keep
the plan numbering (S1 is reserved for moves).

| Step | Work and checks |
| --- | --- |
| S0 | `get_clock`, `setup_info`, census (limit 100, not truncated). Bind players. Absent factions absent. Multiplier 1: native from `engine_facts`, MeitouClient from `setup_info` with `source:"settings.cfg"`; both require the line's parsed value equal to the engine value. `autosave_enabled` and `autosave_configured` false. Pin check. |
| S2 | Spawn point checked inside `scene_radius`, then `setup_spawn_squad` per spawn. Requires `returned_squad_id` non-null, `len(returned_members) == count == new_loaded_count`, `new_loaded_truncated` false, every member's `squad_id == returned_squad_id`, `medical` non-null, the faction, alive, and `expected_templates` (a mismatch fails with `template plan differs`). A census confirms the new characters. Bind aliases. |
| S3 | `start` = `get_clock().elapsed_seconds` read after S2 and after `set_game_speed(1, preserve_pause=true)`; `run_until(start+33)`, paused at target; pin check; `calendar_seconds_run` = completion clock − `start` (overshoot recorded, not failed). |
| S3b | `dump_state` to `setup/S3b.json`. A character to heal that is unconscious here fails with `unconscious before heal`. |
| S5 | `setup_heal` per bound player and member. Every part `flesh == max` (`max` non-null) and `stun == 0`, not dead, not unconscious. Dump `setup/S5.json`; its relations equal S3b's. |
| S4 | Per relation item: `(a,b,a_to_b)` then `(b,a,b_to_a)`. Each call's changed cells are only `(a,b)` or `(b,a)`; per-call `changed_cells` is recorded in `read_back`, not judged. After the pair both directions read the requested value; `is_enemy` is recorded both ways and must be `true` when the value is -60 or lower (the hostility Observed on both engines), otherwise it is recorded only; where `at_war` is non-null, `after == before` in both directions, and a null is recorded as the limitation `war flag not observable on <target>`. |
| S6 | Dump `setup/S6.json` and census. Relations differ from S5 only in the pair cells, and the dump reads `a_to_b` and `b_to_a` for each item. Every alias is in the census, not dead, not unconscious. Heal state rests on the S5 replies (census has no medical rows). |

Then, if `scenario.speed != 1`, re-select it with `preserve_pause`.

## Receipt, report and comparator

The receipt is written to `<execution>/setup/setup.json` and copied to
`execution.setup`, also on failure (`verdict:"failed"`) before the error is
raised.

| Key | Type |
| --- | --- |
| `receipt_format` | `"scene-setup-0.1"` |
| `target` | `"original"` or `"meitou"` |
| `setup_hash` | lowercase hex SHA-256 of `json.dumps(scenario["setup"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` encoded UTF-8 |
| `build_commit` | string from `ping` |
| `build_commit_known` | boolean, false for `"unknown"` |
| `alias_map` | object alias to id |
| `steps` | array of `{step, request:{command, params}, reply, read_back, verdict:"passed" or "failed"}`, one per command, in order |
| `dumps` | `{S3b, S5, S6}`, each `{path, sha256}`, path relative to the execution folder |
| `members` | array per character alias: `{alias, id, template_id, faction_id, part_max:{part id: max}, blood_before, blood_after, rng_key}` (maxima recorded per repetition, no verdict on the fight) |
| `squad_size` | `{source:"engine_facts" or "setup_info", multiplier, line, sha256, path}` |
| `settle` | `{sim_seconds:1, calendar_seconds_requested:33, start_seconds, end_seconds, calendar_seconds_run, player_before:[x,y,z], player_after:[x,y,z], pin, observed, delta}` |
| `limitations` | array of strings |
| `verdict` | `"passed"` or `"failed"` |
| `failure` | null or `{step, message}` |

**Report keys (every run, with or without setup).** `report.json` carries
`report_format:"0.1"`, `scenario_schema` (the scenario's `schema_version`),
`state_schema`, `build_commit`, `build_commit_known` and `limitations[]`; the
bare `schema_version` key is removed. `build_commit` comes from `ping`; with
`build_commit_known:false` the runner adds `"commit unknown"` to
`report.limitations` (and to the receipt), and a commit that changes between
repetitions fails the run. Each checkpoint capture adds
`setup:{setup_hash, alias_map, census:{count, truncated, alive_count,
dead_count, unconscious_count, player_count}}` (recorded, not compared).

**Comparator (Q10, owner block).** It refuses any campaign with
`build_commit_known:false`. A report without `build_commit` (before 0.11) is
refused for scenario-0.2 and stays comparable for 0.1 with the limitation
`build commit not recorded`. A campaign with a setup is accepted only when
every execution has `verdict:"passed"`, a `setup_hash` equal to the hash
recomputed from `scenario.setup`, every capture's `alias_map` equal to its
execution's, and the same alias key set in every execution.

| Scope | Contents | Use |
| --- | --- | --- |
| in scope | alias ids, player ids, characters with X/Z distance to `scene_center` `<= scene_radius` | |
| `/scene/` | alias presence and missing, `/scene/intruders/count`, the declared relation pairs both ways | classified |
| `/scene/outcome/` | alias and player cohort survivors, dead, unconscious, health, engagement traces | reported per repetition, never classified |
| `/background/` | `/population/*`, `/clock/*`, every other relation, saved metrics and temporal findings outside the alias and player cohorts | `report.background_metrics`, never classified |

A limitations line in the comparison states that outcome and background
metrics are not classified.

## Implementation notes (not contract changes)

- Native: port the private menu-drain condition with the prefix `setup_`;
  use `oracle::position` in every setup row; sort census rows by id, not by
  pointer; build `squad_size` facts in the runner from preserved bytes.
- MeitouClient: one gate helper in contract order and texts (it currently
  checks pause first and keeps the allowlist); contract parameter helpers for
  `setup_*` only (UTF-8 byte length, NUL, separate integer check), with each
  handler reordered to keys, gate, values, lookups; plan the spawn outside the
  edit bracket and commit the serial only after the unique check; refuse a
  dead or medical-less heal; take only `character_id`; a projection layer that
  emits exactly the contract keys (extras go to `engine_detail`); add
  `loading_from_save_unavailable_reason:null` and drop `window`; a raw-line
  reader for `settings.cfg`.
- Parameter renames from the private build: `faction`/`faction_match` become
  `faction_id`; `source`/`target`/`match` become `source_id`/`target_id`.

## What stays private

Not in the public probe, adapter or runner: the `test_*` commands and their
test build, including `test_set_health`, `test_spawn_character`,
`test_teleport_platoon`, `test_autosave_state`, `test_window_watch` and its
loading-window record, and `name_prefix`; the content and resource audits
(`get_loaded_mods`, `get_effective_preferences` and the audit tools); the
private harness and its results; local saves and engine-profile files.
