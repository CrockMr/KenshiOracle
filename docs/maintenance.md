# Maintenance of the MeitouClient patch series

This guide is for maintainers who keep the
[MeitouClient patch series](../integrations/meitou/README.md) usable on a newer
upstream commit. It refines the
[planned update procedure](meitou-oracle-design.md#procédure-de-mise-à-jour-prévue)
with the routine actually followed. The start-of-session routine runs no game.
During a rebase, only the no-`--oracle` start check (step 3) and the quick city
test (step 7) launch MeitouClient. No step publishes or pushes to the upstream
repository.

The public series has exactly four patches, in order: exact camera restoration,
the opt-in Oracle adapter, the scene-setup simulation entry points, then the
scene-setup adapter commands. [series.json](../integrations/meitou/series.json)
is the source of truth for the upstream base, the fork tip, and each patch's
source commit, SHA-256 and byte size. A maintainer may carry further local
commits on top (diagnostic instrumentation, test-only commands); they are not
part of the series, are never exported into it, and are rebased as separate
layers above it.

## Start-of-session routine

1. Close Kenshi and MeitouClient. Nothing in this routine needs either.
2. Check upstream from a dedicated mirror or clone, never from a frozen
   working copy (see [Version-change rules](#version-change-rules)):
   - new commits on `master` since the last check, and since the series base;
   - new release tags matching `^v\d+\.\d+\.\d+$`; nightly tags
     (`*-nightly.*`) are informational only;
   - upstream changes to measured systems (population and squads, save
     loading, factions) and to the files the series touches;
   - whether the four patches still apply to `master` with `git am --3way`, and
     whether the result builds and passes the focused tests.
3. Record the findings (conflicts, patches already present upstream, build or
   test failures, measured-system changes) and the last upstream commit
   reviewed. A finding is something to record, not a reason to rebase
   immediately.
4. The next check starts from the recorded commit. A finding stays open until
   the maintainer has read it.

**Observed:** a measured-system change upstream does not by itself mean a
behavior change in a campaign; it means the next rebase decision must look at
it.

## Version-change rules

Rebase only:

- before a new campaign series;
- before sending anything to the upstream developer;
- before and during a port;
- when the upstream check flags a change in a measured system.

Never rebase in the middle of a campaign series: every repetition of a series
runs on the same frozen build.

Choice of base:

- campaigns prefer a published MeitouClient release (tag matching
  `^v\d+\.\d+\.\d+$`) over an arbitrary `master` commit;
- ports use `master`;
- never a nightly build.

A rebase always produces a new branch and a new frozen build with new
fingerprints. Frozen builds, their working copies and their recorded
fingerprints are never modified in place. An upstream check advises; the
maintainer decides.

## Rebasing the series

Run these steps in a separate MeitouClient checkout. `$Base` is the new
upstream commit or release tag, `$OracleRoot` this KenshiOracle checkout.

1. Record the old base from `series.json`, then create the new branch without
   touching the previous one, as in the
   [series README](../integrations/meitou/README.md). The previous
   `oracle-adapter-*` branch is kept unchanged as the backup:

   ```powershell
   git fetch origin
   git switch -c oracle-adapter-<new-short-base> $Base
   ```

2. Apply the series with line-ending conversion disabled, so the result does
   not depend on the local Git configuration:

   ```powershell
   $Series = "$OracleRoot/integrations/meitou"
   git -c core.autocrlf=false am --3way -- "$Series/0001-exact-camera-restoration.patch" "$Series/0002-opt-in-oracle-adapter.patch" "$Series/0003-scene-setup-simulation.patch" "$Series/0004-scene-setup-adapter.patch"
   ```

   Resolve conflicts explicitly, especially in the host lifecycle and frame
   seams, clock units, seed application before loading and load preparation.
   Do not copy unrelated upstream changes into the series.

3. Build, confirm that the game still starts without `--oracle` (the adapter
   must stay inert without the flag), then run the focused tests:

   ```powershell
   dotnet build -c Release src/Meitou.Game/Meitou.Game.csproj
   dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle|FullyQualifiedName~Meitou.Tests.Engine.CameraTests|FullyQualifiedName~Meitou.Tests.Engine.OracleCameraRestoreTests"
   ```

   Run them a second time with `KENSHI_ORACLE_VECTORS` pointing at this
   repository's [canonical vectors](../schema/canonical-vectors.json).

4. Run the complete suite on the patched branch and on the same upstream
   commit without the patches, in the same environment. Only failures absent
   from the unmodified upstream count against the series. **Observed:** some
   upstream tests fail in a given environment and at least one Oracle timing
   test is sensitive to full-suite load; rerun such a test class in isolation
   before drawing a conclusion.

5. Export a fresh series into an empty temporary directory, then rename the
   files to the published names and review the diff against the old series:

   ```powershell
   git format-patch --no-signature -o $TempDir $Base..HEAD
   ```

   The published patches are stored with LF line endings
   (`.gitattributes` forces `eol=lf`). Compute `sha256` and `bytes` on that
   LF content, then update `upstream_base`, `fork_tip`, each `source_commit`,
   `sha256` and `bytes` in `series.json`, and the base and validation evidence
   in the [series README](../integrations/meitou/README.md).

6. Check reproduction: apply the exported patches with `git am` to a fresh
   checkout of `$Base` and compare the changed files with the rebased branch
   byte for byte.

7. Run a quick city test with seed 0 before claiming compatibility: set
   `base_seed` to `0` in `config.meitou.json` and run
   [ville-calme](../scenarios/ville-calme.json) once with `--repeat 1`, as
   described in the [Meitou target guide](meitou-target.md#cli-and-shared-tools).
   Its checkpoints at 120 and 600 calendar seconds are about 3.6 and 18.2
   simulated seconds (1 simulated second = 33 calendar seconds).

8. Freeze the new build into a new directory with its own fingerprints, and
   rebase any private layers on top of the new series separately.

A clean `git am`, a passing focused suite and one quick city run are evidence
for that base and that environment only. They do not establish scenario
compatibility, parity with the original game, or results on another machine.
Revalidate pause and loading, seed provenance, heartbeat freshness,
cancellation and restoration with local saves as the series README requires.
