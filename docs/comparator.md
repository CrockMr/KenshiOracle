<a id="comparateur-de-campagnes"></a>

# Campaign comparator

The comparator reads two completed campaigns, original and MeitouClient, without
contacting either game. It produces descriptive statistics and local drafts.
Sources are [oracle_comparison.py](../mcp-server/oracle_comparison.py),
[oracle_compare.py](../mcp-server/oracle_compare.py) and
[oracle_traces.py](../mcp-server/oracle_traces.py).

<a id="commande-et-entrées"></a>

## Command and inputs

From the repository root, after installing Python dependencies:

```powershell
python -m launcher compare ORIGINAL_REPORT MEITOU_REPORT OUTPUT
```

Replace the first two arguments with `report.json` paths or their campaign
directories. `OUTPUT` must be a **new, nonexistent directory**.
Example layout, adapting batch names:

```powershell
& .\.venv\Scripts\python.exe -m launcher compare runs/ville-calme/lot-original/report.json runs/ville-calme/lot-meitou/report.json runs/comparisons/ville-calme
```

Reports and snapshots stay on the same volume to allow relative links.
`runs/` is Git-ignored; no game dump may enter public sources.

| CLI option | Default | Scope |
| --- | ---: | --- |
| `--minimum-repetitions` | `5` | Required minimum **on each side**, integer 1..100. Reducing it serves diagnostics, not the five-repetition criterion. |
| `--position-tolerance` | `0.000001` | Absolute world-unit tolerance for positions, distances and displacements. |
| `--number-tolerance` | `0` | Absolute tolerance for other numbers. |
| `--arrival-radius` | `5` | Geometric X/Z radius for observing arrival; separate from comparison tolerance. |
| `--known-deviations` | absent | JSON file associating each exact metric with documented attribution; see below. |

Tolerances and radius must be finite and nonnegative. Radius is bounded to
1e9 units. MCP tool `compare_scenarios(original_report, meitou_report,
output, minimum_repetitions=5, position_tolerance=0.000001,
number_tolerance=0, arrival_radius=5)` uses the same comparator.
Known-rule option available through CLI/Python API, not this MCP tool.

Loader requires:

- Same scenario excluding repetition count, same save and same
  `quick.save`/indexed-platoon fingerprint; complete repetitions/checkpoints.
- Canonical **0.2** snapshots, matching SHA-256, within their campaign directory.
  Paused clock, requested time reached, `actual_at`, overshoot and snapshot
  clock consistent with repetition origin.
- Original: audited Kenshi 1.0.65/RE_Kenshi 0.3.5 build, GUI/CRT evidence of six
  neutralized booleans at campaign/repetition/snapshot levels, and effective
  restoration of the player's profile after a cold restart.
- Meitou: distinct uint64 seeds applied before loading and consistent across
  ready state, repetition provenance and every snapshot's provenance.
- Verified control restoration for both campaigns.

`completed` status alone is insufficient. Fingerprint does not cover assets,
mods, their order or builds: retain these preconditions and build evidence
separately. It does not certify their identity.

<a id="classement-et-identités"></a>

## Classification and identities

Original stability is computed on **exact values**. Tolerances apply only to
cross-target equality and range endpoints; they do not remove original variation.
N, available N, values, range/median and number of out-of-range Meitou observations
remain explicit. Category compatibility uses observed values, not a numeric interval.

| Class | Interpretation bounded to observations |
| --- | --- |
| Stable identical | Original exactly stable, all Meitou values equal to its reference within tolerance. `comparison_exact` distinguishes exact equality; Meitou may vary inside tolerance. |
| Stable divergent | Original exactly stable and at least one Meitou value differs beyond tolerance: priority discrepancy. |
| Variable compatible | Original variable; Meitou values within observed range/set, with numeric tolerance if applicable. No general parity demonstrated. |
| Variable outside range | Original variable; at least one Meitou value outside observed range/set. |
| Known deviation | Previous divergence reassigned by an explicit applicable rule for this exact metric; base class retained. |
| Not comparable | Missing/null field, unknown coverage, incompatible type or unmatchable identity in at least one repetition. |

Characters match individually only through **complete HAND** and
`identity_origin:"saved"`. Squad/target references must also be proven.
Name, position, faction, index or coincident current ID does not establish identity.
Other NPCs contribute to groups; they are never individually matched across games.

<a id="groupes-et-observations-temporelles"></a>

## Groups and temporal observations

- Total loaded population and per-faction population; alive, unconscious, dead
  and counts without proven saved identity. The latter are not automatically
  called generated.
- Each faction's initially loaded cohort, tracked within a repetition: size,
  survivors, dead, unconscious and absent. Survivors include unconscious
  characters; disappearance does not prove death.
- Faction/squad-template groups and loaded members. Unknown coverage:
  metric censored to `null`. Absent group but established coverage: zero.
  Towns follow the same rule; currently unknown town identities remain
  not comparable.
- **Directional** relations: value and change since first checkpoint,
  without assumed symmetry.

For a saved squad, cohort comprises members loaded at the first checkpoint.
Final position is their mean. Observed distance is mean length of **each member's
3D polyline** between snapshots: a lower bound, distinct from mean net displacement
between first/last positions. A missing position censors the cohort; no interpolation
or extra simulation fills intervals.

For a `move` order, arrival requires **all** initial members observed within
the destination's X/Z radius. First snapshot establishing this gives only
scenario-relative interval `[0, first_observed_at]`; `exact_arrival_time`
remains null. Unobserved arrival does not prove no arrival/departure occurred
between snapshots.

Faction-cohort engagement uses `in_combat`. Span between first and last positive
snapshots proves neither continuity nor cumulative combat duration.
Bounds `[0, window width]` concern only the sampled window; exact total duration
remains unknown and `duration_seconds` remains not comparable.
Three snapshots do not replace a temporal log.

All times, intervals and windows above (`first_observed_at`, window widths,
`duration_seconds`, checkpoint times) are game **calendar** seconds, like
scenario `at` and `elapsed_seconds`. Per MeitouClient's constant of `1200/11`
simulated seconds per in-game hour (**Verified** in its code), one simulated
second is 33 calendar seconds: a 600-second window covers about 18.2 simulated
seconds. This conversion is measured on MeitouClient; on the original the
engine reports the same hour length, but simulated time is not measured
directly (**Unknown**);
see [time units](protocol.md#time-units).

<a id="écarts-re_kenshi-et-sorties"></a>

## RE_Kenshi deviations and outputs

The [RE_Kenshi inventory](rekenshi-deviations.md) provides context; its mere
presence reclassifies no divergence. `--known-deviations` JSON is an object whose
**keys are exact metrics**. Each value contains `metric` equal to its key,
`id`, `source` (HTTP/HTTPS URL), nonempty `explanation` and `evidence`.
No wildcard. Supplied attribution must explain the mechanism, effective condition
and evidence applicable to this field; verifying causality remains an audit
responsibility, not a statistical inference. A rule replaces neither parity
nor unknown coverage with “known deviation”.

`OUTPUT` contains:

- `report.md`: summary, N on both sides, sorted classes and preview limited to
  20 strong discrepancies, linking all details.
- `details/index.md` and pages: discrepancies/coverage, available N, ranges,
  medians, out-of-range observations, tolerances and snapshots. At most 100
  indicators per page, targeting 200 KiB where a row's size permits.
- `report.json`: equivalent detailed observations/statistics, also including
  parities summarized by count in Markdown.
- `issues/`: one English draft per **stable divergent** metric, with evidence,
  values and tolerance; metric-derived filenames and relative links.
  No issue is published.

With small N, ranges/medians describe only the sample; no significance test
is presented as proof. An original N = 5, 15-snapshot campaign is
[validated locally](../runs/ville-calme/20261029T195936.248409Z-8d76ea5c/report.json),
with cold profile restoration. The
[Meitou N = 5 campaign](../runs/meitou/ville-calme/20261029T200854.596180Z-c872b96e/report.json)
also completed its 15 snapshots and restoration. These links point to
Git-ignored evidence, not distributed files. The [validation report](phase2-validation.md)
presents the real comparison of these batches, divergence families and
confidence limitations; results do not establish general parity.
