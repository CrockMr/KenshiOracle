<a id="ville-calme--validation-complémentaire-du-29-octobre-2026"></a>

# Quiet town: additional validation on October 29, 2026

> Historical report. The [0.9.5 delivery summary](oracle-phase1-delivery.md) and [acceptance checklist](phase1-acceptance.md) describe final sources, tests and validations; the results below retain their original version and scope.

The user's `ville-calme` save was replayed **three times**, producing nine state-0.1-compliant captures and verified control restoration, including following character Imai. The DLL remains **0.9.1**; the fix concerns the Python server. The complete suite finishes with **1 310 tests passed in 65,16 s**. Agents in this batch use GPT-6.1 Sol, ultra effort.

All three examples now have a successful three-repetition series: travel, battle and town, totaling 27 captures for these series. Earlier attempts are not retroactively validated by the new stability check. No performance campaign was run.

<a id="preuves-locales"></a>

## Local evidence

Large files and game data remain outside Git. Evidence for this batch:

- `runtime/oracle-phase1/city-preflight-091.json`: initial state and fingerprints of four protected saves, including the 54 `ville-calme` files.
- `runtime/oracle-phase1/live-ville-calme-stable-091.json`: MCP stdio validation, nine hashes, unchanged process identity, checked settings and saves.
- `runs/ville-calme/20261029T001325.437085Z-06ebaeea/report.json` and `report.md`: three executions, nine captures and field comparison.
- `runtime/oracle-phase1/city-final-audit-091.json`: controls rechecked after the experiment, active pause, no pending restoration, exact settings and four unchanged saves.

All nine captures were schema-validated and their bytes compared with native sources and Python canonicalization. The game is Kenshi 1.0.65 Steam, instance `34736:1222705718`, plugin 0.9.1. Every repetition reloads the save; no character action is sent. Checkpoints are 0, 120 and 600 **game-calendar seconds**, not real seconds.

<a id="résultats-et-variabilité"></a>

## Results and variability

| Checkpoint | Characters, repetitions 1 / 2 / 3 | Squads, repetitions 1 / 2 / 3 | Stable fields | Variable fields |
| --- | --- | --- | ---: | ---: |
| Initial | 101 / 103 / 110 | 22 / 22 / 22 | 42 029 | 2 945 |
| 120 s | 101 / 103 / 110 | 22 / 22 / 22 | 41 802 | 3 436 |
| 600 s | 123 / 125 / 131 | 26 / 25 / 26 | 42 241 | 4 707 |

Every capture contains 114 factions and 12 882 directional pairs. Variable-field counts include presence and absence: they are neither probabilities nor counts of independent entities.

Imai retains identity `hand:1:1:751953152:1:3279785216`, his squad and the same state across repetitions at each checkpoint. He remains alive with a null current task. His x/z coordinates remain `-50978.796875, 2932.476563`; y changes from `1531.995850` initially to `1533.468262` at the next two checkpoints. This proves neither complete three-dimensional immobility nor world determinism.

| Repetition | Overshoot at 120 s | Overshoot at 600 s |
| --- | ---: | ---: |
| 1 | 0,145797 s | 0,227737 s |
| 2 | 0,296859 s | 0,073242 s |
| 3 | 0,166397 s | 0,368499 s |

The plugin pauses at the first observed crossing. Overshoots remain in reports; they are not hidden by replacing actual times with requested times.

<a id="correction-de-la-vérification-caméra"></a>

## Camera-verification fix

The first attempt, `20261029T000108.688978Z-ed2aa999`, produced three repetitions and nine captures, but the runner correctly retained it as **failed**: the camera center differed by `0.17248535156295475`, beyond the 0,05 threshold. This attempt and its report are preserved.

Previously, code checked only one read after restoration. `wait_stable_controls` now observes distinct frames for at least 0,5 second, with at least three frames and a ten-second deadline. It brackets reads with identity/readiness checks, requires a stationary clock and retains observations. The reference is captured paused before arming the journal, then remains fixed. A stable pose differing from that reference fails; uncertain mutations are never retried.

Thresholds remain: 0,05 for center, position and zoom, 0,0001 for quaternion, 0,000001 for selected speed. An unknown selection is not treated as zero. Verification happens after native camera-lock release; it does not neutralize user input or guarantee future immobility.

Diagnosis had observed an SDK pointer at the edge and orientation changes. Windows interactions with the pause banner then placed input inside the window; movement stopped in subsequent reads. This observation alone does not prove the cause of the initial difference. These interactions sent no move or attack order.

Explicit recovery of the first attempt succeeded without changing its reference, evidence `runtime/oracle-phase1/city-recovery-stable-091.json`. The next series uses the new check from the start. Its initial window validates six frames over 0,625 second; restoration validates five over approximately 0,531 second. Center, position and quaternion differences are **zero in the report's final read**. Following Imai, signed zoom `-1181.855224609375`, strategic mode, enabled scrolling, pause and prepared speed selection 1 are verified. This validates this follow case, not every possible mode or offset.

The final audit confirms the same controls in a fresh window after file validation. It leaves `ville-calme` reloaded and paused; it does not claim to reconstruct a transient view or an unsaved game from before preparation.

<a id="pnj-générés-ou-identité-déplacée"></a>

## Generated NPCs or shifted identity

The [identity audit](npc-identities-phase1.md) distinguishes two cohorts. In this town, the 80 initially common identities exactly match saved characters. Initially variable members belong to three squads recorded as never activated, without saved individual states: generation on activation is strongly supported. At 600 seconds, the 92 individually saved characters occur in every repetition.

For the earlier Ando, Hisako and Ishida, matching individual states already exist in the save. Their container components change in captures. They therefore do not prove complete creation on loading. Engine alias resolution and a canonical origin identity still need implementation and verification; exported state uses neither name matching nor index/serial-only matching.

<a id="vérifications-et-limites"></a>

## Checks and limitations

The complete suite ran with fake-server sockets, under a guard blocking the real game port:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/oracle-phase1/pytest-city-full-20261029
```

Result: **1 310 passed, 65,16 s**. The MCP, runner and examples subset had previously passed 64 tests. This Python fix required no new native build; only a TODO comment was added to the identity adapter.

Still unvalidated here: other follow modes/offsets, general identity persistence after restart, completeness of all engine memory, worker atomicity and new real crashes/freezes. Offline watchdog tests and historical evidence are retained. The MeitouClient adapter and cross-engine comparator remain outside phase 1.

The three native-code TODOs are `ORACLE-IDENTITY-REMAP` (stable origin and aliases), `ORACLE-ORDER-ENUM` (future task types unknown to the SDK) and `ORACLE-CAMERA-NONCHARACTER` (following an object other than a loaded character). See [open questions](research/open-questions.md).
