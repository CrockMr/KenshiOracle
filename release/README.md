# Preparing KenshiProbe v0.11.0

This is the scene-setup probe release. Do not publish the older v0.9.5 or
v0.10.0 packages for the current `main`. Live validation of scene setup is
pending, and no reviewed 0.11.0 DLL hash is recorded yet: the packager refuses
to package until one is. The native version comes from
[`plugin/Version.h`](../plugin/Version.h); both shared-state 0.1 and 0.2 remain
supported. The [release notes](v0.11.0-notes.md) describe the validation scope.

## Build and package locally

Follow the environment-variable setup in the [first-run guide](../docs/first-run.md),
then build both DLLs from the repository root:

```powershell
cmd /d /c plugin\build-v100.cmd
& .\.venv\Scripts\python.exe release/prepare_release.py
```

The packager uses only Python's standard library and does not install into a
game or contact GitHub. It accepts only the exact reviewed DLL hashes recorded
in its source, verifies x64 PE files and neutral CodeView PDB basenames, checks
ordinary and UTF-16 strings for machine paths/account names, and packages an
explicit member allowlist. A differently built DLL needs a fresh review; do
not bypass the hash check by copying an earlier release.

The generated zero-record `.mod` descriptor is original metadata, not a game
file. A synthetic installation verifies extraction, manifest targets and exact
restoration of a previous synthetic mod folder. This is a layout check, not a
real-game loading test.

Generated files stay under ignored `dist/v0.11.0/`:

| File | Purpose |
| --- | --- |
| `KenshiProbe-v0.11.0-win-x64.zip` | Two DLLs, manifest, zero-record descriptor, installation notice and GPLv3 |
| `SHA256SUMS` | Archive, extracted DLL and companion-record SHA-256 hashes |
| `source-manifest.json` | Exact native/packaging inputs, with CRLF normalized to LF |
| `build-info.json` | Version, toolset, binary hashes and corresponding source commit |
| `binary-audit.json` | PE/PDB-path and package privacy checks |
| `installation-verification.json` | Synthetic installation/restoration result |
| `release-notes.md` | Notes bound to the exact reviewed source commit |

The DLLs use `/PDBALTPATH` with a neutral basename. Raw PDBs can still contain
absolute source-machine paths; **no symbols archive is prepared or published**.
Keep local PDBs private for crash diagnosis.

## Bind the final source commit

After creating the reviewed commit in the clean public repository, run there:

```powershell
$SourceCommit = (git rev-parse HEAD).Trim()
& .\.venv\Scripts\python.exe release/prepare_release.py --bind-source --repository CrockMr/KenshiOracle --source-commit $SourceCommit
```

If Python is outside this checkout, invoke the interpreter chosen through
`KENSHI_PROBE_PYTHON` instead. The packager refuses to bind through an ancestor
repository, verifies every manifest input against that commit, writes its
immutable source URL and refreshes `SHA256SUMS`. Do not edit generated records
after binding without regenerating their checksums.

## Owner publication commands

Review the commit and assets first. The following commands are for the owner;
the agent does not push, create a tag or publish a release. Run them only from
the clean public repository, whose `origin` is already configured:

```powershell
$SourceCommit = (git rev-parse HEAD).Trim()
git push origin main
git tag -a v0.11.0 $SourceCommit -m "KenshiProbe v0.11.0"
git push origin refs/tags/v0.11.0
gh release create v0.11.0 --verify-tag --title "KenshiProbe v0.11.0" --notes-file dist/v0.11.0/release-notes.md dist/v0.11.0/KenshiProbe-v0.11.0-win-x64.zip dist/v0.11.0/SHA256SUMS dist/v0.11.0/source-manifest.json dist/v0.11.0/build-info.json dist/v0.11.0/binary-audit.json dist/v0.11.0/installation-verification.json dist/v0.11.0/release-notes.md
```

GitHub CLI must be installed and authenticated for the final command. The tag
must point to the same reviewed commit as `build-info.json`. Do not force-push
or publish from the old working repository.
