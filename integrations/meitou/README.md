# MeitouClient Oracle patch series

This directory makes the Meitou adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the four patches, in
order, to upstream MeitouClient commit
`88ae71a1eeb65bc7081751f19763f032093b2621` (master of 2026-11-01). They
correspond to the local fork tip `893114dec3a8543ade4147fb8f2f4040ac4cf365`;
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

[series.json](series.json) records the exact SHA-256 and byte size of each patch.

Patch 2 was regenerated for this series: it now declares the adapter version
as the constant `OracleProtocol.AdapterVersion` instead of a literal (still
`0.10.0` there). Patch 4 raises it to `0.11.0`, the version of the
[scene-setup contract](../../docs/scene-setup.md), and adds `build_commit` to
ping. Evidence that reported `plugin_version` `0.10.0` from Meitou does not
identify one build; from this series on, a build is identified by
`build_commit`.

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
git -c core.autocrlf=false am -- "$Series/0001-exact-camera-restoration.patch" "$Series/0002-opt-in-oracle-adapter.patch" "$Series/0003-scene-setup-simulation.patch" "$Series/0004-scene-setup-adapter.patch"
dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~Meitou.Tests.Engine.CameraTests|FullyQualifiedName~Meitou.Tests.Engine.OracleCameraRestoreTests"
```

Build from a clean Git checkout: `build_commit` is the full commit only when
`git status --porcelain` is empty at build time, otherwise `"unknown"`, which
the comparator refuses for campaigns.

**Verified:** in a scratch clone of upstream `88ae71a1`, `git am` applied the
four patches cleanly with `core.autocrlf=false` and with `core.autocrlf=true`;
both times the resulting tree equalled the fork tip's tree (compared with
`git rev-parse HEAD^{tree}`).
This checks source reproduction, not a live campaign.

Adapt the relative `../KenshiOracle` checkout name. No contributor's installation
path is embedded in the patches. Configure your own original content through
Meitou's `KENSHI_PATH`; no content, save or SDK binary is included here. Use the
[Meitou target guide](../../docs/meitou-target.md) for private working preferences,
process ownership, scenario execution and restoration.

**Verified** at fork tip `893114de` on `88ae71a1`, in the fork's own checkout
(whose tree equals the `git am` result above), with SDK 10.0.403:
- The focused Oracle/camera tests (the filter above) passed 145 of 145.
- The quick suite (`Category!=Slow&Category!=Bench`) had 919 passes and 0
  failures (3 skipped).
- The complete suite, the run with `KENSHI_ORACLE_VECTORS`, the start without
  `--oracle` and a quick city run were not repeated on this base; the last such
  evidence is for the `100c6cae` series (see the
  [maintenance guide](../../docs/maintenance.md)).

**Observed:** the timing test
`OracleServerTests.A_host_timeout_cancels_queued_work_and_late_completion_cannot_replace_the_error`
(1 s host timeout) fails occasionally when the machine is loaded: once in a
complete run on each of the `08340c7` and `100c6cae` bases. It passed in every
isolated rerun (five on each base) and in the quick suite on `88ae71a1`.
Treat it as timing-sensitive.
This is not a claim that the full suite is green or that another machine will
reproduce every environmental result. See the
[phase 2 validation](../../docs/phase2-validation.md).

**Unknown:** the in-game behaviour of the scene-setup commands; no live
campaign has run on this series.

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
`load_save`, the ping additions and the `issue_order` refusals. Keep these
integration points small when updating upstream; do not copy unrelated
upstream changes into this series. The shared canonical vectors are synthetic
fixtures, not game data.

Maintain the branch as a durable fork. Before updating, keep a local backup
branch, record the old upstream base, then fetch the current upstream and rebase
the four adapter commits onto the selected upstream commit. Resolve
host/lifecycle conflicts explicitly. Build both flag modes, rerun the focused
tests and shared canonical vectors, and compare any complete-suite failures
with that same unmodified upstream. Revalidate pause/loading, seed provenance,
fresh heartbeat, cancellation, restoration and scene setup with local saves
before claiming compatibility. Export a fresh four-patch series into a
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
MeitouClient contributors; the four modifications were made for KenshiOracle,
with patches 1-2 committed as KenshiOracle contributors and patches 3-4 as
CrockMr (each patch's `From:` line). No proprietary executable, disassembled listing or decompiled
game code is included. Upstream dependency notices remain in the separately
obtained MeitouClient checkout.
