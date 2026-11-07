<a id="cible-meitouclient"></a>

# MeitouClient target

The [patch series](../integrations/meitou/README.md) now targets base
`88ae71a1` (branch `oracle-adapter-88ae71a` in its README). The evidence below
was obtained on branch `oracle-adapter-100c6ca` (base `100c6cae`); the adapter
is activated only by `--oracle`. Earlier branches (`oracle-adapter-08340c7`, `oracle-adapter`
on `1df4493`) may be kept as backups.
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
`runtime/meitou`. `state_schema` defaults to `"0.5"` and requires that
contract; an adapter without state 0.5 (series before patch 0008) needs
`"state_schema":"0.4"` (`"0.3"` before patch 0007, `"0.2"` before patch 0006)
here and in `config.json`,
because the comparator never compares two state schema versions. The same
holds in two other cases: an adapter against a probe that lacks its version
(the 0.11.0 probe has state 0.2 only; 0.12.0 has 0.1 to 0.5), and an old
`config.meitou.json` that still says `"0.2"`, `"0.3"` or `"0.4"` against a
probe with a later state. The comparator refuses the mismatch only after both campaigns have
run, so set the same `state_schema` explicitly in both files before a
campaign.
`game_install` supplies `KENSHI_PATH` to the child process.
When `config.meitou.json` has no `engine_profile`, it uses the one from
`config.json`: one local profile may hold both targets' entries, because
lookups are keyed by target.

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

<a id="live-two-target-tools"></a>
### Live two-target tools

With both games open, each under its own supervisor, three MCP tools work on
both targets at once. They need no plugin or adapter change: they combine the
existing commands.

| Tool | What it does |
| --- | --- |
| `step_both(advance_seconds=None, target_seconds=None, timeout_seconds=120)` | Runs `run_until` on both targets concurrently to the same absolute game-clock time, then both are paused. `advance_seconds` is added to the later of the two current clocks. Returns both reached clocks, their difference and any per-target error; one target's failure does not hide the other's result. |
| `compare_now(fields=None, limit=20, position_tolerance=0.000001)` | Captures both paused games concurrently (two ordinary `dump_state` snapshots under each target's `runs/dumps/`), pairs saved characters by complete handle and returns only the fields that differ, per field and per pair. `fields` filters by whole field-path prefix, for example `["goal", "order/type", "health"]`. |
| `inspect_both(saved_id)` | One saved character (`hand:1:…`) or squad (`hand:34:…`) from the pair kept by the last `compare_now`, both raw rows side by side, plus the differing fields. It captures nothing new. |

`compare_now` uses the campaign comparator's per-character fields
(`oracle_compare.character_fields`), so a live difference names the same field
as a campaign metric. A `null` on one side is unknown: it is counted under
`not_comparable_fields`, never listed as a difference. Unsaved (generated)
characters are not paired. Before `step_both`, set a positive speed on each
target since its last load (`set_game_speed(speed=1, preserve_pause=True)`).

**Limits.** One pair of snapshots is one observation. It shows where two runs
stand at that moment, not whether a difference is stable, variable or a known
deviation; campaigns with repetitions classify. The two engines do not draw
the same random numbers, so pairs taken long after a load mostly show
divergent histories rather than single rule differences. MeitouClient stops
on whole ticks, so its clock can be up to about 1.1 calendar seconds past the
original's. The kept pair lives in the MCP server process only and is lost
when it restarts.

**Observed** (2026-11-07, one local session, save `oracle-base-cage-blesse`,
original probe state-0.5 build 8221ba1, MeitouClient adapter 0.12.0): loading
took about 22 s on each target, a paired 120-second advance ended at
124380.0 and 124381.0, each capture took about 7 s (about 1 MB), and all 54
saved characters of the original snapshot were found among the 128 of
MeitouClient's. That run used the commands one by one.

**Observed** (2026-11-07, a second session, same save and builds, the three
tools above): right after the load, `compare_now` paired 54 saved characters
(74 only in MeitouClient) with clocks 0.0045 s apart. `step_both(advance_seconds=120)`
ended at 124380.12 and 124381.00. `compare_now(fields=["goal", "order/type", "health"])`
then listed 24 pairs with differences (goal type 10, order type 10), and
`inspect_both` returned both rows for one character and for one squad. For a
squad it lists no differing fields, because the comparator fields are
per-character. One `inspect_both` result for a character is about 8 KB, most
of it the stats block.

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
`99f4bfee37ee2c953c7dc34954d8d525e5f116564dcfda11c67bb2ab0f8c1484`, checked by
KenshiOracle, so CRLF and LF checkouts agree without a Git setting. Patch 0008
carries this 74-case fixture copy and pins this identity in its C# test. Patch
0007 carries the earlier 69-case fixture copy and pins its identity
`cd935563cb97f247ca7021a6bc1215d76bf21c01382e8d544783e4c138447f63` in its C#
test, patch 0006 the 65-case identity
`06a63911f1375ec5d19027c261a1bd066f2a4682c84add7f0e84ce3f434b2170`, and series
before it the 62-case identity
`d41b18288b8510e379ff7bcc62212d018ec75fe80edfa045f8c2df2b17a03cad`. The exact name read by tests is
`KENSHI_ORACLE_VECTORS`. The 74 cases include the 59 historical ones, three
state 0.2 cases, three state 0.3 cases, four state 0.4 cases and five state 0.5 cases; selecting another file does not authorize changing
expected bytes to make a capture pass.
