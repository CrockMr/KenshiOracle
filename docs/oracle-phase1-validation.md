<a id="validation-de-loracle-phase-1--29-octobre-2026"></a>

# Phase 1 oracle validation — October 29, 2026

> Historical report. The [0.9.5 delivery report](oracle-phase1-delivery.md) and [acceptance checklist](phase1-acceptance.md) describe final sources, tests and validations; the results below retain their initial version and scope.

Later supplement: [quiet town and the camera-control fix](oracle-ville-calme-validation.md) bring successful series to nine repetitions and 27 captures, and the Python suite to 1 310 passes. The [NPC audit](npc-identities-phase1.md) distinguishes generation on activation from container changes for saved entities. The measurements below remain historical; they are not retroactively subjected to the new stability window.

Probe **0.9.1**, with state and scenario contracts **0.1**, executed three real `trajet-escouade` repetitions, then three `petite-bataille` repetitions through the stdio MCP server. All **18 captures** from these two successful campaigns conform to the schema, and their bytes exactly match Python normalization and native source files. Movement, attack orders, wounds and restoration of scenario-specific controls are observed under the conditions detailed below. Final return to the pre-phase camera pose is nevertheless **not validated exactly**. Full states differ across repetitions: this validation does not demonstrate universal Kenshi determinism. A first battle trial that ended in restoration failure remains separately retained.

<a id="périmètre-et-preuves-locales"></a>

## Scope and local evidence

The observed game is Kenshi **1.0.65 Steam**, plugin **0.9.1**, instance `34736:1222705718`. The campaign starts on October 28, 2026 at 23:31 UTC, October 29 in Paris time. It is not a performance campaign. Large evidence remains in local directories ignored by Git:

- `runtime/oracle-phase1/live-trajet-091.json`: MCP result, process identity at boundaries, nine capture hashes, before/after controls and protected-save verification.
- `runs/trajet-escouade/20261028T233134.179400Z-04bb9a8d/report.json` and `report.md`: executions, loads, actions, actual times and field-by-field comparison.
- In the same directory, `scenario.json`, then `1/`, `2/`, `3/` with captures `initial.json`, `en-route.json`, `arrivee.json` and `execution.json` journals.
- `runtime/oracle-phase1/first-real-dump.json`: first real-capture evidence, preceding the repeated campaign.
- `runtime/oracle-phase1/native-canonical.json`: C++/Python format comparison on 59 synthetic states, separate from real captures.

The archived scenario reloads `KenshiProbe_test` on each repetition, selects speed 1, issues a `move` order at time 0 to squad `hand:34:1:3701293824:0:0`, then captures at times 0, 120 and 600. Actions at the same time precede capture: `initial` therefore already contains the movement order. A pause command at 600 precedes the last capture. Every time is a duration in **game-calendar seconds** from the clock read after this reload, not wall time.

<a id="mouvement-et-identités-observées"></a>

## Observed movement and identities

Both characters retain their identity, squad and initial position in all three repetitions:

| Character | Identifier | Initial position x, y, z |
| --- | --- | --- |
| Ryers | `hand:1:1:3701293824:1:1415283200` | `50533.593750, 1005.236938, -13895.199219` |
| Okada | `hand:1:1:3701293824:2:1858032256` | `50540.773438, 1005.285950, -13891.675781` |

Their initial task is `move_cus_ordered`, with requested destination `50573.593750, 1005.236938, -13895.199219`. Their position changes before checkpoint 120; their task is then `null`. In each repetition they remain at that position at checkpoint 600 and are alive. This establishes an in-game effect of the order beyond simple acknowledgment. It does not claim every member reaches the exact destination coordinates.

| Repetition | Ryers' horizontal displacement | Okada's horizontal displacement | Ryers' final horizontal distance to target | Okada's final horizontal distance to target |
| --- | ---: | ---: | ---: | ---: |
| 1 | 39,164 | 23,438 | 1,502 | 9,792 |
| 2 | 38,934 | 24,110 | 1,741 | 9,094 |
| 3 | 39,993 | 24,718 | 0,983 | 8,468 |

Distances are in world-coordinate units, calculated over x/z. The maximum difference between final positions in three dimensions is 1,136 for Ryers and 1,325 for Okada. At arrival, only their three position fields vary across repetitions; the other fields in their records are stable in this report.

Identity stability remains limited to the cohort actually observed and these reloads in the same instance. Initially, all three captures contain 106 characters but only **103 shared identifiers**; their union contains 112. The 35 squads per capture have 32 shared identifiers, 41 in the union. Three rows named Ando, Ishida and Hisako respectively have a different `containerSerial` on every reload, as does the associated squad. Their cause is not established: they are not merged by name, and no claim is made that they have been proven new entities. Stability after restarting the game remains to be checked.

<a id="variabilité-et-temps-réel-des-captures"></a>

## Variability and actual capture times

| Checkpoint | Characters, repetitions 1 / 2 / 3 | Squads, repetitions 1 / 2 / 3 | Stable fields | Variable fields |
| --- | --- | --- | ---: | ---: |
| initial, 0 s | 106 / 106 / 106 | 35 / 35 / 35 | 42 922 | 511 |
| en-route, 120 s | 106 / 106 / 106 | 35 / 35 / 35 | 42 239 | 1 377 |
| arrivee, 600 s | 181 / 180 / 180 | 64 / 65 / 70 | 44 815 | 2 329 |

These numbers count comparator value paths, not independent characters or a success probability. The report distinguishes differing values from an absent entity. Respectively 450, 438 and 1 185 variable paths include at least one absence. At arrival, 170 character identifiers are shared by all three captures, from a union of 196; loaded populations are therefore not interchangeable.

All nine captures contain the same 114 factions and 12 882 directional pairs. No relation varies across repetitions at checkpoints 0 and 120. At 600, the value from `1085-gamedata.base` to `56098-rebirth.mod` is `-0.03875`, `-0.0425`, `-0.03875`. The faction set is stable; this does not make every relation constant.

| Repetition | Overshoot at 120 s | Overshoot at 600 s |
| --- | ---: | ---: |
| 1 | 0,156097 s | 0,073242 s |
| 2 | 0,094299 s | 0,244903 s |
| 3 | 0,204162 s | 0,169372 s |

`run_until` stops at the first crossing observed on the main thread; it does not impose a simulation step split exactly at the threshold. The maximum overshoot in this campaign is therefore **0,244904 game-calendar seconds**, rounded upward to six decimals. The initial residual of about `1.82e-7` seconds comes from comparing the unquantized clock with its six-decimal canonical representation; it is not observed progression at time 0. Every capture is paused with `clock.speed = 0`.

<a id="restitution-et-sauvegardes"></a>

## Restoration and saves

The runner report states `restoration.verified: true`, then the external MCP record confirms `settings_restored_exactly: true`. Before/after values are equal for pause, known selected speed, camera mode, edge scrolling, center, position, quaternion, node-local position, zoom and followed target. This verification's values are: paused, selection 1, free mode disabled, scrolling enabled, signed local zoom `-1887.5`, followed target `null`.

The signed-zoom and camera-operation-order fix is therefore observed on this pose without following. Character following and other camera modes are not validated by this campaign. Selection 1 had been explicitly established with `set_game_speed(1, preserve_pause=True)`; no public getter can infer an unknown prior selection. Control restoration and reloading the scenario save do not restore an unsaved game.

The control record establishes that saves `KenshiProbe_validation`, `KenshiProbe_test` and `KenshiProbe_test_scene_20261028T022539600581Z` are unchanged. It does not establish equality of all installation files.

<a id="bataille-répétée-et-récupération-dun-échec"></a>

## Repeated battle and failure recovery

The second record, `runtime/oracle-phase1/live-bataille-prepared-091.json`, confirms three successful repetitions and nine captures in `runs/petite-bataille/20261028T234412.193109Z-5000999d`. The driver first loads the scenario save before recording its controls; each repetition then reloads it. `completed`, `settings_restored_exactly` and all three protected-save checks are true. The restored pose has no following, strategic mode, signed zoom `-10`, pause active and known selection 1. All nine captures were also reread outside the game: schema, hash and copy/native/Python byte equality conform.

The `attack` order at time 0 targets the following two saved actors, whose identities and initial positions are stable in all three repetitions:

- Attacker `KenshiProbeFight_1_0`: `hand:1:254:2620117248:1:390136704`.
- Target `KenshiProbeFight_1_1`: `hand:1:255:2565673728:1:1780517632`.

The attacker's immediate task is `equip_weapon` in initial captures, then `unprovoked_focused_melee_attack` targeting the correct identifier at 120 and 600. Both start with seven parts at health 100 and stun 0 and remain `alive` in final captures. Effects differ:

| Repetition | Attacker health at 600 | Target state observed at 600 |
| --- | --- | --- |
| 1 | All parts at 100, no stun | Task `run_away`, all parts at 100 |
| 2 | `31-gamedata.quack:right` at 16,303886, stun 6,437221; `32-gamedata.quack:neither` at 37,776840, stun 11,375998 | Task `melee_attack` targeting the attacker, health 100 |
| 3 | `100-gamedata.quack:neither` at 85,754456, stun 1,175521 | Task `melee_attack` targeting the attacker, health 100 |

This proves an applied attack order and wounds in two repetitions, without claiming identical damage from all three fights or individually attributing each hit. Other tasks' `subject` field does not necessarily mean a combat target: at 120 the first target exposes `move_on_free_will` toward `[0,0,0]` with `target_id:hand:0:1487:11111:38923:355957024`, then `run_away` with its own identifier. Type 0 is `BUILDING` in the public enumeration, not a null handle; it may designate a building absent from this schema's collections. The object was not resolved and the meaning of `[0,0,0]` remains open. These observations do not prove corrupt data and do not justify erasing the raw subject.

| Checkpoint | Characters, repetitions 1 / 2 / 3 | Squads, repetitions 1 / 2 / 3 | Stable fields | Variable fields |
| --- | --- | --- | ---: | ---: |
| initial, 0 s | 173 / 168 / 151 | 30 / 30 / 30 | 39 752 | 16 510 |
| engagement, 120 s | 173 / 168 / 151 | 30 / 30 / 30 | 39 698 | 17 739 |
| fin, 600 s | 303 / 280 / 330 | 46 / 42 / 45 | 39 787 | 34 683 |

Only 21 character identifiers are shared by all three initial captures, from a union of 450; all 30 squad identifiers are shared. At the end, 23 character identifiers are shared, from a union of 867. Factions and their relations do not vary across repetitions in this report. Overshoots at 120 are respectively 0,053100, 0,231628 and 0,108032 game-calendar seconds; at 600, 0,148773, 0,135040 and 0,196838 seconds. The maximum is below **0,231629 seconds** in this campaign.

The first trial `runs/petite-bataille/20261028T233907.644180Z-afbe49f2` **failed**, despite three executions and nine captures: `restoration_error` reports a camera-center difference of 131 095,3671875 units. The driver had recorded a camera from `KenshiProbe_test`, then executed a save from another region. The precise engine mechanism for this movement is unknown. Strict verification was not relaxed; the `restore_required` guard remained active. `runtime/oracle-phase1/cross-save-recovery-091.json` establishes explicit recovery on `KenshiProbe_test`, with `verified:true`, before releasing the guard. This first trial does not count as complete runner validation and its captures are not mixed with the 18 captures from successful campaigns.

<a id="retour-final-à-la-vue-antérieure-à-la-phase"></a>

## Final return to the pre-phase view

After both campaigns, a separate attempt to return to the pre-phase pose was reread in `runtime/oracle-phase1/final-restoration-091.json`. It does **not** establish exact restoration: an initial read returns `world not ready`, then the final audit gives `complete:false`, `original_pose_verified:false` and camera-center difference `[-0.9453125, -0.02117919921875, -0.2734375]`. The position difference is `[-0.9453125, -0.021240234375, -0.2734375]`. This final attempt does not replace the restoration evidence specific to either scenario.

The normalized pointer is observed at `[1,1]` with edge scrolling enabled, against `[0.5,0.5]` in the reference. Screen-edge-related movement is plausible, without a certified engine cause. The final state retains free mode disabled, scrolling enabled and pause, with `clock.speed:0`. Selection becomes **unknown** (`selected_game_speed:null`, source `unknown`, `selected_speed_verified:false`) after the transition; neither a final selection of 1 nor the hidden prior 0.8.20 selection is claimed.

The final audit states `protected_state_verified:true`, `settings_equal_prephase:true` and all three protected saves unchanged. The DLL hash is `b99a1190bae405bbed60fad8380d9a9a038bb2b46745100f25739bbc63f5b4d3`, identical to the deployed build; the instance remains `34736:1222705718`. These checks do not compensate for the pose failure or absent known selection. No further trial or fix is undertaken after the request to stop the batch. Limits are retained rather than relaxing the check or claiming exact restoration.

<a id="vérifications-hors-jeu"></a>

## Checks outside the game

The full Python suite, after adding an explicit recovery save, finishes with **1 289 passing tests in 49,60 s**, using:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=runtime/oracle-phase1/pytest-recovery-final-20261029
```

It ran outside the sandbox to permit fake-game sockets. An `autouse` guard prevents tests from using real port 47800. Tests cover schemas, canonicalization, fake game, runner, timeouts, cancellation, restoration guard, concurrency and path protection; they do not replace Kenshi observations.

Scripts `tests/test-oracle-format-v100.cmd` and `tests/test-statistics-detail-v100.cmd` report **38 assertions** for format/speed control and **2 272 assertions over 198 cases** for statistics. Independent comparison of **59 synthetic states** produces identical C++/Python bytes. For all 18 captures in the two successful campaigns, rereading outside the game confirms schema, native/copy/canonicalization byte equality and every SHA-256 hash in the report. Identical serialization of a given state does not prove identical simulations.

<a id="limites-restantes"></a>

## Remaining limits

Identities across the entire population, persistence after restart, completeness of objects in memory and atomicity with respect to internal workers remain partly or entirely unknown. The schema captures loaded characters and their immediate task, not the unloaded world or complete order queue. Contract consistency and its sources are detailed in [state coverage](state-coverage.md).

At the end of this first batch, `ville-calme` had not been executed. The save has since been provided and its [validation supplement](oracle-ville-calme-validation.md) records three successful repetitions. Observed variation must remain in reports and must not be filtered to manufacture an identical state.

The first batch's two TODOs, `ORACLE-ORDER-ENUM` and `ORACLE-CAMERA-NONCHARACTER`, remain open. The later audit adds `ORACLE-IDENTITY-REMAP` for stable origins of NPC handles whose container changes. See [open questions](research/open-questions.md) and the [identity audit](npc-identities-phase1.md).
