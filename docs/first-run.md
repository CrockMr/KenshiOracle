<a id="première-exécution"></a>

# First run

These instructions target **KenshiProbe 0.11.0** and phase 2: the original
reference controller, additive state 0.2 and the MeitouClient comparator.
The [scene-setup block](scene-setup.md) is implemented and was first run live
on 2026-11-01 (see the release notes).
State 0.1 remains supported. Start with the [documentation index](README.md),
[field coverage](state-coverage.md) and [validation scope](phase2-validation.md).
Historical campaign reports identify the exact earlier binaries they tested;
rebuilding a release does not retroactively change those results.

## Install Python dependencies

Use Windows x64 and Python 3.11 or newer. From the repository root:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

For a prebuilt probe, use the [0.11.0 release instructions](../release/README.md).
Visual Studio is needed only to build native binaries. Install RE_Kenshi and
matching KenshiLib separately; neither the game nor its dependencies are shipped.
The validated environment is Kenshi 1.0.65 Steam compatibility mode,
RE_Kenshi 0.3.5 and KenshiLib 0.5.0. Other installations need their own validation.

## Configure native and optional research tools

No script embeds a contributor's tool installation path. Set these environment
variables in your local shell; keep their values out of Git:

| Variable | Meaning |
| --- | --- |
| `KENSHI_VCVARSALL` | Required for native build/tests: the Visual C++ 2010 `vcvarsall.bat` file. The helper requests `amd64`. |
| `KENSHI_MSBUILD` | Required for the plugin build: the selected `MSBuild.exe` file from a compatible Visual Studio installation. |
| `KENSHI_VC_TARGETS` | Required for the plugin build: the v100 `Microsoft.Cpp/v4.0` directory containing `Microsoft.Cpp.Default.props`. |
| `KENSHILIB_DIR` | KenshiLib dependency directory, containing `Include/kenshi` and `Libraries`. Defaults to `references/KenshiLib_Examples_deps/KenshiLib` relative to this checkout. |
| `BOOST_INCLUDE_PATH` | Boost dependency directory, including its `stage/lib` libraries. Defaults to `references/KenshiLib_Examples_deps/boost_1_60_0`. |
| `KENSHI_PROBE_PYTHON` | Optional Python executable for native build preparation; defaults to this checkout's `.venv/Scripts/python.exe`, then `python` on `PATH`. |
| `KENSHI_XPERF` | Optional research export tool: the matching Windows Performance Toolkit `xperf.exe`. |
| `KENSHI_WPR` | Optional research recorder: the selected `wpr.exe`. |
| `KENSHI_DBGHELP` | Optional research stack/minidump helper: a compatible x64 `dbghelp.dll`. |

Obtain the official [KenshiLib example dependencies](https://github.com/BFrizzleFoShizzle/KenshiLib_Examples_deps)
with Git LFS and follow their setup instructions. Keep headers, import libraries
and runtime DLLs consistent. A modern compiler alone cannot replace v100.
For example, collect local tool locations without putting them in a script:

```powershell
$env:KENSHI_VCVARSALL = Read-Host 'VC2010 vcvarsall.bat file'
$env:KENSHI_MSBUILD = Read-Host 'MSBuild.exe file'
$env:KENSHI_VC_TARGETS = Read-Host 'v100 Microsoft.Cpp targets directory'
$env:KENSHILIB_DIR = (Resolve-Path 'references/KenshiLib_Examples_deps/KenshiLib').Path
$env:BOOST_INCLUDE_PATH = (Resolve-Path 'references/KenshiLib_Examples_deps/boost_1_60_0').Path
$env:KENSHI_PROBE_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
cmd /d /c plugin\build-v100.cmd
cmd /d /c tests\test-oracle-format-v100.cmd
```

The scripts locate source/output directories relative to themselves, rather than
the caller's current directory. Outputs are `plugin/build/Release/` and
`plugin/build/native-tests/`, both ignored. The checked dependency preparation
uses `KENSHILIB_DIR`, applies only recognized SDK declaration fixes and refuses
an unexpected revision. It does not patch game instructions or guessed layouts.
For a direct Visual Studio build, run `plugin/prepare_deps.py` first, retain
`v100`, select `Release|x64` and reject automatic retargeting. The optional
bootstrap additionally needs compatible VC2010 ATL/MFC headers/libraries/runtime.

## Install and configure the original target

Close the game, back up any existing `mods/KenshiProbe/`, then install both
new DLLs, `RE_Kenshi.json` and the original empty `.mod` from the reviewed
archive. Enable the mod in the launcher. The bootstrap is inactive without
an explicit activation file; see the optional section below.

Copy [config.example.json](../config.example.json) to ignored `config.json`.
Set the gameplay executable, working directory, `rekenshi_config`,
`rekenshi_module`, save/output locations, logs and timeouts for your local
test installation. Relative paths resolve against the configuration file.
The example's `../Kenshi` is a neighboring installation, not a required layout.
Supervise the executable that remains active during gameplay, rather than an
intermediate launcher. Use a local test copy of each save outside Git.

The native port is `127.0.0.1:47800`. `KENSHI_PROBE_CONFIG` selects the Python
configuration file. The owned process receives `KENSHI_PROBE_PORT` and
`KENSHI_ORACLE_OUTPUT` from the controller/watchdog. Manual launches must use
matching values; changing a configuration does not change an existing process.

<a id="scénarios-sans-client-mcp-ni-agent"></a>

## Original reference without MCP

Stop Kenshi and its watchdog before starting. The controller owns a cold
process; it rejects an already-running game and does not adopt unrelated ones.
Adapt [the scenario example](../scenarios/README.md) to a real local save:

```powershell
& .\.venv\Scripts\python.exe -m launcher run-reference-scenario scenarios/ville-calme.json --repeat 5 --config config.json
```

It backs up settings, disables `FixRNG`, `UseCustomGameSpeeds` and the four
gameplay overrides, then verifies effective GUI and CRT observations. It
loads the scenario, prepares saved origins, captures stable controls in pause,
repeats, validates/canonicalizes/hashes each snapshot and restores the recorded
controls. Finally it restores and cold-verifies the player's RE_Kenshi profile,
restores exact configuration bytes and stops its process. Known permanent
RE_Kenshi changes remain [documented deviations](rekenshi-deviations.md).

The result names `report.json`, `report.md` and the snapshot directory under
`runs/`. Keep requested/actual checkpoint times and restoration evidence.
Do not interact with the game during the transaction. The starting save and
prepared controls are the restoration scope; an earlier unsaved game is not
reconstructed. [The complete reference procedure](original-reference.md)
explains provenance, fixed restoration tolerances and interruption recovery.
The historical `run-scenario --prepare` route cannot bypass the reference-profile
requirement of the current original probe.

For MCP, configure the client to launch `.venv/Scripts/python.exe` with
`mcp-server/server.py` and a local `KENSHI_PROBE_CONFIG`. Use the client's
resolved absolute executable/configuration paths locally, without committing
them. `ping` must identify plugin version `0.11.0`, state 0.2 with 0.1 support,
the expected game versions and a stable instance ID. `dump_state()` validates
its returned snapshot. The [protocol](protocol.md) describes manual tools;
those calls alone do not certify an original reference campaign.

## Meitou and comparison

Apply the [pinned adapter patch series](../integrations/meitou/README.md) to a
separate upstream checkout. The adapter is opt-in behind `--oracle`; the
normal game remains opt-out. Follow [target setup](meitou-target.md), including
the required .NET SDK, separate port `47801`, private preferences and seed
provenance. Do not install or upgrade an SDK as part of running this repository.

After both targets complete and restore their campaigns:

```powershell
& .\.venv\Scripts\python.exe -m launcher compare ORIGINAL_REPORT MEITOU_REPORT OUTPUT
```

The default minimum is five repetitions per target. The
[comparator guide](comparator.md) defines tolerances, the six classes,
unknown coverage and the limits of sampled trajectories/combat. Reports and
English issue drafts remain local; creating a draft never publishes an issue.

## Recovery and offline tests

Retain every journal with `restore_required:true`; do not delete it to bypass
recovery. With all original-game processes stopped, recover exact settings
bytes through the reference controller:

```powershell
& .\.venv\Scripts\python.exe -m launcher restore-reference --config config.json
```

That emergency file recovery does not itself prove effective runtime settings.
For a scenario control journal, use `restore-scenario --config config.json`
after the correct target is available; the journal and
[reference guide](original-reference.md) determine the appropriate recovery.
An uncertain mutation is not retried automatically. Acknowledgment of a
watchdog restart is not proof that a save is ready.

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

The suite uses synthetic data, fake processes, loopback sockets and subprocesses;
it refuses real probe ports 47800 and 47801. Optional local-capture tests may
skip in a public clone. Native `tests/test-*-v100.cmd` use the environment
variables above. Manual `tests/live_*.py` checks require an identified test
installation and are excluded from pytest. Performance captures and diagnostic
utilities are separate [research tools](../tools/research/README.md), not part
of ordinary scenario setup.

<a id="campagne-autonome-optionnelle"></a>

## Optional launcher automation

The bootstrap is inert by default. An explicitly created
`mods/KenshiProbe/auto_launch.enabled` accepts a positive Unix UTC deadline
or the exact word `unlimited`. Malformed, absent, empty, oversized, signed,
overflowing or expired values leave the launcher interactive. `unlimited`
requires explicit authorization for that launch session. The file is read
once when the bootstrap loads; removal affects subsequent launches.

Unless `auto_launch.enabled` is set, click **OK** in Kenshi's launcher
yourself after each owned start. Alternatively, set `"launcher_click": true` (default `false`) and
the reference controller and watchdog click it from outside the game, once per
owned start. Only a visible `#32770` dialog of the owned PID, titled `Kenshi`
or `Kenshi 1.0.65 - x64 (Newland)`, with a single enabled `OK` button of
control id 1003, is clicked; any other dialog, a PID/executable mismatch, a
duplicate button or a timeout (`startup_grace`) refuses and leaves the
launcher open for a manual click. Each start writes a JSON receipt under
`launcher/` in the lifecycle output (reference runs, also in `report.json`
as `launcher_click`) or in `launcher/` under the configured `runtime` folder
(watchdog). Observed: the same
clicking rule accepted and closed the runtime-titled launcher on Kenshi 1.0.65
Steam with RE_Kenshi 0.3.5 in private campaign harnesses; this public wiring
is covered by offline tests only, and other builds are untested (**Unknown**); a dialog that does not match the rule above is refused.
Do not combine it with `auto_launch.enabled`. The Meitou watchdog rejects
the switch.

`startup_save` lets a standalone watchdog request one initial load. It does
not replace origin preparation, profile verification or scenario restoration.
`session_until` separately bounds watchdog supervision; Ctrl+C stops its owned
game. Keep only one supervisor. Remove the activation file and reset
`startup_save` to restore interactive behavior on later launches. Historical
autoload/restart evidence is indexed in [validation](research/validation.md).
