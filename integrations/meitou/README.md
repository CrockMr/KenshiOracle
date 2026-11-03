# MeitouClient Oracle patch series

This directory makes the Meitou adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the nine patches, in
order, to upstream MeitouClient commit
`88ae71a1eeb65bc7081751f19763f032093b2621` (master of 2026-11-01). They
correspond to the local fork tip `9e16733617a47f647ed91ef98f62994bf3580d12`;
they are not an upstream release or an endorsement from the MeitouClient team.
Earlier series targeted `1df44934efd32c49998e7f3aa75d877fb499459a` (the
recorded phase 2 campaigns), `08340c728c6b85a2b2d12df4211a60e170acb5ba` and
`100c6caec876cb1cdb4e3a404eed7e6d7b33eb54`; the
[mod-free campaigns](../../docs/mod-free-campaigns.md) name the base of each run.

| Order | Patch | Source commit |
| --- | --- | --- |
| 1 | [Exact camera restoration](0001-exact-camera-restoration.patch) | `e85071f137ba0f5f8d6e8b045f2f4a95e6ae339c` |
| 2 | [Opt-in Oracle adapter](0002-opt-in-oracle-adapter.patch) | `2b10478095651fdfbb5fd7ea38c8a20ef9e75750` |
| 3 | [Scene-setup simulation entry points](0003-scene-setup-simulation.patch) | `8b255b96d877094e184edce14b212afbd893ada4` |
| 4 | [Scene-setup adapter commands](0004-scene-setup-adapter.patch) | `893114dec3a8543ade4147fb8f2f4040ac4cf365` |
| 5 | [Calculated health maxima in the state dump](0005-calculated-health-maxima.patch) | `5ab88d9a8960e75241965c1e48b3760544db264e` |
| 6 | [Slave state and owner faction in state 0.3](0006-slave-state-fields.patch) | `cd5a194dc9013ec8a81d1b339686bda649e3cc5f` |
| 7 | [State 0.4 fields and task-row orders](0007-state-04-fields-and-task-orders.patch) | `8677d68da41e8961972e387c565c0f678618e79b` |
| 8 | [State 0.5 goals and plan-step orders](0008-state-05-goals-and-plan-step-orders.patch) | `198f4f8149aa06589c39d52f7688925591d67197` |
| 9 | [Captive job goals in state 0.5](0009-captive-job-goals.patch) | `9e16733617a47f647ed91ef98f62994bf3580d12` |

[series.json](series.json) records the exact SHA-256 and byte size of each patch.

Patch 2 was regenerated for this series: it now declares the adapter version
as the constant `OracleProtocol.AdapterVersion` instead of a literal (still
`0.10.0` there). Patch 4 raises it to `0.11.0`, the version of the
[scene-setup contract](../../docs/scene-setup.md), and adds `build_commit` to
ping. Evidence that reported `plugin_version` `0.10.0` from Meitou does not
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
defects that later upstream changes address, all after the pinned base; see the
[MeitouClient findings](../../docs/meitou-findings.md).

Patch 9 changes only the 0.5 `goal` of a character that works a captive job.
MeitouClient runs captive work (gathering slaves from cages, working them,
getting into a cage, guarding or processing prisoners) as `CaptiveSystem` jobs,
and the AI holds no worker of a job, so its mind keeps the goal it had before.
The captive sweep now records on each job the AI goal it started the job for
(`CaptiveJob.Goal`, a role list's or the race's goal). While the job runs, the
worker's goal is that goal, by row number with its AI_TASK tier; otherwise it is
the mind's goal as before. A job started any other way (a player animal's race
goal) has no recorded goal and changes nothing. 0.1 to 0.4 output and the 0.5
`order` are unchanged (pinned by test). Whether this goal is what the original's
`currentGoal` holds during the same work is **Unknown** until a live check.

## Apply and build

Use a separate checkout beside this KenshiOracle checkout. MeitouClient's
`global.json` requires .NET SDK 10.0.401 with `latestFeature` roll-forward; the
local validation used the already installed SDK 10.0.403. Install the SDK
separately if necessary.

For a new checkout:

```powershell
git clone https://github.com/VlcekM/MeitouClient.git MeitouClient
Set-Location MeitouClient
git switch -c oracle-adapter-88ae71a 88ae71a1eeb65bc7081751f19763f032093b2621
```

In an existing checkout of an earlier series, run `git fetch origin` and then the
same `git switch` line; your old branch stays as a backup. Then, in either case:

```powershell
$OracleRoot = (Resolve-Path ../KenshiOracle).Path
$Series = "$OracleRoot/integrations/meitou"
git -c core.autocrlf=false am -- "$Series/0001-exact-camera-restoration.patch" "$Series/0002-opt-in-oracle-adapter.patch" "$Series/0003-scene-setup-simulation.patch" "$Series/0004-scene-setup-adapter.patch" "$Series/0005-calculated-health-maxima.patch" "$Series/0006-slave-state-fields.patch" "$Series/0007-state-04-fields-and-task-orders.patch" "$Series/0008-state-05-goals-and-plan-step-orders.patch" "$Series/0009-captive-job-goals.patch"
dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~Meitou.Tests.Engine.CameraTests|FullyQualifiedName~Meitou.Tests.Engine.OracleCameraRestoreTests"
```

Build from a clean Git checkout: `build_commit` is the full commit only when
`git status --porcelain` is empty at build time, otherwise `"unknown"`, which
the comparator refuses for campaigns.

**Verified:** in a scratch checkout at upstream `88ae71a1`, without network
access, `git am --3way` applied the nine patches cleanly with
`core.autocrlf=false` and with `core.autocrlf=true`; both times the resulting
tree equalled the fork tip's tree `4eee259e925abeb6c1eeb9b35bb4f23b362f0fb4`
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
(fork tip `893114de`); see the [0.11.0 notes](../../release/v0.11.0-notes.md).
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
`GameHost.OracleSetup.cs` and `Oracle/`; the existing host files contain the
lifecycle/frame seams. The first patch adds two exact camera-restoration
methods and their tests. The third adds the simulation entry points scene
setup needs (a swap-aware relation setter, a template-squad plan and spawn, a
paused edit bracket); the fourth adds the `setup_*` commands of the
[scene-setup contract](../../docs/scene-setup.md), `allow_setup` on
`load_save`, the ping additions and the `issue_order` refusals; the fifth
fills `health[].maximum` with the calculated part maximum; the sixth, seventh and
eighth add the state 0.3, 0.4 and 0.5 fields; the ninth reports a captive job's
goal as the 0.5 goal. Keep these
integration points small when updating upstream; do not copy unrelated
upstream changes into this series. The shared canonical vectors are synthetic
fixtures, not game data.

Maintain the branch as a durable fork. Before updating, keep a local backup
branch, record the old upstream base, then fetch the current upstream and rebase
the nine adapter commits onto the selected upstream commit. Resolve
host/lifecycle conflicts explicitly. Build both flag modes, rerun the focused
tests and shared canonical vectors, and compare any complete-suite failures
with that same unmodified upstream. Revalidate pause/loading, seed provenance,
fresh heartbeat, cancellation, restoration and scene setup with local saves
before claiming compatibility. Export a fresh nine-patch series into a
temporary directory with `git format-patch -N --no-signature`, review the diff,
then update the pinned base, source commits, hashes and validation evidence
here. Do not publish or force-push an upstream repository as part of this
procedure.

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
MeitouClient contributors; the nine modifications were made for KenshiOracle,
with patches 1-2 committed as KenshiOracle contributors and patches 3-9 as
CrockMr (each patch's `From:` line). No proprietary executable, disassembled listing or decompiled
game code is included. Upstream dependency notices remain in the separately
obtained MeitouClient checkout.
