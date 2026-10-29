# Preparing v0.9.5

This public source repository has one initial commit on `main`. The exact
committed file list is `PUBLICATION_FILES.txt`. Internal session journals,
prompts, old Git objects, game files and local captures were not exported.

## Prepare the local release assets

Python 3.11+ is required. `release/prepare_release.py` packages the reviewed
Release v100 DLLs after they are placed in `plugin/build/Release/`; it refuses
unrecognized binary hashes. It does not build or install into the game.
It generates an original empty mod descriptor and verifies installation and
restoration in a synthetic mods directory.

```powershell
& .\.venv\Scripts\python.exe release/prepare_release.py
$SourceCommit = (git rev-parse HEAD).Trim()
& .\.venv\Scripts\python.exe release/prepare_release.py --bind-source --repository CrockMr/KenshiOracle --source-commit $SourceCommit
```

Generated assets stay in ignored `dist/v0.9.5/`: the main ZIP, separate symbols
ZIP, SHA256SUMS, source manifest, build information, release notes and layout
verification. Source binding checks the native inputs in the exact commit.
The release DLLs and archived copies were scanned for the Windows user name in
ASCII/UTF-8 and UTF-16 and their CodeView PDB paths were inspected; no user name
was found, so the reviewed binaries and their hashes remain unchanged.

## Commands for the owner

No remote is configured in the freshly initialized repository. Run the following
from its root only when ready to publish; they have not been run by the agent.

```powershell
git remote add origin https://github.com/CrockMr/KenshiOracle.git
git push -u origin main
```

These commands publish the selected sources only. The release assets remain
local. Review any future source changes and never force-add game content,
captures, local configuration or internal work journals.
