<a id="couverture-de-létat-commun-01-et-02"></a>

# Shared state 0.1 and 0.2 coverage

The contracts are [state.schema.json, 0.1](../schema/state.schema.json) and [state-0.2.schema.json](../schema/state-0.2.schema.json). The native adapter is in [OracleState.h](../plugin/OracleState.h); shared validation and normalization are in [oracle_schema.py](../mcp-server/oracle_schema.py). This page distinguishes the existence of an API from validation of a real capture.

- **Verified**: declaration present in the public headers used, with an explicit mapping in our code. This alone does not prove safety or completeness in every scene.
- **Observed**: limited behavior established by the cited trials; distinguish their versions and do not extend it to other scenes.
- **Unknown**: a property that has not been demonstrated; no replacement value is invented.

The header paths below are relative to `references/KenshiLib_Examples_deps/KenshiLib/Include/kenshi/`. This directory is a local dependency ignored by Git. Names come from the [public KenshiLib SDK](https://github.com/BFrizzleFoShizzle/KenshiLib), not addresses copied from the executable.

A first real capture is recorded in `runtime/oracle-phase1/first-real-dump.json`: **106 characters, 35 squads, 114 factions and 12 882 relations**, representing the 114 × 113 directional pairs excluding self. The 1 125 301-byte file passes the schema 0.1 loader; its native bytes are identical to the copy and Python normalization, SHA-256 `d775f1caa1911a9c7b0b4095c2680fe383996fd72516035c10e1f35bae05db23`. All 106 characters have an available health collection; 98 have `order:null`. These files remain local, outside Git. Since then, **three successful travel runs and three successful battle runs**, 18 canonical captures and exact restoration of controls without camera following have been established on 0.9.1 in the [validation report](oracle-phase1-validation.md), which also retains the first battle trial that failed. Populations and some values vary across repetitions; determinism is not claimed.

Version **0.9.3** adds canonicalization of saved identities, retained in 0.9.5. Its [initial real trial](../../oracle-phase1/identities-smoke-093.json), outside Git, completed with a context of 1 470 origins, 138 links to loaded objects and three remapped character identifiers. The dump retains 106 characters, 35 squads, 114 factions and 12 882 relations; its native, MCP and canonical Python bytes match, SHA-256 `ec6ab440861f637f1d1e087fd712b06be0b58e2147e6f44662cf5dd0fe0e9824`. This initial evidence is supplemented by the **27 canonical captures** from the three examples, each replayed three times on the final 0.9.3 DLL, SHA-256 `ebce02cd618675e88d1cadf7a239b964b3a4347825ecae5e63c7da87c2d52f91`. The [delivery report](oracle-phase1-delivery.md) retains their variability and distinguishes the 0.9.5 restoration validation.

| Field or collection | Exact public source and conversion | Status and limits |
| --- | --- | --- |
| `schema_version` | Requested version `0.1` or `0.2`, without an engine API. | **Verified** in the schemas and serializers. The historical evidence above concerns 0.1. |
| `clock` | `GameWorld.h:238`, `GameWorld::getTimeStamp_inGameHours()`; `util/TimeOfDay.h:23`, `TimeOfDay::getTotalHours()`. | **Verified**; progression and lack of movement while paused are **Observed** in the [clock measurements](research/simulation-clock-measurements.md). |
| `clock.day` | `floor(total_hours / 24)`, carrying into the next day if the rounded hour reaches 24. | **Verified**: zero-based day. This is not the day displayed starting at 1 in the interface. |
| `clock.hour` | `total_hours % 24`, with shared six-decimal rounding. | **Verified**; native code normalizes an hour rounded to 24 to zero on the following day. The schema also permits 24 for another adapter's representation of this boundary. |
| `clock.elapsed_seconds` | `getTotalHours() * 3600`. | **Verified**: world-calendar seconds. Neither QPC nor real seconds nor `TimeOfDay::getTotalSeconds()`, whose unit must not be assumed equivalent. Simulated-time equivalent: 1 simulated second = 33 calendar seconds per MeitouClient's `1200/11` s per in-game hour (**Verified** in its code); not yet measured on either target (**Unknown**). See [time units](protocol.md#time-units). |
| `clock.speed` | `GameWorld.h:208`, `GameWorld::frameSpeedMult`. | **Observed** during the first oracle trial: **effective** multiplier, zero while paused, like `getFrameSpeedMultiplier()` (`:127`). The initial hypothesis that this field retained the selected speed was disproved. No public getter for the selected speed has been identified. |
| `clock.paused` | `GameWorld.h:131`, `GameWorld::isPaused()`. | **Verified**; control/restoration **Observed** in 0.8.20 and the three 0.9.1 travel repetitions. |
| `characters` | Union of `GameWorld::getCharacterUpdateList()` (`GameWorld.h:140`), `GameWorld::deathParade` (`:210`) and active squad members: `FactionManager::getAllFactions()` (`Faction.h:194`), `Faction::getActivePlatoons()` (`:106`), `Platoon::getActivePlatoon()` (`Platoon.h:168`), `RootObjectContainer::getThings()` (`RootObject.h:196`). Deduplicated by identifier. | API **Verified**; 106 rows **Observed** in the first real dump. Completeness of this union among all characters in memory is **Unknown**. Explicit safety limits; a truncated capture is never presented as complete. |
| `characters[].id` | `RootObjectBase.h:63`, `RootObjectBase::getHandle()`; `util/hand.h:33–37`, five HAND components. Since 0.9.3: public constructor `hand(index, serial, type, container, containerSerial)` (`:29`), then `getCharacter()` (`:49`), checked against the loaded inventory and a complete current → saved table. | Reading and canonicalization **Verified** in code; three engine resolutions with different C/CS and three saved IDs in the dump **Observed** in the initial 0.9.3 trial. Other objects retain their current HAND. A universally stable identity is **not demonstrated**; no association by name, position or I/S. [Evidence and scope](npc-identities-phase1.md). |
| `characters[].name` | `RootObjectBase.h:32`, `RootObjectBase::getName()`. | **Verified**, names **Observed** through `list_characters`. A name is never an identity key. |
| `characters[].race_id` | `Character.h:562`, `Character::getRace()` → `RaceData.h:31`, `RaceData::data` → `GameData.h:92`, `GameData::stringID`. | **Verified**, identities **Observed** in the first real dump; `null` if data is absent. |
| `characters[].faction_id` | `RootObjectBase.h:52`, `getFaction()` → `Faction.h:86`, `Faction::getData()` → `GameData::stringID`. | **Verified**; character faction **Observed** in the historical inventory. `null` if absent. |
| `characters[].squad_id` | `Character.h:588`, `getPlatoon()` → `Platoon.h:265`, `ActivePlatoon::me` → `RootObjectBase::getHandle()`, then the same context's canonicalization table. | **Verified**; `null` without an available squad. A reference without a proven link retains its current HAND. |
| `characters[].position` | `Character.h:332`, `Character::getPosition()` → x, y, z components. | **Verified**, positions **Observed**. Absolute world coordinates; y is height. The schema permits `null` for an adapter without a reading; native code rejects a non-finite position. |
| `characters[].state` | `Character.h:619`, `isDead()`; `:470`, `isUnconcious()` (public spelling). Dead takes precedence, then unconscious, otherwise alive. | **Verified**; wounds/unconsciousness **Observed** in [battles](research/battle-observations.md). The schema permits `null` if the reading is unknown. |
| `characters[].health` | `Character.h:533`, `getMedical()` → `MedicalSystem.h:184`, `getPartCount()` and `:181`, `getPart(unsigned __int64)`. | **Verified**; historical partial medical reading **Observed**. `null` if the system or a part is missing; `[]` only for an ensemble known to be empty. |
| `characters[].health[].id` | `MedicalSystem.h:131`, `HealthPartStatus::data` → `GameData::stringID`, then `:145`, `HealthPartStatus::side`. | **Verified**: suffix `:neither`, `:left`, `:right` or `:both`. Unknown side value: the entire health value is `null`, with no array index used as an identity. |
| `characters[].health[].current` | `MedicalSystem.h:167`, `HealthPartStatus::flesh`. | **Verified**, wounds **Observed** in two battle replay repetitions, minimum 16,303886 for the attacker; negative values allowed. `null` if non-finite. |
| `characters[].health[].stun` | `MedicalSystem.h:168`, `HealthPartStatus::fleshStun`. | **Verified**, positive values **Observed** alongside wounds in the battle replay; `null` if non-finite. |
| `characters[].health[].maximum` | `MedicalSystem.h:173`, `HealthPartStatus::_maxHealth`. | **Verified** as a stored value; `null` if negative or non-finite. Equivalence to maximum health recalculated after age/multipliers is **Unknown**; this field exposes precisely the stored value. |
| `characters[].order` | `Character.h:530`, `getBody()` → `CharBody.h:67`, `getCurrentAction()`. | **Verified**; immediate task, not the complete order queue or long-term objectives. `move_cus_ordered`, then `null` after movement, **Observed** for Ryers and Okada in all three repetitions. `null` if there is no action, `NULL_TASK`, no body or an unknown type. |
| `characters[].order.type` | `Tasker.h:142`, `Tasker::key()`; public enumeration names from `Enums.h`, own table `OracleTaskNames.h`, converted to lowercase. | **Verified**. A future type absent from the table remains unknown and leaves a TODO; no C++ enumeration integer enters the schema. |
| `characters[].order.target_id` | `Tasker.h:146`, `Tasker::subject`, encoded as a `hand`, then canonicalized if its full handle is linked to the context. | **Verified**; correct target **Observed** for the replay's targeted attack. `null` for a null handle. It may reference an absent object: type 0 observed during autonomous movement means `BUILDING` (`Enums.h:4–7`). Fleeing references the actor itself. Other references retain their current HAND; no universal combat target is assumed. |
| `characters[].order.position` | `Tasker.h:147`, `Tasker::getLocation()` for `MOVE_CUS_ORDERED`, `MOVE_ON_FREE_WILL`, `MOVE_ON_FREE_WILL_FAST` only. | API **Verified**; requested destination **Observed** for `MOVE_CUS_ORDERED` in all three travel runs. Position exposed for those three types if finite and absolute value at most 1e9. `null` for other tasks, whose storage may be dormant. The meaning of `[0,0,0]` observed in autonomous movement is **Unknown**; the fast autonomous type has not been observed. |
| `squads` | Faction manager's active squads and squads referenced by captured characters. | **Verified** in the adapter. Entirely unloaded squads are outside this snapshot's scope. |
| `squads[].id` | `Platoon` inherits `RootObjectBase`: `getHandle()`; public constructor `hand(...)`, then `hand::getPlatoon()` (`util/hand.h:50`) for indexed origins, checked against the loaded inventory. | API and canonicalization **Verified**. Ryers/Okada's squad **Observed** stable in the three historical travel runs; 22 initial squad HANDs identical in town. The initial 0.9.3 trial records zero squad remappings; it does not validate a real remapping in this category. Universal stability is not established. [Limits](npc-identities-phase1.md). |
| `squads[].faction_id` | Inherited `Platoon::getFaction()`; `Faction::getData()->stringID`. | **Verified**; `null` if absent. |
| `squads[].members` | Identifiers of captured characters whose `Character::getPlatoon()->me` designates this squad, canonicalized using the same context as `characters[].id`. | **Verified**: members **loaded in this snapshot**, not the total saved membership. Lexical sorting after canonicalization; duplicates rejected. |
| `squads[].leader_id` | `Platoon.h:191`, `Platoon::getSquadLeader_theRealOne()` returns the designated leader's `hand`, then the same context's table. | **Verified**. Does not substitute the active deputy for the leader; may reference an unloaded leader. `null` for a null handle; a reference without a proven link is retained unchanged. |
| `factions` | `GameWorld.h:101`, `factionMgr` → `FactionManager::getAllFactions()` and factions of captured characters. | **Verified**: factions registered in the live manager, not only those with a visible character. |
| `factions[].id` | `Faction.h:86`, `Faction::getData()` → `GameData.h:92`, `stringID`. | **Verified**; data identity, independent of display name and address. |
| `factions[].name` | `Faction.h:115`, `Faction::getName()`. | **Verified**, names **Observed** in the historical inventory. |
| `relations` | All ordered pairs of captured factions, excluding self-relations. | **Verified** in our code; 114 × 113 = 12 882 relations **Observed** in the first real dump. |
| `relations[].source_id`, `target_id` | `GameData::stringID` identities of the two factions. | **Verified**; source/target order is meaningful, no symmetry assumed. |
| `relations[].value` | `Faction.h:128`, `Faction::relations` → `FactionRelations.h:35`, `getFactionRelation(Faction*)`. | **Verified**; reciprocal hostility **Observed** in some battles. `null` if the object or value is unavailable; do not substitute zero. |

<a id="extension-additive-02"></a>

## Additive extension 0.2

Version 0.1 remains unchanged. Version 0.2 retains its fields and requires
**seven additional fields**: four per character and three per squad.
Changing only `schema_version` is insufficient. The runner selects 0.2 if the
probe advertises it, otherwise 0.1; `state_schema` explicitly requests either
version. A version change during an execution is rejected.
Scenarios and reports retain their own version 0.1.

| Added field | Native source and Meitou projection | Certainty and limits |
| --- | --- | --- |
| `characters[].identity_origin` | Native: `SavedOrigins::hasSavedOrigin`, after full HAND resolution. Meitou: `CharacterCold.Save.Source.Handle`, retained by the loader. | **Verified in code**, saved origin **Observed** on the native side. Values `saved`, `generated` or `null`; current producers do not emit `generated`. An absent link remains unknown. |
| `characters[].current_town_id` | Shared town **placement** key. Native and Meitou currently emit `null`. | **Unknown**: equivalence of `Town::instanceID.uid` and `TownSite.InstanceId` has not been verified in-game. No `TOWN` record, name, current HAND, proximity or index substitutes for it. |
| `characters[].town_assignment` | `inside`, `outside` or `null`; currently `null` in both producers. | `inside` requires a known `current_town_id`; otherwise this ID must be null. `outside` means an established absence; `null` does not mean outside town. Town groups are currently non-comparable. |
| `characters[].in_combat` | Native: `Character.h:538`, `isInCombatMode(true,true)`. Meitou: `WorldSnapshot.CombatMode`, published by the melee + ranged predicate, only with `CombatSystem` and a snapshot of the current tick. | Reading **Verified in code**, false values **Observed** in native quiet town; this does not validate a battle. `null` if coverage is unknown. Never inferred from an order, health or a target. |
| `squads[].identity_origin` | Native: the same resolved HAND table. Meitou: `PLATOON` HAND linked by the loader, or agreeing saved sources of members. | **Verified in code**, `saved` **Observed** on the native side. Same values and unknown rule as characters. A local ID does not establish generation. |
| `squads[].template_id` | Native: `Platoon.h:183`, `squadTemplate->stringID`. Meitou: `Squad.TemplateId`. | API **Verified**, non-null IDs **Observed** on the native side. `SQUAD_TEMPLATE`/`UNIQUE_SQUAD_TEMPLATE` data key, not a squad ID. Meitou creation paths with fallback values still require scope verification; an unproven value does not justify matching. |
| `squads[].origin_town_id` | Placement of the origin town, in the same namespace as `current_town_id`; currently `null` in both producers. | **Unknown** until this identity is proven. Does not describe current presence and cannot be inferred from a town name. |

Native extensions are in [OracleState.h](../plugin/OracleState.h) and
[OracleSavedOrigins.h](../plugin/OracleSavedOrigins.h). In the local fork,
`src/Meitou.Game/Oracle/OracleState.cs` produces these fields;
`src/Meitou.Simulation/WorldPublish.cs` publishes combat mode.
The [town identity design](meitou-oracle-design.md#identité-des-villes--distinction-à-préserver)
details the evidence levels.

**Observed on the original side:** a cold quiet-town cycle produced three
0.2 snapshots, N = 1, with verified restoration. At the initial checkpoint:
103 characters, including 80 linked to a saved origin, and 22 saved squads;
at the last: 133 characters, including 92 linked, and 27 squads,
including 24 linked. All 27 final templates are populated; town fields
remain null and combat mode is false in these snapshots. The
[local acceptance record](../../phase2-live-schema02/acceptance.json), ignored
by Git and not distributed, identifies the three SHA-256 hashes and restoration
of files/saves. These observations prove neither determinism nor parity.

The [original N = 5 campaign](../runs/ville-calme/20261029T195936.248409Z-8d76ea5c/report.json)
subsequently completed 15 snapshots in 0.2 with controls and player profile
restored, with effective evidence after a cold start. Capture DLL SHA-256:
`a42ac22176204e2a9cfea9e938adc87ba15fa1baa17d9914c9564698040ed512`.
This local report is ignored by Git and not distributed.

**Verified outside the game:** 62 shared canonical vectors, including the 59
historical ones, pass in C#, Python and the native encoder; all 115 focused
Oracle/camera fork tests pass, including initial preparation without simulation advance.

**Observed on the Meitou side:** a first real paused snapshot validates in
0.2: 960 345 bytes, 130 characters, 27 squads, 103 factions and 10 506
relations, seed 1729 applied before loading. SHA-256:
`931a6c5b1f55e49fea130f26cb012c8660f3c99273eb4b361cb90d200566ae71`.
The [local acceptance record](../../phase2-meitou-first/acceptance.json), not
distributed, confirms the owned process stopped, player settings and four
saves unchanged. One snapshot does not validate a complete scenario,
scenario-control restoration or comparison between engines.
The [Meitou quiet-town N = 5 campaign](../runs/meitou/ville-calme/20261029T200854.596180Z-c872b96e/report.json)
subsequently completed 15 canonical 0.2 snapshots with seeds 0..4 and restored
controls; the prepared seed 1729 is restored on the final reload.
A [Meitou battle N = 1](../runs/meitou/petite-bataille/20261029T200733.030331Z-fe023ab1/report.json)
completed three snapshots and restoration, with a health change observed on
two targeted saved HANDs. These reports remain local, outside Git.
A [Meitou travel run N = 1](../runs/meitou/trajet-escouade/20261029T201301.764942Z-52f15f5f/report.json)
also completed three snapshots and restoration. The 21 Meitou captures,
5-versus-5 quiet-town comparison and their limits are collected in the
[phase 2 report](phase2-validation.md).

The Meitou projection currently leaves `order` and `health[].maximum` as `null`:
equivalence of the task and stored maximum value has not been established.
See [Meitou configuration and limits](meitou-target.md).

<a id="identités-et-comparabilité"></a>

## Identities and comparability

Identity is `hand:TYPE:C:CS:I:S`, with five unsigned 32-bit decimal components. Since 0.9.3, the snapshot publishes the saved HAND when a complete link to the loaded object has been proven; otherwise it retains the current HAND. The schema still treats this as an opaque string: a C# adapter can produce it without exposing a C++ type. When a save reader represents a component as a signed integer, it must preserve all 32 bits and render them unsigned before encoding the identity. A race, faction or body part uses its data identity; identical data and mods are a prerequisite for comparison.

The [project's own FCS reader](../mcp-server/oracle_origins.py) follows the public format: type 15 only, `quick.save` and explicitly indexed `.platoon` files, volume/count limits, safe paths, ambiguities rejected. It produces origins located by file, state, instance and full HAND; it neither copies nor modifies a save. Hashes are checked during reading and after loading, before context publication. The fingerprint covers exactly those indexed files, not zones or portraits. The root comes from `SaveManager::getSavePath()`; a contradictory configuration is rejected. `getCurrentGame()` remains diagnostic: in the 0.9.3 trial it still says `ville-calme` while the loaded, verified context names `KenshiProbe_test`.

Resolution exclusively uses the public `hand(...)` constructor, `getCharacter()` / `getPlatoon()` and objects already inventoried as loaded. The returned candidate is not dereferenced to invent an identity. The current ↔ saved table enforces a bijection of full HANDs; collisions and duplicates fail the operation. It is tied to the load requested through the probe and its world epoch, invalidated on a load or world transition, then refreshed against objects still loaded. Native canonicalization covers character and squad IDs, members, leaders, squad references and order targets, before sorting and serialization. Origin metadata remains in the tool response, outside state schema 0.1. A dump without a prepared context returns `origin_context_required`.

Canonicalization is therefore **implemented**, and the three characters Ando/Hisako/Ishida are **Observed** under their saved HANDs after explicit engine resolution in the initial 0.9.3 trial. This exceeds the value matches alone from the [previous audit](npc-identities-phase1.md). It demonstrates neither the internal chain responsible for container changes nor a universal identity across saves or restarts. A character without a resolved origin retains its current HAND; that absence does not prove generation on load. All three saved HANDs appear in each of the nine final 0.9.3 travel captures; the [delivery report](oracle-phase1-delivery.md) states the scope of the other series and 0.9.5 validation. Squad references without a proven link remain current.

Collections and subcollections sort by identifier; relations by source/target pair. Finite numbers have absolute value at most 1e9 and are quantized to six decimals using `floor(abs(x)*1e6+0.5)`, then the sign is reapplied and negative zero normalized. Object keys are sorted, strings are UTF-8, independent of locale, with an LF terminator. C++/Python byte equality is verified on 59 synthetic states and real captures from the identified campaigns, including all 27 files in the final 0.9.3 batch; it does not prove Kenshi determinism.

Reading occurs while paused on the main thread, then the copy is serialized and written without accessing engine objects. Atomicity with respect to possible internal workers remains **Unknown**: pause and the capture boundary do not prove every engine thread is stopped. No wall time, PID, memory address or adapter name enters common state.

<a id="références-examinées"></a>

## References examined

[RE_Kenshi and its wiki](https://github.com/BFrizzleFoShizzle/RE_Kenshi/wiki), [HelloWorld and the examples](https://github.com/BFrizzleFoShizzle/KenshiLib_Examples), [KenshiCoop API reference](https://github.com/nhoral/KenshiCoop/blob/main/docs/API_REFERENCE.md), and Meitou documentation: [index and certainty levels](https://github.com/VlcekM/MeitouClient/blob/master/docs/README.md), [loop and clocks](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/game-loop.md), [factions and squads](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/factions-squads-towns.md), [health](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/character-stats.md), [tasks](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/ai-tasks.md). These references inform the contract; only existing SDK declarations authorize native calls. No decompiled code is copied into the project.
