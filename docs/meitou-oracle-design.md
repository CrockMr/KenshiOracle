<a id="adaptateur-oracle--fork-durable-et-possibilité-de-mod"></a>

# Oracle adapter: durable fork and possible mod

The public [adapter patch series](../integrations/meitou/README.md) pins the
upstream base, includes source checksums and licensing, and documents
application, build/test checks and updates. It reproduces the locally
validated fork without requiring access to a private checkout.

Design approved on October 29, 2026, before implementation. The examined clone is
`1df44934efd32c49998e7f3aa75d877fb499459a`; modding documentation was also reread
on the current `master`. It is still marked as an undecided, unimplemented
concept. Component names below are proposals for our adapter, not APIs present
in MeitouClient. The current integration target is upstream
`88ae71a1eeb65bc7081751f19763f032093b2621` (see the [patch series](../integrations/meitou/README.md)); the source links
below still document the examined commit.

The [Meitou target guide](meitou-target.md) describes the contract now implemented
in the local fork and its limited evidence; the proposed components below remain
a separation design, not a list of public APIs.

<a id="diff-limité-exploitable-sans-fusion-upstream"></a>

## Small diff, usable without an upstream merge

The adapter must live durably on our local `oracle-adapter` branch,
without depending on a merge into MeitouClient. No push, issue, PR or contact
with the team is authorized by this scope.

Phase 2 proceeds in order: [RE_Kenshi deviations](rekenshi-deviations.md),
an additive state contract shared by both producers, then adapter and
comparator. An accepted schema alone does not prove a real capture.

- Group JSON/TCP transport, protocol and canonicalization into isolated Oracle
  files; their logic must remain independent of the game interface.
- Separate projection of simulation data and saved HANDs from the connection
  to host controls.
- Prefer a small `GameHost.Oracle.cs` partial file to connect existing loading,
  clocks, pause/speed, camera and seed methods, with only indispensable
  activation/service/shutdown points in upstream files. Do not copy simulation
  composition into a second engine or reorganize the engine for the oracle.
- Activate only with `--oracle`, listening on `127.0.0.1:47801` by default.
  Without this option, no server or Oracle activity.
- The network queues; the host processes at a safe boundary, including while
  paused, without world access during tick-ahead. The server belongs to the
  host/process; every world replacement invalidates operations and identities
  without destroying the server with the old world.

<a id="six-composants-proposés"></a>

## Six proposed components

These names designate files/classes in our module, not existing interfaces or
a plugin framework to add to the engine.

| Component | Responsibility and limit |
| --- | --- |
| `OracleServer` | Bounded loopback TCP, JSON request/response queue and published heartbeat; no world access from the network. |
| `OracleProtocol` | Envelopes, parameter validation, errors and advertised capabilities. |
| `OracleController` | Dispatch, advances with identity/status/cancellation, instance/epoch and provenance; no persistent reference to an old world. |
| `OracleState` | Projection of loaded entities and their proven saved HANDs; copy at a safe boundary. |
| `OracleCanonicalJson` | Sorting, rounding and UTF-8 independent of the game interface. |
| `GameHost.Oracle.cs` | Small partial file connecting existing services: loading, clocks, controls, camera, seed and session end. |

Prefer this module to a new host recomposing simulation. The only required
upstream points are activation, safe servicing and shutdown; any scheduler
extension must be motivated by the timing contract, not hidden in state
projection. Service after a batch of ticks can overshoot a target: retain
requested time, actual time and overshoot without claiming an exact-tick stop.
Tick-ahead must be joined and reconciled with the clock before any coherent
world read.

The eight priority commands alone are insufficient for the current runner:
it also needs its heartbeat, advance status/cancellation and control
restoration, or an explicit adaptation of its capabilities preserving the
same guarantees. Do not advertise scenario compatibility by merely returning
`not_implemented` for their recovery operations.

Priority commands are `ping`, `get_clock`, `dump_state`, `pause`,
`set_game_speed`, `run_until`, `load_save`, `issue_order`. The runner also uses
`heartbeat`, `run_until_status`, `cancel_run_until`, `get_scene_state`,
`set_camera_free`, `prepare_scene_control` and `commit_scene_control`.
Saved origins must be prepared through an explicit capability; a current
identity must not be presented as a proven origin.

**Units and seed:** the shared clock uses absolute calendar seconds
(`Clock.TotalHours * 3600`), not `GameClock.GameSeconds` since loading.
Loading can restore `meitou seed` from CAMERA and replace `--seed`.
Imposing a seed per repetition requires a point before the first draws,
then recording the effective seed. Asynchronous game services do not become
deterministic merely because the seed is known.

<a id="identité-des-villes--distinction-à-préserver"></a>

## Town identities: distinction to preserve

**Verified in Meitou sources:** `TownSite.InstanceId` comes from the level-data
placement ID, distinct from `TownId`, which designates the `TOWN` record.
`PopulationData.Create` retains these two identities separately; `SaveLoader`
matches saved state and site using this placement ID, then establishes the
mapping to the saved HAND. Neither site index nor town name is a proven
shared key.

**Verified in the public SDK:** `Town` exposes `InstanceID instanceID`, and
`InstanceID` exposes the `uid` string, with a constructor taking a
`GameData::ObjectInstance`. `TownList` distinguishes `getTown(instanceID)`
and `getTownBySID`. These declarations make `Town::instanceID.uid` a relevant
placement-identity candidate. `getOriginalGameData()->stringID` designates
another layer, the definition record; it must not substitute for a placement ID.

**Unknown before real cross-checking:** headers do not show assignment of
`Town::instanceID` from level data. Reading them alone therefore does not
prove equality with `TownSite.InstanceId`. Planned validation must read the
native candidate, its original record and position, then require an exact,
unique match in `WorldLevelData.Towns()` using the same data and mod order.
Then check stability after reloading; overridden towns, nests and outposts
require separate scope evidence. Required local data is not published in
the repository.

Until that evidence exists, retain `current_town_id=null` and
`town_assignment=null` for this producer. A current HAND, name, geographic
proximity or invented index does not justify an `inside` assignment.
Faction groups can proceed independently; town groups remain non-comparable
until their keys are established.

<a id="procédure-de-mise-à-jour-prévue"></a>

## Planned update procedure

1. Keep an `upstream` remote pointing to MeitouClient, a clean upstream
   reference and Oracle changes in small commits separate from engine fixes.
   Record the validated upstream revision.
2. With measurement stopped, verify a clean tree and create a local backup
   branch of `oracle-adapter` before any update.
3. Fetch `upstream/master`, then rebase `oracle-adapter` onto it. No rewriting
   or silent update of a campaign already started.
4. Inspect the remaining diff and conflicts, especially the limited host
   seams, clock units, HANDs, seed application on load and options affecting
   simulation.
5. Revalidate build, functional/canonicalization tests and protocol
   compatibility. Confirm no effect without `--oracle`. Exclude benchmark
   tests from this phase; no new performance campaign.
6. Repeat necessary functional checks in quiet-town, travel, battle order,
   with restoration. Update the validated upstream revision and record it in
   every repetition's provenance.

Updating is an explicit operation, never a task changing a running campaign.
Fork paths and validation results are local; provenance retains upstream
and Oracle commits. No publication remote is needed to maintain this branch.
The procedure will be refined when the fork is created and does not depend
on agreement to merge upstream.

<a id="un-futur-mod-c-pourrait-il-remplacer-le-patch-"></a>

## Could a future C# mod replace the patch?

**Verified in current documentation:** `docs/modding.md` describes only a
concept. `meitou.json`, `IMod.Initialize(ModContext)`, the `Meitou.Modding`
assembly and registration points are not an available API. The model
proposes simulation systems, a `SimCommand` queue and loading through assembly
contexts, but no initial UI/rendering hook.

**Inferred possibility:** transport, canonical encoding, world projection
at safe ticks and some orders could be reused in a mod if this surface is
implemented. The oracle needs no rendering hook to compare states, so lack
of rendering is not the central blocker.

**Concrete limits of the concept for a complete oracle:**

- Pause: no simulation tick executes; current paused-command handling filters
  command types and permitted systems. An arbitrary Oracle system would not
  automatically be serviced. Reading, resuming and observing a paused game
  must be possible without artificially advancing it.
- Host controls: the proposed mod context does not define access to
  `WorldSession`, loading with status, the clock, camera or a seed imposed
  before the first draws. The oracle needs these.
- Lifecycle: `ReplaceWorld` disposes systems in the old world; a clear contract
  is needed for world replacement, session start/end and resources that live
  longer than one world, notably the socket. The concept loads assemblies
  once at startup but places `Initialize` in system composition: its exact
  per-world frequency remains to be specified before migration. A loaded
  assembly does not imply a system or socket survives disposal.
- Compatibility: the concept directly exposes simulation types and provides
  for compatibility per game version. Turning it into a mod would therefore
  not guarantee automatic compatibility with every new build.

**Design conclusion:** keep an isolated module in our fork today. Preparing
separation of its dependencies permits later migration to a mod, provided
the API supplies the necessary host controls and paused-service points.
Do not implement a fake mod loader or present this migration as guaranteed.

## Sources

- [Modding concept at the examined commit](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/docs/modding.md).
- [WorldSession: clocks, tick-ahead, world replacement and disposal](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Engine/WorldSession.cs).
- [Commands serviced while paused](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Simulation/World.Interface.cs).
- [Host composition and loading](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Game/GameHost.Saving.cs).
- [Simulation and determinism](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/docs/simulation.md).
- [Seed restored on loading](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Simulation/Saving/SaveLoader.cs#L42-L53).
- [Town placements in level data](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Data/World/WorldLevelData.cs#L125-L145).
- [TownSite and identity preservation](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Simulation/PopulationData.cs#L76-L99).
- [Exact saved-town matching](https://github.com/VlcekM/MeitouClient/blob/1df44934efd32c49998e7f3aa75d877fb499459a/src/Meitou.Simulation/Saving/SaveLoader.cs#L114-L125).
- [Town::instanceID field in the public SDK](https://github.com/BFrizzleFoShizzle/KenshiLib_Examples_deps/blob/b566d74bf3d74629cc2fb632a97595b8202993f1/KenshiLib/Include/kenshi/Town.h#L444).
- [InstanceID type in the public SDK](https://github.com/BFrizzleFoShizzle/KenshiLib_Examples_deps/blob/b566d74bf3d74629cc2fb632a97595b8202993f1/KenshiLib/Include/kenshi/InstanceID.h#L6-L30).
