# MeitouClient Oracle patch series

This directory makes the Meitou adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the ten patches, in
order, to upstream MeitouClient commit
`8ae1141a2c91598a161eefd68dc277cc0aeaabb4` (master of 2026-11-12). They
correspond to the local fork tip
`e3a37180abe706c05f866e1da2135f0f0ebf0d31`; they are not an upstream release or
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
  lies 1759 commits before this base. On this base it applies, builds and
  passes its tests ([below](#apply-and-build)).
- **Verified** on 2026-11-12 (local mirror, fetched after the rebase): upstream
  `master` is `8ae1141a2c91598a161eefd68dc277cc0aeaabb4`, the base itself
  (0 commits after the base). It will not stay so for long.
- The holds reported in the [MeitouClient findings](../../docs/meitou-findings.md)
  after 2026-11-03 used private builds on
  `c09ed01c3d26eeb69433dbd6c69fae7dc71b554f`, which lies 435 commits before
  this base. One hold has run on this series ([below](#apply-and-build)); it
  does not include the private fixes those builds carried, so those figures
  are not reproduced from it.

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
| 1 | [Exact camera restoration](0001-exact-camera-restoration.patch) | `8e8d83bcfe98d7e6d468e0248b5843176e71b316` |
| 2 | [Opt-in Oracle adapter](0002-opt-in-oracle-adapter.patch) | `b9cf5f3c6735ab6b60d8bb84f550b4b8874d911e` |
| 3 | [Scene-setup simulation entry points](0003-scene-setup-simulation.patch) | `24bcadb0fd6fcb317afa8657256ca15933bc1759` |
| 4 | [Scene-setup adapter commands](0004-scene-setup-adapter.patch) | `9035e0a05b07bcb0b8d66b019affdb3923e127c4` |
| 5 | [Calculated health maxima in the state dump](0005-calculated-health-maxima.patch) | `2416f2d1486f84da1558f6e94eb987b71e42af35` |
| 6 | [Slave state and owner faction in state 0.3](0006-slave-state-fields.patch) | `ce1618b52c384f8129c95bfe5c08bedde40fcec4` |
| 7 | [State 0.4 fields and task-row orders](0007-state-04-fields-and-task-orders.patch) | `1730fec7519fbe6ffa64fd5236623b51dee084d6` |
| 8 | [State 0.5 goals and plan-step orders](0008-state-05-goals-and-plan-step-orders.patch) | `d34c3bbafb8d7201a9b55105933b41079dcb8105` |
| 9 | [Captive job goals in state 0.5: the check](0009-captive-job-goals.patch) | `957405fa156c3d56cbf7ee4f09cddc1d1053dd26` |
| 10 | [Adapter version 0.12.0](0010-adapter-version-0.12.0.patch) | `e3a37180abe706c05f866e1da2135f0f0ebf0d31` |

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
git switch -c oracle-adapter-8ae1141a 8ae1141a2c91598a161eefd68dc277cc0aeaabb4
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

**Verified** on 2026-11-12, at fork tip `e3a37180` on `8ae1141a`, with SDK
11.0.100 on Windows:

- In a scratch checkout at upstream `8ae1141a`, `git am` with
  `core.autocrlf=false` applied the ten patches cleanly and the resulting tree
  equalled the fork tip's tree `fa6779d19c0543e5aadc3996470c3b7934afdd4a`
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
  `42205b61cd6211d2db7c391d2008acfbf2de0584`, 28 commits earlier and the last
  upstream commit that builds with SDK 10.0.403: 0 warnings and 0 errors, 190
  of 190 focused tests, 826 quick-suite passes and 0 failures there. Between
  the two, one hook had to be placed again (the follow camera, which upstream
  changed for a carried character).

**Observed** on 2026-11-12, in the game, with a Release build of the fork tip
(one machine, N = 1, local saves not distributed):

- Started without `--oracle`, MeitouClient ran for 45 s; nothing listened on
  port 47801, no oracle output folder was made and no oracle line was printed.
- Started with `--oracle` under the watchdog, `ping` reported
  `plugin_version` `0.12.0` and `build_commit`
  `e3a37180abe706c05f866e1da2135f0f0ebf0d31`.
- One paused hold on a slave-camp save (seed 0, no orders, 20 checkpoints from
  0 to 3960 s, state 0.5) completed through the shared runner: every snapshot
  validated and the controls were verifiably restored.
- Against one hold of the original on the same save
  ([agreement between runs](../../docs/agreement.md)), the goal types agreed
  in 1626 of 1907 pairs (85.3 %), and in 1626 of 1688 (96.3 %) with the
  save's three load-order classes set aside. The private build on `c09ed01c`
  read 1643 of 1698 (96.8 %) by the same count, and a second hold of the
  original 1768 of 1795 (98.5 %). One hold per build: the half point between
  the two MeitouClient builds is not shown to be a difference.

**Not done on this base:**

- The complete suite (Slow and Bench included).
- The quick city run of the [maintenance guide](../../docs/maintenance.md),
  any scene setup, any scenario with orders and any campaign with repetitions.
  Revalidate cancellation, seed provenance across repetitions and scene setup
  with local saves before relying on them.
- The Metal loop's hooks (`MetalGameLoop.cs`) compile on macOS only and were
  not compiled.

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
