# MeitouClient Oracle patch series

This directory makes the Meitou adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the ten patches, in
order, to upstream MeitouClient commit
`9a19748be975fe7716aff90e3dcfd6691622e175` (master of 2026-11-12). They
correspond to the local fork tip
`38196fe197a74f600d59b3676ac43e73df98e5d6`; they are not an upstream release or
an endorsement from the MeitouClient team.
Earlier series targeted `1df44934efd32c49998e7f3aa75d877fb499459a` (the
recorded phase 2 campaigns), `08340c728c6b85a2b2d12df4211a60e170acb5ba`,
`100c6caec876cb1cdb4e3a404eed7e6d7b33eb54` and
`88ae71a1eeb65bc7081751f19763f032093b2621` (probe 0.12.0); the
[mod-free campaigns](../../docs/mod-free-campaigns.md) name the base of each run.

<a id="upstream-drift"></a>

## Upstream drift

The series is pinned and upstream moves fast: about 160 commits a day in
November 2026. As recorded in [series.json](series.json) (`upstream_review`):

- **Verified** on 2026-11-12: the series was rebased from `88ae71a1`, which
  lies 1761 commits before this base. On this base it applies, builds and
  passes its tests ([below](#apply-and-build)).
- **Verified** on 2026-11-12 (local mirror, fetched after the rebase): upstream
  `master` is `9a19748be975fe7716aff90e3dcfd6691622e175`, the base itself
  (0 commits after the base). It will not stay so for long.
- The holds reported in the [MeitouClient findings](../../docs/meitou-findings.md)
  after 2026-11-03 used private builds on
  `c09ed01c3d26eeb69433dbd6c69fae7dc71b554f`, which lies 437 commits before
  this base. A hold, a scene-setup campaign and a city run have run on this
  series ([below](#apply-and-build)); it does not include the private fixes
  those builds carried, so those figures are not reproduced from it.

What the rebase changed. Between the two bases upstream merged its `Engine`
project into `Game`, split the host into separate classes (`GameLoop`,
`GameSaves`, `SandboxScenario`), made the build enforce its naming rules and
renamed its enum members to PascalCase. `git am --3way` could not follow that,
so the series was rebuilt commit by commit: the adapter's own files were
carried over whole and brought to the new names, and each hook into an upstream
file was placed again at its new location. The command-line options moved into
the adapter's own `OracleOptions.cs`, so `GameOptions.cs`, where the previous
series conflicted, now carries one call each for parsing and checking. Patch 9
no longer changes MeitouClient ([below](#patch-9)).

| Order | Patch | Source commit |
| --- | --- | --- |
| 1 | [Exact camera restoration](0001-exact-camera-restoration.patch) | `0ee169c7e49a1cfa0802c2248ebea5909d366b55` |
| 2 | [Opt-in Oracle adapter](0002-opt-in-oracle-adapter.patch) | `5ea01a6b513b8ace142dbcf14a12fdd36fcd6496` |
| 3 | [Scene-setup simulation entry points](0003-scene-setup-simulation.patch) | `8bb9b58665f17493b57834163cbe5d2246d1d9c6` |
| 4 | [Scene-setup adapter commands](0004-scene-setup-adapter.patch) | `d1b261f62be56ad9110c25227e6dc9fcce731e9d` |
| 5 | [Calculated health maxima in the state dump](0005-calculated-health-maxima.patch) | `67ceefbf8a6f985ede982626416963bc27f39492` |
| 6 | [Slave state and owner faction in state 0.3](0006-slave-state-fields.patch) | `cd5645d5d9c1dd31b3744dc6c4c8c9522446eb21` |
| 7 | [State 0.4 fields and task-row orders](0007-state-04-fields-and-task-orders.patch) | `d389ab7141ab733877ff32c2243e586abd4276f5` |
| 8 | [State 0.5 goals and plan-step orders](0008-state-05-goals-and-plan-step-orders.patch) | `c99baeaa9c215283d654d8ad80b001bf0dd72938` |
| 9 | [Captive job goals in state 0.5: the check](0009-captive-job-goals.patch) | `eae4dda61c896ff7dcd192a8b92869b8e285977f` |
| 10 | [Adapter version 0.12.0](0010-adapter-version-0.12.0.patch) | `38196fe197a74f600d59b3676ac43e73df98e5d6` |

[series.json](series.json) records the exact SHA-256 and byte size of each patch.

Since the `88ae71a1` series, patch 2 declares the adapter version
as the constant `OracleProtocol.AdapterVersion` instead of a literal (still
`0.10.0` there). Patch 4 raises it to `0.11.0`, the version of the
[scene-setup contract](../../docs/scene-setup.md), and adds `build_commit` to
ping; patch 10 raises it to `0.12.0`, the release that adds states 0.3 to 0.5.
Evidence that reported `plugin_version` `0.10.0` from Meitou does not
identify one build; from this series on, a build is identified by
`build_commit`.

Patch 5 changes no protocol version. It fills `health[].maximum` with
MeitouClient's calculated `HealthPart.MaxHp` instead of `null` (still `null`
when negative, non-finite or above 1e9, as on the native probe); `order` stays
`null`. The value is calculated, not the original's stored `_maxHealth`. In the
1 November 2026 setup heal receipts (unworn, full health) the saved player
matched part by part on both engines in every repetition, including a stump at
5 (**Observed**). Spawned members of races `17-gamedata.quack` (100 per part)
and `5276-chareditor.mod` (125 per part) showed the same set of values on both
engines, but the race draw differs between engines, so this is not a
same-character comparison; whether 125 comes from base HP, multiplier or scale
is **Unknown**. Wear, prosthetics, robots, and multiplier or scale changes
after load are **Unknown**. See [state coverage](../../docs/state-coverage.md).

Patch 7 adds [state 0.4](../../docs/state-coverage.md#extension-additive-04)
and makes it the default dump schema; 0.1 to 0.3 output is unchanged, `order`
included (pinned by test). In 0.4, `order` is projected from the character's
task provenance (`CharacterCold.Running`) while it runs the current task, by
row number through a copy of the native probe's task names (KenshiLib
`TaskType` order, 291 rows; Meitou's own symbols differ at rows 0, 38, 52, 65,
223, 245, 289 and 290), never through the Meitou enum's spelling. Goal rows that
the original's task factory builds as `Task_Blank` (147 rows, from MeitouClient's
`docs/game/ai-tasks.md`) give `null`: the original's body reports the immediate
task under a goal, so an attack (Meitou row 16) is not expected to match the
original's immediate task. `position` stays `null`. In one paused run per
engine on one save, every 0.4 field with a save key equalled the save at load,
and every task the AI starts recorded its goal's row (`TaskSource.Goal`, not
only attacks), so Meitou named an order for 324 of 2338 character checkpoints
and the original for 1933, of equal type in 70 (**Observed**). Whether
player orders (a move, a treatment, a fight) match the original is **Unknown**:
none was given in that run.

Patch 8 adds [state 0.5](../../docs/state-coverage.md#extension-additive-05)
and makes it the default dump schema; 0.1 to 0.4 output is unchanged, `order`
included (pinned by test). In 0.5 each character gets `goal` from its mind's
current goal (`CharacterCold.Ai.Goal`): `type` is the goal row's native name by
row number, Task_Blank rows included (they are goals); `priority` is the
AI_TASK tier of the goal, `TaskPriority` 0 to 4 named `just_action`, `fluff`,
`non_urgent`, `urgent` and `obedience` (the native `taskPriority` numbering,
**Verified** by reading both enums), any other value `null`; `target_id` is
always `null` because `AiGoal` has no target. `goal` is `null` without a mind
(player squads), before the mind's first think (right after a load) and for a
row without a native name. Unlike the native probe, Meitou does not null the
goal of a dead character; `null` on one side is never a divergence. In 0.5
only, the order of a goal's task (`TaskSource.Goal`) is the mind's first plan
step (`AiMind.Step`) when that step is not none, differs from the goal's row,
is one of the steps the engine carries out (`AiSystem.Carried`, made public
for this) and has a native name; `target_id` and `position` are then `null`.
Every other case keeps the 0.4 rule. The patch carries the 74-case canonical
vector copy and its pin. In one paused run per engine on the same save
(**Observed**, N = 1), the goal types agreed in 778 of 1773 pairs where both
were non-null, the priorities were equal in all 778, and 301 of 770 carried
plan steps equalled the native order; see the
[state coverage](../../docs/state-coverage.md#extension-additive-05). Whether
Meitou's tier is the same quantity as the native stored goal priority in
general is **Unknown**. Most goal differences of that run came from MeitouClient
defects that later upstream changes address; this base contains those merged
by 2026-11-11; see the
[MeitouClient findings](../../docs/meitou-findings.md).

<a id="patch-9"></a>

Patch 9 is now a check, not a change to MeitouClient. MeitouClient runs captive
work (gathering slaves from cages, working them, getting into a cage, guarding
or processing prisoners) as `CaptiveSystem` jobs. On the earlier base the AI
held no worker of a job, so its mind kept the goal it had before, and this patch
recorded the job's goal on the job (`CaptiveJob.Goal`) for the adapter to read.
Upstream now gives the job's goal to the worker's mind when the job starts
(`AiSystem.TakeCaptiveGoal`, **Verified** by reading `CaptiveSystem.Start` on
this base), so the adapter reads the mind's goal alone, as patch 8 does, and
the `CaptiveJob.Goal` change is dropped. The patch keeps its two tests (the
worker's 0.5 goal is the job's goal while the job runs, and its mind's goal
again once the job is over) and the adapter's documentation. 0.1 to 0.4 output
and the 0.5 `order` are unchanged (pinned by test). In one hold on a private
build of the earlier port (**Observed**, N = 1), the slavers read
`gather_slaves_from_cages` and `work_the_slaves`, as the original's census does;
see the [MeitouClient findings](../../docs/meitou-findings.md). In the hold on
this base (**Observed**, N = 1) the slavers' goals were again
`work_the_slaves` and `gather_slaves_from_cages`; 21 of their pairs differ
from the original's by which of the two it is at that checkpoint.

## Apply and build

Use a separate checkout beside this KenshiOracle checkout. At this base
MeitouClient's `global.json` requires .NET SDK 11.0.100 with `latestFeature`
roll-forward (upstream moved to .NET 11 on 2026-11-11); the local validation
used SDK 11.0.100. Install the SDK separately if necessary.

For a new checkout:

```powershell
git clone https://github.com/VlcekM/MeitouClient.git MeitouClient
Set-Location MeitouClient
git switch -c oracle-adapter-9a19748b 9a19748be975fe7716aff90e3dcfd6691622e175
```

In an existing checkout of an earlier series, run `git fetch origin` and then the
same `git switch` line; your old branch stays as a backup. Then, in either case:

```powershell
$OracleRoot = (Resolve-Path ../KenshiOracle).Path
$Series = "$OracleRoot/integrations/meitou"
git -c core.autocrlf=false am -- "$Series/0001-exact-camera-restoration.patch" "$Series/0002-opt-in-oracle-adapter.patch" "$Series/0003-scene-setup-simulation.patch" "$Series/0004-scene-setup-adapter.patch" "$Series/0005-calculated-health-maxima.patch" "$Series/0006-slave-state-fields.patch" "$Series/0007-state-04-fields-and-task-orders.patch" "$Series/0008-state-05-goals-and-plan-step-orders.patch" "$Series/0009-captive-job-goals.patch" "$Series/0010-adapter-version-0.12.0.patch"
dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~Meitou.Tests.Engine.CameraTests|FullyQualifiedName~Meitou.Tests.Engine.OracleCameraRestoreTests"
```

Build from a clean Git checkout: `build_commit` is the full commit only when
`git status --porcelain` is empty at build time, otherwise `"unknown"`, which
the comparator refuses for campaigns.

**Verified** on 2026-11-12, at fork tip `38196fe1` on `9a19748b`, with SDK
11.0.100 on Windows:

- In a scratch checkout at upstream `9a19748b`, `git am` with
  `core.autocrlf=false` applied the ten patches cleanly and the resulting tree
  equalled the fork tip's tree `90257dc781e4f807a1cafb14c66ce7042771eb5a`
  (compared with `git rev-parse HEAD^{tree}`). This checks source
  reproduction, not a live campaign.
- The Release build of the game and of the test project had 0 warnings and 0
  errors. Upstream treats warnings as errors and its build checks its naming
  rules, so the adapter's private fields follow them.
- The focused Oracle and camera tests (the filter above) passed 190 of 190,
  and again 190 of 190 with `KENSHI_ORACLE_VECTORS` pointing at this
  repository's [canonical vectors](../../schema/canonical-vectors.json).
- The quick suite (`Category!=Slow&Category!=Bench`) had 827 passes, 0
  failures and 3 skipped.
- The same series was first rebuilt on
  `42205b61cd6211d2db7c391d2008acfbf2de0584`, 30 commits earlier and the last
  upstream commit that builds with SDK 10.0.403: 0 warnings and 0 errors, 190
  of 190 focused tests, 826 quick-suite passes and 0 failures there. Between
  the two, one hook had to be placed again (the follow camera, which upstream
  changed for a carried character). It was then replayed on `8ae1141a`
  (two commits before this base) and on this base without further change.

**Observed** on 2026-11-12, in the game, with a Release build of the fork tip
(one machine, local saves not distributed):

- Started without `--oracle` (build of `8ae1141a`, two commits earlier),
  MeitouClient ran for 45 s; nothing listened on port 47801, no oracle output
  folder was made and no oracle line was printed.
- Started with `--oracle` under the watchdog, `ping` reported
  `plugin_version` `0.12.0` and `build_commit`
  `38196fe197a74f600d59b3676ac43e73df98e5d6`.
- One paused hold on a slave-camp save (seed 0, no orders, 20 checkpoints from
  0 to 3960 s, state 0.5) completed through the shared runner: every snapshot
  validated and the controls were verifiably restored.
- Against one hold of the original on the same save
  ([agreement between runs](../../docs/agreement.md)), the goal types agreed
  in 1626 of 1907 pairs (85.3 %), and in 1626 of 1688 (96.3 %) with the
  save's three load-order classes set aside. The build of `8ae1141a` gave the
  same counts. The private build on `c09ed01c` read 1643 of 1698 (96.8 %) by
  the same count, and a second hold of the original 1768 of 1795 (98.5 %).
  One hold per build: the half point between the MeitouClient builds is not
  shown to be a difference.
- The scene-setup scenario [nature-bandit-ambush](../../scenarios/nature-bandit-ambush.json)
  completed three repetitions (seeds 0, 1 and 2): in each the setup block
  passed (six aliases resolved), the attack order and the pause were accepted,
  nine checkpoints were captured, and the controls were restored at the end.
  No campaign of the original was run beside it, so nothing is compared.
- The quick city run of the [maintenance guide](../../docs/maintenance.md)
  ([ville-calme](../../scenarios/ville-calme.json), seed 0, one repetition)
  completed and restored.
- The same hold ran five repetitions (seeds 0 to 4) beside five repetitions
  of the original through the reference controller. The goal types agreed in
  94.6 % of the pairs with the classes set aside (25 run pairs, 92.0 % to
  98.0 %), where the original's five repetitions agree with each other in
  94.1 % (10 run pairs, 91.9 % to 96.8 %); see
  [agreement between runs](../../docs/agreement.md#a-real-example).
  The [campaign comparator](../../docs/comparator.md) ran on the two
  campaigns in 19 minutes and wrote a report of 1.4 GB: 646926 metrics stable
  and identical, 3745 stable in the original and different, 7402 variable and
  outside the original's range, 3808 variable and compatible, 47127 not
  comparable; 72 groups and 62 local drafts. None of the drafts has been
  reviewed: they are counts, not findings.
- A private variant of the ambush scenario with a move order (the bandits made
  friendly, the player ordered 200 units east) completed: the order was
  accepted, the character's order read `move_cus_ordered`, and it stood 0.6
  units from the target from the third checkpoint on.
- A scenario cancelled while it ran, the way an MCP client cancels a tool
  (25 s into the hold, four checkpoints captured): the runner's report says
  `failed` with the cancellation, its restoration is verified, the guard is
  cleared, and the game is paused on the reloaded save.
- While a `run_until` ran, a second `run_until` and a `set_game_speed` were
  both answered `busy`, as on the native probe. Before this series the adapter
  answered `invalid_request` to the second `run_until` (seen on the build of
  `8ae1141a`); patch 2 now answers `busy` there.

**Verified** on 2026-11-12, without the game:

- The complete suite (Slow and Bench included, with a local install) had 983
  passes, 6 failures and 25 skipped of 1014 on the fork tip. The same run on
  upstream `9a19748b` without the patches had 798 passes, the same 6 failures
  and 25 skipped of 829. The six are rendering, texture, interface, distant
  mesh and particle tests; none is an Oracle test. The series adds no failure.
- The Metal-only code, with the adapter's three hooks in `MetalGameLoop.cs`,
  compiled with 0 warnings and 0 errors under `-p:MeitouMetal=true`, the
  option upstream gives for checking that code off macOS. It was not run.

**Observed** on 2026-11-12, in the game, beside the original (one machine):

- The scene-setup scenario ran five repetitions on each engine (MeitouClient
  seeds 0 to 4; the original through the reference controller); the setup
  passed in all ten. The [comparator](../../docs/comparator.md) classified
  117 scene metrics: 114 stable and identical, 2 variable and compatible, 1
  stable in the original and different, `/scene/intruders/count` at 330 s
  (0 in the original's five repetitions, 0 to 5 on MeitouClient: characters
  that enter the scene from outside). No draft was made.
- The move-order variant ran once on each engine: the order was accepted on
  both and the character ended 0.8 units from the target on the original and
  0.6 on MeitouClient.
- A second save, a large town, ran the same kind of hold five times on each
  engine. Only the 38 characters stored in that save pair between the
  engines; their goal types agree in 99.1 % of the pairs between MeitouClient
  and the original (25 run pairs, 95.7 % to 100 %) and in 98.3 % between the
  original's own repetitions (10 run pairs, 95.7 % to 100 %). The town's
  people, made at load with different handles, are outside this count.

**Not done on this base:** recovery after a crash of MeitouClient in the
middle of a scenario, and anything on macOS.

One test changed with the base: `OracleTaskNamesTests` compares the native
lower_snake task names with Meitou's `TaskType` members without the
underscores, because those members are PascalCase now; the same eight rows
differ (0, 38, 52, 65, 223, 245, 289 and 290).

### Evidence on the earlier base `88ae71a1`

The figures below were obtained on the previous series and are kept as its
record. They do not describe this base.

**Verified:** in a scratch checkout at upstream `88ae71a1`, without network
access, `git am --3way` applied the ten patches cleanly with
`core.autocrlf=false` and with `core.autocrlf=true`; both times the resulting
tree equalled the fork tip's tree `0a6623763baf3bdfa2743a0edd974ca1dcd7676d`
(compared with `git rev-parse HEAD^{tree}`).
This checks source reproduction, not a live campaign. The patch 7 results below
ran at `efc2eb2a`, the same tree as `8677d68d` before patch 7's author was set
to CrockMr.

Adapt the relative `../KenshiOracle` checkout name. No contributor's installation
path is embedded in the patches. Configure your own original content through
Meitou's `KENSHI_PATH`; no content, save or SDK binary is included here. Use the
[Meitou target guide](../../docs/meitou-target.md) for private working preferences,
process ownership, scenario execution and restoration.

**Verified** at fork tip `198f4f81` on `88ae71a1`, in the fork's own checkout
(whose tree equals the `git am` result above), with SDK 10.0.403:
- The Release build had 0 warnings and 0 errors.
- The Oracle tests (`FullyQualifiedName~Meitou.Tests.Oracle`) passed 180 of
  180.
- The quick suite (`Category!=Slow&Category!=Bench`) had 962 passes and 0
  failures (3 skipped) at the fork tip `198f4f81`, and 957 passes at
  `a9684066`, the patch 8 commit before the five shared 0.5 vector cases and
  the documentation were amended in (its source code is identical to
  `198f4f81`). It had 947 passes and 0 failures (3 skipped) at the patch 7
  tip `8677d68d`, and 926 passes and 0 failures (3 skipped) at the patch 6 tip
  `cd5a194d`.
- The complete suite (Slow and Bench included) on the `198f4f81` tree had 1109
  passes, 13 failures and 25 skipped of 1147. The same run at the patch 7 tip
  `8677d68d` had the same 13 failures plus the timing test
  `OracleServerTests.A_host_timeout_cancels_queued_work_and_late_completion_cannot_replace_the_error`,
  which fails or passes with machine load. None of the 13 is an Oracle test:
  they are UI, rendering, texture, navigation, world and kidnap tests.
- At the patch 6 tip `cd5a194d`, the focused Oracle/camera tests (the filter
  above) passed 152 of 152; with `GoldenHashTests` and `DeterminismTests`
  added, the Oracle filter passed 172 of 172. The golden hashes are unchanged,
  and tests of patches 5 to 8 check that the capture leaves
  `World.StateHash()` unchanged.
- At the earlier tip `da2b35b4` of patch 6 (before the shared 0.3 vectors were
  copied in), a first quick-suite run had 2 failures outside the adapter
  (`AiTests` and `ConstructionTests`, one a missing shared `%TEMP%` save
  folder); both passed alone and in a complete rerun. Treat them as
  environment-sensitive; they were not reproduced on `cd5a194d`.
- The complete suite (Slow and Bench included) had 1094 passes, 13 failures
  and 25 skipped at the patch 7 tip `8677d68d`, and 1072 passes, 14 failures and 25 skipped at
  `cd5a194d`, run one after the other on the same machine. The 13 failures are
  the same tests on both (GPU, texture, interface, navmesh, distant-mesh,
  particle and one kidnap test, none in the adapter); the extra failure at
  `cd5a194d` is the timing test named below. Patch 7 adds no failure.
- The run with `KENSHI_ORACLE_VECTORS`, the start without `--oracle` and a
  quick city run were not repeated on this base; the last such evidence is for
  the `100c6cae` series (see the [maintenance guide](../../docs/maintenance.md)).

**Observed:** the timing test
`OracleServerTests.A_host_timeout_cancels_queued_work_and_late_completion_cannot_replace_the_error`
(1 s host timeout) fails occasionally when the machine is loaded: once in a
complete run on each of the `08340c7` and `100c6cae` bases. It passed in every
isolated rerun (five on each base) and in the quick suite on `88ae71a1`.
Treat it as timing-sensitive.
This is not a claim that the full suite is green or that another machine will
reproduce every environmental result. See the
[phase 2 validation](../../docs/phase2-validation.md).

**Observed:** the 1 November 2026 scene-setup campaigns ran on patches 1-4
of the `88ae71a1` series (fork tip `893114de`); see the
[0.11.0 notes](../../release/v0.11.0-notes.md).
**Observed:** one paused state check (N = 1, one save, no scene campaign) ran
on a build of `8677d68d` (state 0.4) and one on a build of `198f4f81` (state
0.5); see the [state coverage](../../docs/state-coverage.md#extension-additive-04).
**Unknown:** patches 5 to 8 in a scene campaign; no scene campaign has run on
`5ab88d9a`, `cd5a194d`, `8677d68d` or `198f4f81`.

## Scope and maintenance

The adapter starts only with `--oracle`. Its loopback endpoint defaults to port
47801; `--oracle-port` and `--oracle-output` require that flag. The host services
mutations and state projection on its frame thread, including while paused;
network workers parse detached JSON and read an immutable cached heartbeat.
Tick-ahead work is joined before a world read. A load prepares the population
without an unclocked combat tick, and the requested seed is applied before
`SaveLoader`. Oracle mode disables autosaves and drops every key, menu and
import save or load request. With the flag absent, the listener and Oracle
startup preparation do not run.

Most added runtime code is isolated in `GameHost.Oracle.cs`,
`GameHost.OracleSetup.cs` and `Oracle/` (the command-line options in
`Oracle/OracleOptions.cs`); the existing host files contain the lifecycle and
frame seams: the frame loops (`Host/GameLoop.cs`, `Host/MetalGameLoop.cs`),
the save handler (`Host/GameSaves.cs`), the follow camera
(`Scenarios/SandboxScenario.cs`), `GameHost.cs`, `GameHost.Transition.cs`,
`Host/GameOptions.cs` and `Host/Program.cs`. Outside the adapter's own files
the series changes 16 upstream files by 196 added and 9 removed lines. The first patch adds two exact camera-restoration
methods and their tests. The third adds the simulation entry points scene
setup needs (a swap-aware relation setter, a template-squad plan and spawn, a
paused edit bracket); the fourth adds the `setup_*` commands of the
[scene-setup contract](../../docs/scene-setup.md), `allow_setup` on
`load_save`, the ping additions and the `issue_order` refusals; the fifth
fills `health[].maximum` with the calculated part maximum; the sixth, seventh and
eighth add the state 0.3, 0.4 and 0.5 fields; the ninth checks that a captive
job's goal is its worker's 0.5 goal; the tenth raises the adapter version to 0.12.0. Keep these
integration points small when updating upstream; do not copy unrelated
upstream changes into this series. The shared canonical vectors are synthetic
fixtures, not game data.

Maintain the branch as a durable fork. Before updating, keep a local backup
branch, record the old upstream base, then fetch the current upstream and rebase
the ten adapter commits onto the selected upstream commit. Resolve
host/lifecycle conflicts explicitly. Build both flag modes, rerun the focused
tests and shared canonical vectors, and compare any complete-suite failures
with that same unmodified upstream. Revalidate pause/loading, seed provenance,
fresh heartbeat, cancellation, restoration and scene setup with local saves
before claiming compatibility. Export a fresh ten-patch series into a
temporary directory with `git format-patch -N --no-signature`, review the diff,
then update the pinned base, source commits, hashes and validation evidence
here. Do not publish or force-push an upstream repository as part of this
procedure.

Upstream's own guidance at this base asks for a feature with state of its
own to be a class of its own rather than another `partial` file of the host.
The adapter's two host files are still partials of `GameHost`; making them one
collaborator class, as upstream's `GameLoop` and `GameSaves` are, would shrink
the seam further and is not done.

The upstream modding API is still a preliminary concept at the pinned commit.
Its proposed tick-system surface does not yet supply all the loading, seed,
lifecycle and paused-service hooks this adapter needs. This series therefore
implements the host seam; it does not invent a plugin framework. See the
[design and modding analysis](../../docs/meitou-oracle-design.md).

## License and attribution

MeitouClient and this derivative patch series are distributed under
**GPL-3.0-or-later**. The upstream [LICENSE](LICENSE) and its
[additional permission for specified NVIDIA libraries](LICENSE-EXCEPTION.md)
are preserved verbatim from the pinned upstream commit. The latter permission
does not cover unrelated non-free dependencies. Upstream work is by the
MeitouClient contributors; the ten modifications were made for KenshiOracle,
with patches 1-2 committed as KenshiOracle contributors and patches 3-10 as
CrockMr (each patch's `From:` line). No proprietary executable, disassembled listing or decompiled
game code is included. Upstream dependency notices remain in the separately
obtained MeitouClient checkout.
