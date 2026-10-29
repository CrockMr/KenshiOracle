# MeitouClient Oracle patch series

This directory makes the phase 2 adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the two patches, in order,
to upstream MeitouClient commit
`1df44934efd32c49998e7f3aa75d877fb499459a`. They correspond to the validated local
fork tip `076d8abde354b6ac3eb1e4ad6976900534ed0698`; they are not an upstream
release or an endorsement from the MeitouClient team.

| Order | Patch | Source commit |
| --- | --- | --- |
| 1 | [Exact camera restoration](0001-exact-camera-restoration.patch) | `68d703314aa8a468510b9dac3f761b8b8831268f` |
| 2 | [Opt-in Oracle adapter](0002-opt-in-oracle-adapter.patch) | `076d8abde354b6ac3eb1e4ad6976900534ed0698` |

[series.json](series.json) records the exact SHA-256 and byte size of each patch.
Patch application was checked against a fresh upstream `git archive`, with no
old Git directory copied: all 26 resulting changed files match the tested fork
byte for byte. This checks source reproduction, not an additional live campaign.

## Apply and build

Use a separate checkout beside this KenshiOracle checkout. Its `global.json`
requires .NET SDK 10.0.401 with `latestFeature` roll-forward; the local validation
used the already installed SDK 10.0.403. Install the SDK separately if necessary.

```powershell
git clone https://github.com/VlcekM/MeitouClient.git MeitouClient
Set-Location MeitouClient
git switch -c oracle-adapter 1df44934efd32c49998e7f3aa75d877fb499459a
$OracleRoot = (Resolve-Path ../KenshiOracle).Path
git -c core.autocrlf=false am -- "$OracleRoot/integrations/meitou/0001-exact-camera-restoration.patch" "$OracleRoot/integrations/meitou/0002-opt-in-oracle-adapter.patch"
dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~OracleCameraRestoreTests"
```

Adapt the relative `../KenshiOracle` checkout name. No contributor's installation
path is embedded in the patches. Configure your own original content through
Meitou's `KENSHI_PATH`; no content, save or SDK binary is included here. Use the
[Meitou target guide](../../docs/meitou-target.md) for private working preferences,
process ownership, scenario execution and restoration.

The focused Oracle/camera tests passed 115 cases on the tested fork. The complete
non-`Bench` run had 716 passes, 11 failures and 24 skips; those same 11 failures
and messages reproduced on the unmodified pinned upstream in that environment.
This is not a claim that the full suite is green or that another machine will
reproduce every environmental result. See the
[phase 2 validation](../../docs/phase2-validation.md).

## Scope and maintenance

The adapter starts only with `--oracle`. Its loopback endpoint defaults to port
47801; `--oracle-port` and `--oracle-output` require that flag. The host services
mutations and state projection on its frame thread, including while paused;
network workers parse detached JSON and read an immutable cached heartbeat.
Tick-ahead work is joined before a world read. A load prepares the population
without an unclocked combat tick, and the requested seed is applied before
`SaveLoader`. Oracle mode disables autosaves. With the flag absent, the listener
and Oracle startup preparation do not run.

Most added runtime code is isolated in `GameHost.Oracle.cs` and `Oracle/`; the
existing host files contain the lifecycle/frame seams. The first patch adds two
exact camera-restoration methods and their tests. Keep these integration points
small when updating upstream; do not copy unrelated upstream changes into this
series. The shared canonical vectors are synthetic fixtures, not game data.

Maintain the branch as a durable fork. Before updating, keep a local backup
branch, record the old upstream base, then fetch the current upstream and rebase
the two adapter commits onto the selected upstream commit. Resolve host/lifecycle
conflicts explicitly. Build both flag modes, rerun the focused tests and shared
canonical vectors, and compare any complete-suite failures with that same
unmodified upstream. Revalidate pause/loading, seed provenance, fresh heartbeat,
cancellation and restoration with local saves before claiming compatibility.
Export a fresh two-patch series into a temporary directory, review the diff,
then update the pinned base, source commits, hashes and validation evidence here.
Do not publish or force-push an upstream repository as part of this procedure.

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
MeitouClient contributors; the two modifications are by KenshiOracle contributors.
No proprietary executable, disassembled listing or decompiled game code is
included. Upstream dependency notices remain in the separately obtained
MeitouClient checkout.
