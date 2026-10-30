<a id="cible-meitouclient"></a>

# MeitouClient target

The local fork uses branch `oracle-adapter-08340c7` (base `08340c72`; the earlier
`oracle-adapter` branch on `1df44934` is kept as a backup), activated only by `--oracle`.
It does not provide a plugin/modding API. Its `docs/oracle.md` describes the
seam and limits; the [durable-fork design](meitou-oracle-design.md) specifies
maintenance. The supervised workflow below uses the project's Windows watchdog.

**Verified outside the game:** Release build with .NET 10.0.403, no errors or
warnings, 115 passing focused Oracle/camera tests and 62 shared canonical
vectors, including 59 historical cases. **Observed:** a first real paused 0.2
snapshot validates with seed 1729, owned process stopped and protected files
unchanged; [coverage](state-coverage.md#extension-additive-02) gives the
measurements and local evidence. Quiet town subsequently completed **N = 5,
15 snapshots**, seeds 0..4, with controls and initial seed restored;
battle and travel each completed N = 1, three snapshots and restoration,
for **21 Meitou snapshots** in total. These scopes establish neither general
scenario compatibility nor parity. Success of the
[original profile](phase2-step0-validation.md) remains separate evidence.
The [functional and comparison report](phase2-validation.md) collects this
evidence and test-suite limitations.

<a id="configuration-et-lancement"></a>

## Configuration and launch

Copy [config.meitou.example.json](../config.meitou.example.json) to
`config.meitou.json`, ignored by Git. Adapt `executable`,
`working_directory`, `game_install`, `log` and `dump_directory` to the built
fork. The example assumes a neighboring MeitouClient folder. All paths resolve
from the configuration file.

In the main `config.json` used by CLI and MCP, add:

```json
{ "meitou_config": "config.meitou.json" }
```

This field points to the separate configuration; replace neither the original
target's port nor runtime. The Meitou target must declare `"target":"meitou"`,
use a distinct port (47801 by default) and its own `runtime`, for example
`runtime/meitou`. `state_schema:"0.2"` requires the additive contract.
`game_install` supplies `KENSHI_PATH` to the child process.

The supervisor reads `meitou.user.json` preferences from the configured
directory or executable directory, then places a copy in
`runtime/meitou/game-work/`. The process works on this private copy; player
preferences are not its write destination. Configuration-field paths resolve
from the JSON; paths added to `arguments` retain the executable's semantics
and this private working directory. Prefer `startup_save` for startup loading.

Close MeitouClient before launching in a dedicated terminal:

```powershell
& .\.venv\Scripts\python.exe -m launcher.meitou_watchdog --config config.meitou.json
```

This supervisor supplies `--oracle`, `--oracle-port` and `--oracle-output`
itself; do not add them to `arguments`. It rejects an already running
MeitouClient, owns its process and uses the heartbeat published by the host.
`startup_save` requests one load per launch. It can restart its process after
a freeze/exit; it does not resume an interrupted experiment. Keep the
supervision terminal open while running the following commands.
The [real supervisor test](phase2-validation.md#campagnes-et-restitution)
covers startup, heartbeat and owned shutdown; no real Meitou crash was
triggered for this evidence.

<a id="cli-et-outils-communs"></a>

## CLI and shared tools

After startup and loading finish, from the KenshiOracle root:

```powershell
& .\.venv\Scripts\python.exe -m launcher run-scenario scenarios/ville-calme.json --target meitou --repeat 5 --config config.json --prepare
& .\.venv\Scripts\python.exe -m launcher restore-scenario --target meitou --config config.json
```

The second command performs recovery if a journal requires it; it does not
rerun the scenario. `prepare-scenario` also accepts `--target meitou`.
`--prepare` reloads the exact save and establishes x1 in pause before capturing
the restoration reference; an earlier unsaved game is not reconstructed.
Use a local test copy, with identical data/mods on both engines and saved
HANDs actually present.

The following MCP tools accept `target="meitou"`; their default remains
`"original"`:

| Use | Tools |
| --- | --- |
| State | `ping`, `heartbeat`, `get_clock`, `dump_state` |
| Time and orders | `pause`, `set_game_speed`, `run_until`, `run_until_status`, `cancel_run_until`, `issue_order` |
| Loading and controls | `load_save`, `get_scene_state`, `set_camera_free`, `prepare_scene_control`, `commit_scene_control`, `restore_scene_control` |
| Scenario and recovery | `run_scenario`, `restore_scenario` |

Historical tools without this parameter remain specific to the original;
assume neither native telemetry nor equivalent scene creation in Meitou.
`get_scene_state(thread_details=True)` is not implemented by the adapter.
An absent command returns `not_implemented`.

<a id="seed-résultats-et-reprise"></a>

## Seed, results and recovery

`base_seed` is an unsigned 64-bit integer or its decimal string. Repetition
number `i` receives `base_seed + i - 1`, with no overflow permitted. The
runner checks the effective seed and its application before loading;
each repetition/snapshot retains it in provenance outside common state.
Saved seed settings are replaced only in the adapter's loaded in-memory
copy. A known seed does not eliminate asynchronous-service timing effects.

Results retain the layout
`runs/<scénario>/<horodatage>/<répétition>/`, with `report.json` and `report.md`.
Restoration reloads the starting save with the **initial seed**, then verifies
recorded camera/time controls. It does not reconstruct an internal RNG
sequence already consumed. Journal `runtime/meitou/oracle-restoration.json`
remains necessary on failure; after restarting, use
`restore-scenario --target meitou` before trying again. Watchdog restart alone
does not perform this restoration.

Town fields remain unknown, local identities cannot be individually matched
and some 0.1 fields are null; see [0.2 coverage](state-coverage.md#extension-additive-02).
These commands alone establish no statistical result between engines.
Once both campaigns finish and restore, use the
[comparator that certifies its inputs](comparator.md), without contacting games.

<a id="vecteurs-canoniques-c-partagés"></a>

## Shared C# canonical vectors

C# tests use their local fixture if present. To test KenshiOracle's shared
file directly, or if that copy is absent, run from the fork root and adapt
the relative path between repositories:

```powershell
$env:KENSHI_ORACLE_VECTORS = (Resolve-Path ../KenshiOracle/schema/canonical-vectors.json).Path
dotnet test -c Release tests/Meitou.Tests/Meitou.Tests.csproj --filter "FullyQualifiedName~Meitou.Tests.Oracle.OracleCanonicalJsonTests"
Remove-Item Env:KENSHI_ORACLE_VECTORS
```

The fixture identity is the SHA-256 of its content with CRLF normalized to LF,
`d41b18288b8510e379ff7bcc62212d018ec75fe80edfa045f8c2df2b17a03cad`, checked by both
KenshiOracle and the C# tests, so CRLF and LF checkouts agree without a Git setting.
The exact name read by tests is `KENSHI_ORACLE_VECTORS`. The 62 cases include
the 59 historical ones; selecting another file does not authorize changing
expected bytes to make a capture pass.
