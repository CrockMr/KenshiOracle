<a id="référence-originale--processus-à-froid-et-profil-re_kenshi"></a>

# Original reference: cold-start process and RE_Kenshi profile

This procedure concerns the phase 2 probe and the
`original_reference.py` controller. It describes its interface and the
conditions for a valid reference. A first real ville calme cycle, one
repetition and three snapshots using schema 0.1, is documented in the
[step 0 report](phase2-step0-validation.md).
That scope does not validate all of phase 2. Phase 1 evidence remains separate
in the [0.9.5 delivery report](oracle-phase1-delivery.md).

The profile must be prepared **before a fresh process starts**, rather than
applied live: disabling `FixRNG` does not remove hooks already installed.
See the [deviation inventory](rekenshi-deviations.md).

<a id="configuration-locale"></a>

## Local configuration

Copy [config.example.json](../config.example.json) to `config.json`, which is
ignored by Git, then adjust its paths. **All relative paths**, including the
three fields below, resolve from this configuration file's directory, not
from the terminal.

| Field | Purpose |
| --- | --- |
| `executable` | Steam 1.0.65 compatibility executable that stays active during gameplay; avoid a launcher that delegates and then exits. |
| `working_directory` | Test installation root, containing `RE_Kenshi.ini` and `settings.cfg`. |
| `rekenshi_config` | `RE_Kenshi.ini` JSON from that same installation; this path must correspond to `working_directory/RE_Kenshi.ini`. |
| `rekenshi_module` | Expected `RE_Kenshi.dll` file. The controller checks the audited 0.3.5 build and compares its path with the one reported by the process. |
| `reference_controls` | Optional, `null` by default. Local JSON with a `controls` object containing a camera/time reference for that same save. It is not a game save. |

The example assumes a neighboring `../Kenshi/` installation; the actual
1.0.65 executable may be at `../Kenshi/RE_Kenshi/kenshi_x64.exe`.
Keep `../Kenshi` as the working directory in that case.

`reference_controls` expects restoration parameters: center, quaternion
`[w,x,y,z]`, signed zoom, free mode, scrolling, a known positive speed,
pause, and optional follow target. Reuse only a reference whose provenance
belongs to the scenario save. Do not invent coordinates or a HAND to
satisfy validation. If this field is absent, the runner captures the
prepared controls after loading and rejects an unstable camera.

Also adjust `oracle_output`, `runs`, `runtime`, timeouts, and the port.
The probe and this controller use the same native output directory and
loopback port. Use a local test copy of the save; no game or recovery
file enters the source tree.

<a id="lancement-sans-mcp"></a>

## Running without MCP

Close Kenshi and cleanly stop its watchdog before calling. The controller
**rejects a game that is already running**, does not adopt it, and terminates
no unrelated process. Do not let a concurrent watchdog restart this
installation during the transaction.

From the repository root, after installing Python dependencies:

```powershell
& .\.venv\Scripts\python.exe -m launcher run-reference-scenario scenarios/ville-calme.json --repeat 5 --config config.json
```

This command launches its own game. It uses neither an external MCP client
nor an agent. `--repeat` overrides the scenario count; it accepts 1 to 100.
There is no `--prepare` option: cold-start preparation is part of the
controller.

Each run starts the game twice (reference, then restoration check), whatever
`--repeat` is, so Kenshi's launcher appears twice. Click **OK** each time, or opt in with
`"launcher_click": true`: the controller then clicks only the verified
launcher OK of its own process, once per start, and records receipts in
`launcher/` and `launcher_click` of the lifecycle report. A refusal never
fails the run by itself; click manually within `startup_grace`. See
[optional launcher automation](first-run.md#campagne-autonome-optionnelle).

The initial verifiable profile disables `FixRNG`, `UseCustomGameSpeeds`,
and the four gameplay overrides. Other persistent settings are retained
in provenance; their presence does not mean that every setting has an
independent effective-state read. The heightmap/collider paths remain
unknowns to check against the [inventory](rekenshi-deviations.md).

<a id="ce-qui-doit-être-vérifié"></a>

## What must be verified

The reference cycle prepares settings with the game stopped, starts an
owned process, and checks settings through the probe. The evidence combines
GUI controls and CRT exports; an INI file or an unchecked RNG checkbox
alone does not prove that no old hook remains active. PID, creation time,
instance, module path, and hashes bind the evidence to the process.

After cold loading and origin preparation, repetitions use the shared
runner. Captures are taken in pause and validated; the profile is rechecked
before repetitions/snapshots. A missing required capability or a lost
verification fails the reference. Historical `run-scenario` / `run_scenario`
commands without a profile cannot bypass this requirement.

At the end, the restoration target is: stop the reference process,
return to the player profile, **cold-start again to verify that profile**,
stop this verification process, then restore the exact persistent bytes.
The game must therefore finish stopped, as it started. The initial unsaved
scene is not reconstructed: it had to be closed already.
Checking options does not claim to restore an old process's internal
random sequence.

Declare success only when the scenario result and lifecycle report agree:
no cleanup errors, owned game stopped, files restored, and effective
player-profile evidence. A scenario report alone is insufficient.

Scenario results are under `runs/<scénario>/<horodatage>/`.
The controller writes its report and process outputs under
`runtime/reference-lifecycle/<identifiant>/`; its response provides
`reference_report`. Keep these data local, together with recovery journals.

<a id="récupération-après-interruption"></a>

## Recovery after interruption

Keep `runtime/rekenshi-profile.json`,
`runtime/reference-game-settings.json` and, if it exists,
`runtime/oracle-restoration.json`. Do not delete them to bypass a guard.
Close the identified game and watchdog processes before recovery.

```powershell
& .\.venv\Scripts\python.exe -m launcher restore-reference --config config.json
```

The current scope of `restore-reference` is **file restoration**;
the result states this in `recovery_scope`. That return is not evidence
of a cold restart or effective restoration. In particular, inspect the
`file_verified` and `runtime_verified` indicators in provenance.
Missing effective verification must remain explicitly missing; restoring
bytes alone does not establish it.

Recovering scenario controls is separate from recovering files.
`restore-scenario` reloads a scene and may require a ready game and
the appropriate profile context. Do not send a mutation command to an
unowned process or an unverified profile. After a recovery error, retain
the reports and address the diagnosis before another campaign.

<a id="limites-de-la-procédure"></a>

## Procedure limitations

The controller does not modify RE_Kenshi itself. Residual callbacks,
random initialization, and other non-disableable deviations remain
in provenance. They do not automatically explain every divergence.
The [first real test](phase2-step0-validation.md) validates a cold-start
cycle with reads of the six booleans/CRT exports and restoration.
Other environments, scenarios, and functions require their own evidence;
this workflow does not validate them by extension.
