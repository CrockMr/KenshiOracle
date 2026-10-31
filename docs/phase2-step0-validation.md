<a id="phase-2-étape-0--validation-du-profil-original-à-froid"></a>

# Phase 2, step 0: cold-start validation of the original profile

**Observed on 29 October 2026:** a `run-reference-scenario` cycle for
`ville-calme` completed **one repetition and three snapshots**, with the
RE_Kenshi profile verified, restoration of the player profile verified after
a fresh start, the game stopped again, and protected files unchanged.

This validation authorizes further work on the shared contract. It does not
validate the MeitouClient adapter, format 0.2, or the comparator.
The snapshots for this milestone still use schema **0.1**. **N = 1** cannot
assess variability or establish parity between engines.

<a id="sources-et-preuves-locales"></a>

## Sources and local evidence

The relevant code is the [process controller](../mcp-server/original_reference.py),
the [profile transaction](../mcp-server/rekenshi_profile.py), its
[native read service](../plugin/ReKenshiSettings.h), and the
[shared runner](../mcp-server/oracle_runner.py). The
[usage guide](original-reference.md) describes the procedure.

The following links refer to **local evidence ignored by Git** in the
validation checkout; those files are not distributed. This report retains
the facts needed to understand it without those files:

- [Acceptance and preservation checks](../../phase2-live-step0/acceptance.json).
- [Cold-start cycle and restoration report](../../phase2-live-step0/runtime/reference-lifecycle/3c11a806a9b1476c9c653625a9767b5d/report.json).
- Scenario report (local evidence, not published).

No snapshot, game data, save, or personal configuration is copied into this
report or the public source tree.

<a id="profil-effectif-et-restitution"></a>

## Effective profile and restoration

The process starts with the **game stopped**. The measurement profile
disables the following six booleans; each is read from the RE_Kenshi GUI
controls, with evidence bound to the PID, instance, and audited module:

| Option | Measurement | Restored player profile |
| --- | --- | --- |
| `FixRNG` | false | true |
| `UseCustomGameSpeeds` | false | false |
| `AttackSlotsOverride` | false | false |
| `MaxFactionSizeOverride` | false | false |
| `MaxSquadSizeOverride` | false | false |
| `MaxSquadsOverride` | false | false |

The recorded method is `rekenshi_0_3_5_ui_and_crt_exports`.
During measurement, the loaded prefixes of both CRT exports, `rand` and
`srand`, match their bytes on disk; the evidence reports
`crt_exports_unmodified=true` and `effective_fix_rng_disabled=true`.
This observation goes beyond reading the INI file or a GUI checkbox alone.

After restoring the options and **cold-starting the player profile again**,
`FixRNG=true` and both exports are observed to be modified:
`crt_exports_modified=true`, with consistent settings.
The final journal reports `state=restored`, `restore_required=false`,
`file_verified=true`, `runtime_verified=true`, and no pending byte
reapplication. The lifecycle report retains `cleanup_errors=[]`,
`owned_game_stopped=true`, and `completed=true`.

This does not restore the previous internal RNG sequence. The residual
x2/x5 callbacks and the other [documented deviations](rekenshi-deviations.md)
remain separate; their presence does not automatically explain a divergence.

<a id="photos-et-conservation-des-fichiers"></a>

## Snapshots and file preservation

| Checkpoint | Characters | Squads | Factions | Relations |
| --- | ---: | ---: | ---: | ---: |
| Initial | 111 | 22 | 114 | 12 882 |
| Two minutes | 111 | 22 | 114 | 12 882 |
| Ten minutes | 143 | 26 | 114 | 12 882 |

All three files were reread outside the game: schema **0.1** accepted,
SHA-256 matching the report, Python canonicalization identical to the
captured bytes, and equality with native output. These checks do not prove
engine determinism.

Acceptance confirms restoration of the **RE_Kenshi.ini bytes**,
**settings.cfg**, and the **previously installed DLL**, and preservation of
**four protected saves**. File evidence remains local; its contents are not
included in the repository.

<a id="build-natif-identifié"></a>

## Identified native build

The Release x64/v100 test DLL has SHA-256:

`aded1a235446af9aba5a341d8c0f77a9476cbfd2b22a9fbf8eec4a2e03b99ebe`

Its CodeView record contains only the name `KenshiProbe.pdb`, without a
personal path; the [project](../plugin/KenshiProbe.vcxproj) enforces
`/PDBALTPATH:KenshiProbe.pdb`. This concerns the PDB reference embedded in
the DLL; this milestone publishes no private symbol file.

<a id="limites-encore-ouvertes"></a>

## Remaining limitations

- Three snapshots from one repetition of ville calme, without a
  MeitouClient comparison or a five-repetition statistical campaign.
- Effective reading verified for the six booleans and CRT export
  consistency, not exhaustive equivalence of all RE_Kenshi functions.
- The heightmap/collider paths and causal attribution of residual effects
  retain the certainty levels described in the deviation inventory.
- Additive schema 0.2 and its new identities/groups require their own
  evidence; the results of this milestone are not reassigned to them.
