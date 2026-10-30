# MeitouClient Oracle patch series

This directory makes the phase 2 adapter reproducible without distributing a
Meitou binary or relying on an unpublished fork. Apply the two patches, in order,
to upstream MeitouClient commit
`100c6caec876cb1cdb4e3a404eed7e6d7b33eb54` (master of 2026-10-31). They correspond
to the validated local fork tip `5ed31178cc6e4ea6a81ee6ab8b7e2ef3a7278ae6`; they are
not an upstream release or an endorsement from the MeitouClient team. Earlier
series targeted `1df44934efd32c49998e7f3aa75d877fb499459a` (the recorded phase 2
campaigns) and `08340c728c6b85a2b2d12df4211a60e170acb5ba`; the
[mod-free campaigns](../../docs/mod-free-campaigns.md) name the base of each run.

| Order | Patch | Source commit |
| --- | --- | --- |
| 1 | [Exact camera restoration](0001-exact-camera-restoration.patch) | `99add603ab4077e924020ea5a1ffb4d37d55ee20` |
| 2 | [Opt-in Oracle adapter](0002-opt-in-oracle-adapter.patch) | `5ed31178cc6e4ea6a81ee6ab8b7e2ef3a7278ae6` |

[series.json](series.json) records the exact SHA-256 and byte size of each patch.

## Apply and build

Use a separate checkout beside this KenshiOracle checkout. MeitouClient's
`global.json` requires .NET SDK 10.0.401 with `latestFeature` roll-forward; the
local validation used the already installed SDK 10.0.403. Install the SDK
separately if necessary.

For a new checkout:

```powershell
git clone https://github.com/VlcekM/MeitouClient.git MeitouClient
Set-Location MeitouClient
git switch -c oracle-adapter-100c6ca 100c6caec876cb1cdb4e3a404eed7e6d7b33eb54
```

In an existing checkout of an earlier series, run `git fetch origin` and then the
same `git switch` line; your old branch stays as a backup. Then, in either case:

```powershell
$OracleRoot = (Resolve-Path ../KenshiOracle).Path
git am -- "$OracleRoot/integrations/meitou/0001-exact-camera-restoration.patch" "$OracleRoot/integrations/meitou/0002-opt-in-oracle-adapter.patch"
dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~Meitou.Tests.Engine.CameraTests|FullyQualifiedName~Meitou.Tests.Engine.OracleCameraRestoreTests"
```

**Verified:** against a fresh upstream `git archive`, with no old Git directory
copied, `git am` applied both patches cleanly with `core.autocrlf=false` and with
`core.autocrlf=true`; both times all 26 changed files matched the tested fork
byte for byte. This checks source reproduction, not an additional live campaign.

Adapt the relative `../KenshiOracle` checkout name. No contributor's installation
path is embedded in the patches. Configure your own original content through
Meitou's `KENSHI_PATH`; no content, save or SDK binary is included here. Use the
[Meitou target guide](../../docs/meitou-target.md) for private working preferences,
process ownership, scenario execution and restoration.

**Verified** at fork tip `5ed31178` on `100c6cae`, in a checkout produced from a
fresh upstream `git archive` with `git am`:
- The focused Oracle/camera tests (the filter above) passed 115 of 115, both with
  the fork's own copy of the shared vectors and with `KENSHI_ORACLE_VECTORS`
  pointing at this repository's `schema/canonical-vectors.json`.
- The quick suite (`Category!=Slow&Category!=Bench`) had 886 passes and 0 failures
  (3 skipped).
- The complete test run had 1033 passes, 13 failures and 25 skips. The same 13
  tests failed on the unmodified pinned upstream in that environment (923 passes,
  13 failures, 25 skips); none of them is an Oracle or camera test.

**Observed:** the timing test
`OracleServerTests.A_host_timeout_cancels_queued_work_and_late_completion_cannot_replace_the_error`
(1 s host timeout) fails occasionally when the machine is loaded: once in a
complete run on each of the `08340c7` and `100c6cae` bases. It passed in every
isolated rerun (five on each base) and in the complete run above, on a quiet
machine. Treat it as timing-sensitive.
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
