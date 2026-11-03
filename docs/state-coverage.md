<a id="couverture-de-létat-commun-01-et-02"></a>

# Shared state 0.1, 0.2, 0.3, 0.4 and 0.5 coverage

The contracts are [state.schema.json, 0.1](../schema/state.schema.json), [state-0.2.schema.json](../schema/state-0.2.schema.json), [state-0.3.schema.json](../schema/state-0.3.schema.json), [state-0.4.schema.json](../schema/state-0.4.schema.json) and [state-0.5.schema.json](../schema/state-0.5.schema.json). The native adapter is in [OracleState.h](../plugin/OracleState.h); shared validation and normalization are in [oracle_schema.py](../mcp-server/oracle_schema.py). This page distinguishes the existence of an API from validation of a real capture.

- **Verified**: declaration present in the public headers used, with an explicit mapping in our code. This alone does not prove safety or completeness in every scene.
- **Observed**: limited behavior established by the cited trials; distinguish their versions and do not extend it to other scenes.
- **Unknown**: a property that has not been demonstrated; no replacement value is invented.

The header paths below are relative to `references/KenshiLib_Examples_deps/KenshiLib/Include/kenshi/`. This directory is a local dependency ignored by Git. Names come from the [public KenshiLib SDK](https://github.com/BFrizzleFoShizzle/KenshiLib), not addresses copied from the executable.

A first real capture is recorded in `runtime/oracle-phase1/first-real-dump.json`: **106 characters, 35 squads, 114 factions and 12 882 relations**, representing the 114 × 113 directional pairs excluding self. The 1 125 301-byte file passes the schema 0.1 loader; its native bytes are identical to the copy and Python normalization, SHA-256 `d775f1caa1911a9c7b0b4095c2680fe383996fd72516035c10e1f35bae05db23`. All 106 characters have an available health collection; 98 have `order:null`. These files remain local, outside Git. Since then, **three successful travel runs and three successful battle runs**, 18 canonical captures and exact restoration of controls without camera following have been established on 0.9.1 in the [validation report](oracle-phase1-validation.md), which also retains the first battle trial that failed. Populations and some values vary across repetitions; determinism is not claimed.

Version **0.9.3** adds canonicalization of saved identities, retained in 0.9.5. Its [initial real trial](../../oracle-phase1/identities-smoke-093.json), outside Git, completed with a context of 1 470 origins, 138 links to loaded objects and three remapped character identifiers. The dump retains 106 characters, 35 squads, 114 factions and 12 882 relations; its native, MCP and canonical Python bytes match, SHA-256 `ec6ab440861f637f1d1e087fd712b06be0b58e2147e6f44662cf5dd0fe0e9824`. This initial evidence is supplemented by the **27 canonical captures** from the three examples, each replayed three times on the final 0.9.3 DLL, SHA-256 `ebce02cd618675e88d1cadf7a239b964b3a4347825ecae5e63c7da87c2d52f91`. The [delivery report](oracle-phase1-delivery.md) retains their variability and distinguishes the 0.9.5 restoration validation.

| Field or collection | Exact public source and conversion | Status and limits |
| --- | --- | --- |
| `schema_version` | Requested version `0.1`, `0.2`, `0.3`, `0.4` or `0.5`, without an engine API. | **Verified** in the schemas and serializers. The historical evidence above concerns 0.1. |
| `clock` | `GameWorld.h:238`, `GameWorld::getTimeStamp_inGameHours()`; `util/TimeOfDay.h:23`, `TimeOfDay::getTotalHours()`. | **Verified**; progression and lack of movement while paused are **Observed** in the [clock measurements](research/simulation-clock-measurements.md). |
| `clock.day` | `floor(total_hours / 24)`, carrying into the next day if the rounded hour reaches 24. | **Verified**: zero-based day. This is not the day displayed starting at 1 in the interface. |
| `clock.hour` | `total_hours % 24`, with shared six-decimal rounding. | **Verified**; native code normalizes an hour rounded to 24 to zero on the following day. The schema also permits 24 for another adapter's representation of this boundary. |
| `clock.elapsed_seconds` | `getTotalHours() * 3600`. | **Verified**: world-calendar seconds. Neither QPC nor real seconds nor `TimeOfDay::getTotalSeconds()`, whose unit must not be assumed equivalent. Simulated-time equivalent: 1 simulated second = 33 calendar seconds per MeitouClient's `1200/11` s per in-game hour (**Verified** in its code); measured on MeitouClient; on the original the engine reports the same hour length and the simulated-time equivalence is argued (**Unknown**). See [time units](protocol.md#time-units). |
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
| `characters[].health[].maximum` | Native: `MedicalSystem.h:173`, `HealthPartStatus::_maxHealth`. Meitou (patch 0005): the calculated `HealthPart.MaxHp`. | Native: **Verified** as a stored value. Meitou: **Verified in code** as a calculated value, not the stored `_maxHealth`. Both are `null` if negative or non-finite (Meitou also above 1e9, as the native formatter). In the setup heal receipts of 1 November 2026 (unworn, full health) the saved player matched part by part, a stump at 5 included (**Observed**); spawned members of races `17-gamedata.quack` (100) and `5276-chareditor.mod` (125) showed the same value set on both engines, not the same characters, and the origin of 125 is **Unknown**; wear, prosthetics, robots, and multiplier or scale changes after load are **Unknown**. Equivalence of the native stored value to maximum health recalculated after age/multipliers is **Unknown**. |
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
probe advertises it, otherwise 0.1 (since [0.3](#extension-additive-03), the
highest version both sides advertise); `state_schema` explicitly requests a
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

The original N = 5 campaign (local evidence, not published)
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
The Meitou quiet-town N = 5 campaign (local evidence, not published)
subsequently completed 15 canonical 0.2 snapshots with seeds 0..4 and restored
controls; the prepared seed 1729 is restored on the final reload.
A Meitou battle N = 1 (local evidence, not published)
completed three snapshots and restoration, with a health change observed on
two targeted saved HANDs. These reports remain local, outside Git.
A Meitou travel run N = 1 (local evidence, not published)
also completed three snapshots and restoration. The 21 Meitou captures,
5-versus-5 quiet-town comparison and their limits are collected in the
[phase 2 report](phase2-validation.md).

The Meitou projection leaves `order` as `null` in states 0.1 to 0.3:
equivalence of the task has not been established (state
[0.4](#extension-additive-04) adds a Meitou order, and
[0.5](#extension-additive-05) a plan-step order for a goal's task). Since patch 0005 of the
[Meitou series](../integrations/meitou/README.md), `health[].maximum` is
Meitou's calculated part maximum, not the stored value, and `null` when negative
or non-finite. In the 1 November 2026 setup heal receipts (unworn, full
health) the saved player matched the original part by part, a stump at 5
included (**Observed**); spawned members of two races showed the same value set
on both engines, but not as the same characters. Wear, prosthetics, robots, and
multiplier or scale changes after load are **Unknown**. The capture changes no simulation state or state hash
(**Verified**, `OracleStateTests` in the patch).
See [Meitou configuration and limits](meitou-target.md).

<a id="extension-additive-03"></a>

## Additive extension 0.3

Versions 0.1 and 0.2 are unchanged byte for byte: every accepted 0.2 snapshot
stays valid. Version 0.3 is 0.2 plus **two required character fields**;
changing only `schema_version` is rejected, and a 0.2 snapshot cannot carry
them. The runner selects the highest version that both it and the probe
advertise (0.3, then 0.2, then 0.1); `state_schema` requests one version
exactly and never falls back. The comparator refuses two campaigns with
different state schema versions, and a campaign whose snapshots differ from
its recorded `state_schema` or from each other. The Meitou target requests
0.3 unless its configuration says otherwise.

| Added field | Native source and Meitou projection | Certainty and limits |
| --- | --- | --- |
| `characters[].slave_state` | Native: `Character.h:217`, member `Character::stateBroadcast` (offset 0x1A0); when it is non-null, `StateBroadcastData.h`, member `StateBroadcastData::_slaveState` (offset 0x0), named after `Enums.h:269` `SlaveStateEnum`: `NOT_SLAVE` `not_slave`, `IS_SLAVE` `slave`, `ESCAPING_SLAVE` `escaping_slave`, `EX_SLAVE` `ex_slave`. Member reads only, no engine function is called. Meitou: `CharacterCold.SlaveState` 0, 1, 2 as `not_slave`, `slave`, `escaping_slave`. | API **Verified** from the headers; the three member offsets are checked at compile time against the same headers, not against the game binary. Native values were read live in one load-and-hold on a slave-start save (five repetitions per engine): at load both engines report the saved escaping state (`escaping_slave`, saved `slavestate` 2) of the two player characters (**Observed**); the engines then differ, the original turning them `not_slave` within 120 s while MeitouClient keeps `escaping_slave` (**Observed**). Other values and their equivalence with the saved value stay **Unknown**. `null` when `stateBroadcast` is null or the raw value is outside 0 to 3; `null` never means `not_slave`. MeitouClient loads a saved 3 as 0 (`SlaveSave.cs`, **Verified** in its code), so it never emits `ex_slave`; a character the original reports as an ex-slave would compare as `ex_slave` against `not_slave`. |
| `characters[].slave_owner_faction_id` | Native: `StateBroadcastData::isSlaveOf` (`Faction*`, offset 0xE0); when it is non-null and is one of the faction pointers met while capturing the same snapshot (found by pointer comparison before any dereference; two pointers sharing an id are both kept), `Faction::getData()->stringID`, exactly as `factions[].id`. Meitou: `SlaveOwner >= 0` gives `PopulationData.Factions[SlaveOwner].Id`, otherwise `null`. | API **Verified**. In the same slave-start hold, both engines report `null` at load for the two escaping player characters (**Observed**); other values **Unknown**. Same `GameData::stringID` namespace as `factions[].id`. `null` means that no owner faction is readable; it does not prove that the character has no owner. An owner pointer outside the captured factions also gives `null` (not observed). When MeitouClient loads an original save it ignores the original's `slaver` handle (`SlaveSave.cs`, **Verified** in its code), so such a slave has no owner (`null`) on MeitouClient at the patch series' pinned base. Upstream MeitouClient reads the handle and takes the owner's faction once the owner is in the world ([MeitouClient#256](https://github.com/VlcekM/MeitouClient/pull/256), merged after the pinned base). At run time the original fills `isSlaveOf` for loaded slaves: in the 0.5 live check its census showed an owner faction for 12 of the 32 Rebirth slaves at load and for all 32 by 198 s (**Observed**, N = 1). |

Read safety: the fields are read under the same guard as the other character
fields (ready paused world, command service, captured census). Whether
`stateBroadcast` can be null or stale for a loaded character is **Unknown**
until a live read and the usual read-safety review.

**Not covered** (**Unknown**, no field): shackles worn or locked, cage or
prisoner use (`inWhat`; `inSomething` is `in_something` since
[0.4](#extension-additive-04)), and `Character::isChained`, whose
meaning is not proven equivalent to MeitouClient's worn-shackle test. Neither
are `StateBroadcastData::isEscapedPrisoner`, `isKidnapped` or the time of the
last slave-state change.

Comparison: in a 0.3 comparison, the two fields of each saved character are
individual metrics (`/characters/<id>/slave_state` and
`/characters/<id>/slave_owner_faction_id`) classified like the other character
fields, and in a scene scope they join the player's outcome fields. A `null`
in any repetition makes the metric not comparable; it never matches
`not_slave`. A 0.2 comparison gains no metric.

The Meitou projection is patch 0006 of the
[Meitou series](../integrations/meitou/README.md): `CharacterCold.SlaveState`
0, 1, 2 give `not_slave`, `slave`, `escaping_slave`, and `SlaveOwner` gives the
owner faction's id (**Verified** in code and in the adapter's tests). An adapter
built from patches 0001 to 0005 does not produce 0.3, and a Meitou target on it
needs `state_schema:"0.2"` in both targets' configurations. Three 0.3
[canonical vectors](../schema/canonical-vectors.json) (65 cases in all, the
earlier 62 unchanged) pass in Python and in patch 0006's C# test (**Verified**).

<a id="extension-additive-04"></a>

## Additive extension 0.4

Versions 0.1, 0.2 and 0.3 are unchanged byte for byte, on both producers:
every accepted 0.3 snapshot stays valid, and a producer with 0.4 writes the
same 0.1 to 0.3 bytes as before (the Meitou `order` included). Version 0.4
([state-0.4.schema.json](../schema/state-0.4.schema.json)) is 0.3 plus **six
required character fields, three required keys in every health part and one
required squad field**. Changing only `schema_version` is rejected, and a 0.3
snapshot cannot carry any of them. Producers with 0.4 advertise `0.1` to `0.4`
and default to `0.4`; the runner selects the highest common version (0.4, then
0.3, 0.2, 0.1), `state_schema` is honoured exactly, and the Meitou target
requests 0.4 unless its configuration says otherwise. Unknown is `null`, never
0, `false`, `"nothing"` or an empty object; numbers follow the shared rule
(finite, magnitude at most 1e9, otherwise `null`; quantization unchanged).

One paused run per engine on one save backs the load values below
(**Observed**, N = 1 per engine): `oracle-base-cage-blesse`, the owner's local
save with caged slaves and an injured caged prisoner (local evidence, not
distributed). The snapshot taken at load was compared with the save for 54
saved characters and 22 squads on the original, 128 and 44 on MeitouClient.
Every 0.4 field that has a save key equalled the saved value at load on both
engines (relative tolerance 1e-4), with one exception: one native bandage was
0.5 % below its saved value, a change during the load frames rather than a
misread (the other 377 native bandages matched). These are field checks, not
behaviour statistics: the interface checks were not made, and the fields
without a save key or without a case in this save stay **Unknown** (see the
list after the table). "API **Verified**" means the member exists at that
offset in the public SDK headers read for this contract; it does not prove what
the game stores there at run time.

| Added field | Native source and Meitou projection | Certainty and limits |
| --- | --- | --- |
| `characters[].medical` | Native: `Character::medical`, an embedded `MedicalSystem` at 0x458 (`Character.h:711`), member reads only. Meitou: `Bodies/MedicalState.cs`. | API **Verified**; values per key below. An object with all six keys below, or `null` when the medical system is unavailable; never `{}`. |
| `medical.blood` | Native `MedicalSystem::blood` (0x70). Meitou `Blood`. Save key `blood`. | Number or `null`; equal to the save at load on both engines (**Observed**, above); against the interface's blood panel **Unknown** (live check 1). |
| `medical.bleed_rate` | Native `currentBleedRate` (0x78). Meitou `Bleeding`. Save key `bleeding`. | Number or `null`; equal to the save at load on both engines (**Observed**). A nonzero rate was seen on MeitouClient only, on a character outside the native census, so a nonzero native rate, and that both name the same rate (not a cumulative loss), are **Unknown** (live check 1). |
| `medical.hunger` | Native `hunger` (0x60). Meitou `Hunger` (0 to 3). Save key `hung`. | Number or `null`; equal to the save at load on both engines, so both read the saved scale (**Observed**); against the interface **Unknown** (live check 1). |
| `medical.fed` | Native `fed` (0x64). Meitou `Fed`. Save key `fed`. | Number or `null`; equal to the save at load on both engines (**Observed**); against the interface **Unknown** (live check 1). |
| `medical.coma` | Native `sub50KO` (0x162). Meitou `Coma` (Meitou docs: +0x162, save `coma`). | Boolean or `null`; `false` means known false. Equal to the save at load on both engines (**Observed**). `true` was seen on MeitouClient only, on a knocked-out character outside the native census; a native `true` is **Unknown** (live check 2). |
| `medical.blood_loss_trauma` | Native `bloodlossTrauma` (0x163). Meitou `BloodKo` (Meitou docs: +0x163); no save key. | Boolean or `null`; no save key, so not compared at load. `true` was seen on MeitouClient only (the same knocked-out character); native values are **Unknown** (live check 2). |
| `characters[].health[].bandage`, `splint`, `wear` | Native `MedicalSystem::HealthPartStatus` members `bandaging` (0x48), `juryRigging` (0x4C), `wearDamage` (0x50) (`MedicalSystem.h:169-171`). Meitou `HealthPart.Bandage`, `Rig`, `Wear`. | API **Verified**; equal to the saved values at load on both engines, except the one native bandage noted above (**Observed**). On the original, the bandage of the injured prisoner rose while medics treated him, up to the part's maximum minus its current health (**Observed**). Number or `null`, never 0 for unknown. `health` keeps its 0.1 rules (`null` when unavailable), and `maximum` is unchanged: whether the native stored `_maxHealth` and Meitou's calculated `MaxHp` mean the same thing stays an open question. |
| `characters[].stats` | Native: `Character::stats` (0x450, a pointer) to `CharStats`; the 34 stored members listed in the schema (for example `_strength` 0x80, `katanas` 0xF8, `unarmed` 0x10C as `martialarts`, `bows` 0x110 as `crossbows`). Meitou: `CharacterStats[StatsEnumerated.X]`. Keys are the KenshiLib `StatsEnumerated` names without `STAT_`, in lower case. | API **Verified**: the native offsets match the stat table in the Meitou documentation ([character stats](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/character-stats.md), "The stat list"), read on both sides. All 34 values equal to the save at load on both engines (**Observed**); against the character screen **Unknown** (live check 4). Exactly 34 keys, each the stored value (no multiplier, no effective-stat formula) or `null`; the object is `null` when the character has no stats object, never `{}`. Excluded: `hivemedic` and `vet` (stored as `medic`), `weapons` and `survival` (no storage behind the stat number in Meitou's reading of the accessor; the native `survival` member is not emitted). |
| `characters[].in_something` | Native `Character::inSomething` (0x2F8), `UseStuffState`: `IN_NOTHING` `nothing`, `IN_BED` `bed`, `IN_PRISON` `prison`; any other raw value is `null`. Meitou `CharacterCold.InSomething` (`Locks.HeldState`: `None`, `Bed`, `Imprisoned`). | API **Verified**; equal to the save at load on both engines, caged prisoners (`prison`) and saved sleepers (`bed`) included (**Observed**). `null` never means `nothing`. |
| `characters[].carrying`, `carrying_id` | Native: `isCarryingSomething` (0x348) false gives `nothing`. True with `carryingObject` (hand, 0x380) of character type gives `character`, and `carrying_id` is that handle encoded and canonicalized exactly like `order.target_id` (a reference without a proven link keeps its current HAND); true with another non-null hand gives `other`; true with a null hand gives `null`. Meitou: `CharacterCold.Carrying` `None` gives `nothing`, otherwise `character` with the carried character's id; Meitou never emits `other`. | API **Verified**; equal to the save at load on both engines (**Observed**), but nobody carried anything in this save, so only `nothing` was seen: the `character` and `other` values and the type of the native `carryingObject` while carrying a body are **Unknown** (live check 6). The schema enforces that `carrying_id` is a string exactly when `carrying` is `character`. Because Meitou never emits `other`, an original `other` never matches a Meitou value. |
| `characters[].being_carried` | Native `_isBeingCarried` (0x3D4). Meitou `CharacterCold.CarriedBy != CharacterId.None`. | Boolean or `null`; no save key, and nobody was carried in this save: values **Unknown** (live check 6). |
| `squads[].money` | Native `Platoon::ownerships` (0x148, `Platoon.h:203`) to `Ownerships::money` (0x88, `Platoon.h:93`). Meitou `Squad.Money`. Same squad rows as 0.3. | API **Verified**; equal to the save at load on both engines (**Observed**); against a trader's trade window **Unknown** (live check 7). Integer or `null`, magnitude at most 1e9; `null` never means 0. |

Meitou `order` in 0.4 output only (no schema change): MeitouClient's 0.4
adapter emits an order from its running task, named by row number through a
copy of the native task-name table (never a C# enum name), with `target_id`
the canonical id of a target character present in the census and `position`
always `null`; Task_Blank goal rows give `null`. Its 0.1 to 0.3 output keeps
`order:null`. Every task the Meitou AI chooses (`TaskSource.Goal`), not only an
attack, records its goal's row, while the native order is the body's current
action, a step of the goal's plan; so the two differ by design for AI-driven
characters, and 0.4 `order` compares player orders and non-blank goal rows
only. In one paused run per engine on one save (`oracle-base-cage-blesse`, a
local save with caged slaves; local evidence, not published), Meitou named an
order for 324 of 2338 character checkpoints and the original for 1933
(**Observed**). In 0.5 output, a goal's task gives its carried plan step
instead ([0.5](#extension-additive-05)); live check 8 is covered there by G4.
Player orders (a move, a treatment, a fight) were not exercised, so their
agreement stays **Unknown**.

Live checks still needed (one paused native session, then the Meitou
counterpart; the save comparisons of checks 1 to 5 and 7 are covered above,
and check 8 by G4 in [0.5](#extension-additive-05)): (1) blood, hunger, fed and
bleed rate against the interface, and a nonzero native bleed rate; (2) native
`coma` and `blood_loss_trauma` on a knocked-out character inside the native
census; (4) the 34 stats against the character screen; (6) carrying a body
(type of `carryingObject`, `_isBeingCarried`), which needs a save where one
character carries another; (7) squad money against a trader's trade window.

Comparison: in a 0.4 comparison, each saved character gains the individual
metrics `medical/<key>` (six) and `stats/<key>` (34), emitted for every key
even when the object is `null`, plus `in_something`, `carrying`,
`carrying_id` (through the same reference handling as `order/target_id`: a
proven saved HAND or a setup alias label, otherwise `null`) and
`being_carried`; each health part gains `bandage`, `splint` and `wear` next to
`current`, `stun` and `maximum`. Each squad with a producer-proven saved
identity gains `/squads/<id>/money`. In a scene scope the player's new fields
join its outcome fields, other saved characters and squads are background
metrics, and setup alias squads get no money metric. A `null` in any
repetition makes the metric not comparable: it is never a divergence and never
matches 0, `false` or `nothing`. A 0.2 or 0.3 comparison gains no metric, and
the comparator refuses a 0.3 campaign against a 0.4 campaign.

Four 0.4 [canonical vectors](../schema/canonical-vectors.json) (every field
filled, a permutation, nulls with `other` and `nothing`, and range edges; 69
cases in all at 0.4, the earlier 65 unchanged) pass in Python and in patch
0007's C# test (**Verified**); the five [0.5 cases](#extension-additive-05)
bring the file to 74. The Meitou projection is patch 0007 of the
[Meitou series](../integrations/meitou/README.md) (**Verified** in code and in
the adapter's tests, which also pin the unchanged 0.1 to 0.3 bytes and the
unchanged state hash). One projection difference is by construction: a carried
character outside the Meitou census gives `carrying` and `carrying_id` `null`
there, while the native probe still reports `character` with the current HAND.
An adapter without patch 0007 does not produce 0.4 and needs
`state_schema:"0.3"` in both targets' configurations. The native probe with 0.4
builds with every offset check above (**Verified** at compile time) and ran in
game for the paused run above (**Observed**: no crash, 20 valid 0.4 snapshots
per engine).

<a id="extension-additive-05"></a>

## Additive extension 0.5

Versions 0.1 to 0.4 are unchanged byte for byte, on both producers: every
accepted 0.4 snapshot stays valid, and a producer with 0.5 writes the same 0.1
to 0.4 bytes as before (the Meitou `order` included). Version 0.5
([state-0.5.schema.json](../schema/state-0.5.schema.json)) is 0.4 plus **one
required character field**, `goal`. Changing only `schema_version` is
rejected, and a 0.4 snapshot cannot carry it. Producers with 0.5 advertise
`0.1` to `0.5` and default to `0.5`; the runner selects the highest common
version (0.5, then 0.4, 0.3, 0.2, 0.1), `state_schema` is honoured exactly, and
the Meitou target requests 0.5 unless its configuration says otherwise.

`goal` is `null` or an object with exactly `type`, `priority` and `target_id`.
`null` means unknown **or** no current goal: Meitou cannot tell "no goal" from
"not thought yet", and what an empty native `TaskMatch` means is **Unknown**,
so "no goal" is never a value. The field exists because the engines' `order`
values do not mean the same thing for AI-driven characters (see the Meitou
`order` paragraph of [0.4](#extension-additive-04)): the goal compares the AI
decision itself, which goal at which tier.

One paused run per engine on the save of [0.4](#extension-additive-04)
(`oracle-base-cage-blesse`, a hold of 20 snapshots) backs the results listed
after the table (**Observed**, N = 1 per engine): field checks, not behaviour
statistics. "API **Verified**" means the member
exists at that offset in the public SDK headers read for this contract (the
native offsets and sizes are checked at compile time against those headers,
not against the game binary); it does not prove what the game stores there at
run time.

| Added field | Native source and Meitou projection | Certainty and limits |
| --- | --- | --- |
| `characters[].goal` | Native: `Character::ai` (0x650, `Character.h:720`, `AI*`) to `AI::taskSystemAI` (0x20, `AI/AI.h:115`, `AITaskSytem*`) to `currentGoal` (0x1C0, a `TaskMatch` of length 0x48) and `currentGoalPriority` (0x20C) of `OrdersReceiver`, the base of `AITaskSytem` at offset 0 (`AI/AITaskSystem.h:179`, `:181`, `:194`). Member reads only: `TaskMatch::key()`, `getCurrentGoal()` and `getAI()` are not called. Meitou: `CharacterCold.Ai.Goal` (`AiMind`); since patch 9, while the character works a captive job, the goal that job runs (`CaptiveJob.Goal`) instead. | API **Verified**; values **Observed** (G1 below). Native `null`: `ai`, `taskSystemAI` or `taskData` null, a key outside 0 to 290, `NULL_TASK`, a row without a name, or a dead character, whose AI is not read (whether its pointer stays valid after death is **Unknown**). Meitou `null`: no mind (`cold.Ai` null: player squads, which `AiSystem` does not attach, and characters without a mind), no goal yet (`mind.Goal` null before the first think, so right after a load), or a row without a native name. Meitou does not null a dead character's goal while the native probe does; a `null` on one side is never a divergence. An engine-routine Meitou mind (`AiMind.Engine`) still emits its combat and self-preservation goals like any goal. |
| `goal.type` | Native `TaskMatch::taskData` (0x0, `AI/AITaskSystem.h:31`, `const TaskData*`) to `TaskData::key` (0x44, `Tasker.h:94`, `TaskType`), named by row number through the shared table ([OracleTaskNames.h](../plugin/OracleTaskNames.h)). Meitou: `mind.Goal.Task.Type` by row number through the adapter's copy `OracleTaskNames.cs`, never the C# enum spelling. | Constrained like `order.type`. Task_Blank rows (for example `wander_town` or `idle`) are **included**: they are goals, unlike in the 0.4 Meitou `order`. Values **Observed** (G1 below). |
| `goal.priority` | Native `currentGoalPriority`, `taskPriority` (`AI/AITaskSystem.h:87-95`): `TP_JUST_ACTION` 0 `just_action`, `TP_FLUFF` 1 `fluff`, `TP_NON_URGENT` 2 `non_urgent`, `TP_URGENT` 3 `urgent`, `TP_OBEDIENCE` 4 `obedience`. Meitou `mind.Goal.Task.Priority`, `TaskPriority` (`JustAction` 0, `Fluff` 1, `NonUrgent` 2, `Urgent` 3, `Obedience` 4, `Meitou.Data/Gameplay/Ai/AiData.cs:6`), with the same names. | The two enums number alike: **Verified** by reading both. They are not proven to hold the same quantity: native stores the tier passed when the goal was set, Meitou keeps the AI_TASK record's `classification` of the chosen goal (its think goes tier by tier). Agreement and whether a goal keeps its tier: **Observed** (G2 below). Any other raw value gives `priority: null` and keeps the other keys. |
| `goal.target_id` | Native `TaskMatch::subject` (0x8, `AI/AITaskSystem.h:40`, `hand`), encoded and canonicalized exactly like `order.target_id`; an empty hand gives `null`. Meitou: always `null`. `AiGoal` has no target; `FollowTarget`, `FightTarget` and `AssaultTarget` are act-out targets, and the last two are cleared within the tick, so mapping them would be a guess. | Native hand types **Observed** (G3 below): none, building and character; no node was seen. Because Meitou always emits `null`, `goal/target_id` is never comparable between the two engines. |

Save: no save key. The saved orders record (type 67, linked to every character
instance) holds only `jobs` and the permanent jobs (`pjob0`, `pjobT0*`):
**Verified** on `oracle-base-cage-blesse` (128 characters, read from a
hashed scratch copy; the save was not changed). So the goal cannot be checked
against the save: at load the native goal is whatever the game rebuilt, and the
Meitou goal is `null` until its first think.

Meitou `order` in 0.5 output only (no schema change; patch 0008): the 0.4 rule
holds except for one case. When the character's task provenance
(`CharacterCold.Running`) is a goal's task (`TaskSource.Goal`) that runs the
character's task now, and the mind's first plan step (`AiMind.Step`) is not
none, differs from the goal's row, is a step the engine carries out
(`AiSystem.Carried`) and has a native name, then `order.type` is that step's
name and `target_id` and `position` are `null` (the plan target is a place, not
a character). The carried steps are `move_on_free_will` (and `_fast`),
`travel_to_target_town` (and `_fast`), `stand_at_node`, `buy_shit`, `use_bed`,
`use_bed_order`, `use_turret`, `operate_machinery`,
`pretend_to_operate_machinery`, `equip_weapon`, `unequip_weapon`,
`equip_crossbow`, the three `get_out_of_bed` rows, `go_homebuilding`,
`get_near_to`, `enter_building` and `leave_building`. A player order is
unchanged. The intended effect is that native `move_on_free_will`,
`stand_at_node`, `use_bed`, `operate_machinery` and `buy_shit` become
comparable: they were 1618 of the 1933 native orders in the 0.4 run above, for
characters present on both engines (**Observed**). Whether Meitou's first plan
step is the step the original body runs at the same moment: **Observed** in
part (G4 below).

Live check results (**Observed**, N = 1 per engine, 2338 character checkpoint
pairs present on both engines; the save has no goal key, so nothing is checked
against the save):

- **G1 goals.** Both goals are non-null in 1773 pairs and their types agree in
  778 (43.9 %). Null: native 364, Meitou 359, both 158. At load the native
  probe reported a goal for 2 of the 54 common characters and Meitou for none
  (expected before its first think), so the original also rebuilds goals after
  a load. A native `null` goal during part of the sleep time was seen; what it
  means is **Unknown**.
- **G2 priority.** When the goal types are equal, the priorities are equal in
  778 of 778 (all `non_urgent`). The native probe reported `urgent` 40 times.
  On neither engine did a character change tier while keeping the same goal
  type.
- **G3 native targets.** Of 1974 native goals: no target 1860, `BUILDING` 87,
  `CHARACTER` 27. Every character target is in the census, and 24 of them are
  the character itself. Meitou: none, by contract.
- **G4 orders.** On the same save, Meitou's non-null orders went from 324 in
  the 0.4 run to 919 in the 0.5 run, and orders of equal type from 70 to 371
  (two separate runs). 770 Meitou orders were carried plan steps, of which 301
  equal the native order (`move_on_free_will` 268, `stand_at_node` 33).
- **G5 player.** Neither the state nor the save marks the player. The two
  candidates (the members of the save's player faction) are both slaves in
  this save; the native probe reports goals for them, Meitou `null` (its AI
  does not run player squads). The identification stays **Unknown**.
- **Dead rule.** No native character died in the census, so the native `null`
  goal of a dead character is unchecked. On Meitou a dead character kept its
  goal, which the contract allows.

Where the goal types differ, both producers still emit the field as the
contract describes; the differences are questions about MeitouClient's
behaviour, not oracle defects. Most have since been traced to MeitouClient
defects, fixed or proposed upstream; see the
[MeitouClient findings](meitou-findings.md). One was a projection gap of the
adapter: MeitouClient runs captive work (gathering slaves, working them) as
jobs outside the AI's goal, which patch 0008 could not report. Patch 0009
reports the goal a running job runs; in one hold its slavers read
`gather_slaves_from_cages` and `work_the_slaves` as the original's do
(**Observed**, N = 1; counts in the findings).

Comparison: in a 0.5 comparison, each saved character gains the individual
metrics `goal/type`, `goal/priority` and `goal/target_id` (through the same
reference handling as `order/target_id`: a proven saved HAND or a setup alias
label, otherwise `null`). A `null` goal gives three `null` values. In a scene
scope the player's goal joins its outcome fields and other saved characters'
goals are background metrics. A `null` in any repetition makes the metric not
comparable: it is never a divergence. Triage rule 7 merges a goal difference
across the members of a squad into one field group
(`/characters/*/goal/type`). A 0.2 to 0.4 comparison gains no metric, and the
comparator refuses a 0.4 campaign against a 0.5 campaign.

Five 0.5 [canonical vectors](../schema/canonical-vectors.json) (two goals, one
with a target and one a Task_Blank row; a permutation; `just_action` and
`non_urgent`; `obedience` and a `null` priority; a `null` goal: 74 cases in
all, the earlier 69 unchanged, fixture identity
`99f4bfee37ee2c953c7dc34954d8d525e5f116564dcfda11c67bb2ab0f8c1484`) pass in
Python and in patch 0008's C# test (**Verified**). The Meitou projection is
patch 0008 of the [Meitou series](../integrations/meitou/README.md)
(**Verified** in code and in the adapter's tests, which also pin the unchanged
0.1 to 0.4 bytes). An adapter without patch 0008 does not produce 0.5 and needs
`state_schema:"0.4"` in both targets' configurations. The native goal logic is
tested on fake objects and its offsets are checked at compile time against the
SDK headers (**Verified**); the probe with 0.5 ran in game for the run above
(**Observed**: no crash, 20 valid 0.5 snapshots per engine, and the 0.4 load
values repeated the 0.4 run's result, the same native bandage included).

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
