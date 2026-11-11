# Agreement between runs

`agree` answers one question about completed runs: **how often do the same
saved characters hold the same value?** It reads run reports and snapshots from
disk and contacts no game. The source is
[oracle_agreement.py](../mcp-server/oracle_agreement.py).

It complements the [campaign comparator](comparator.md). The comparator
classifies each metric across at least five repetitions per engine. `agree`
classifies nothing: it counts, and it works with a single run on each side, so
it suits the daily loop of one hold on a MeitouClient build against one
reference hold of the original.

## Command

```powershell
python -m launcher agree REFERENCE RUN [RUN ...] [--rules RULES.json]
```

`REFERENCE` and each `RUN` are a run's `report.json` or the directory that
holds it. The first is the reference; every other run is compared with it.

| Option | Default | Meaning |
| --- | --- | --- |
| `--rules FILE` | none | Rules file naming documented classes of differences; see [Rules](#rules). |
| `--detail FIELD` | `goal/type` (`order/type` before state 0.5) | Exact field reported in detail. Repeatable. A field named by a rule is always detailed. |
| `--field PREFIX` | all fields | Field prefix kept in the all-fields table, for example `goal` or `health`. Repeatable. |
| `--top N` | `12` | Rows listed in each detail table, 1 to 200. |
| `--position-tolerance X` | `0.000001` | Absolute world-unit tolerance for positions. |
| `--number-tolerance X` | `0` | Absolute tolerance for other numbers. |
| `--output DIR` | none | Writes `agreement.json` and `agreement.txt` there. |
| `--ledger FILE` | none | Appends one JSON line per run and detail field; see [Ledger](#ledger). |
| `--json` | off | Prints the JSON result instead of the text report. |

MCP clients call `agreement(reference_report, run_reports, rules=None,
fields=None, detail_fields=None, top=12)`; it returns the same result with the
text report under `text`.

## What is counted

- **Runs must be the same experiment.** The save name, save fingerprint, state
  schema and checkpoint list must be equal, otherwise the command refuses.
- **Checkpoints are matched by name**, never by file order. A checkpoint that a
  repetition lacks is listed under `missing_checkpoints` and in the text
  report; the others are not shifted.
- **Characters are paired by complete saved handle** (`identity_origin: saved`),
  with the campaign comparator's per-character fields. Generated characters are
  never paired. The report gives, summed over checkpoints, the pairs, the saved
  characters only in the reference and those only in the other run.
- **For each field**, `comparable` is the number of pairs where both sides have
  a value and `equal` the number where the two values are equal. A null or
  absent value on one side is counted as `one_sided_unknown`, on both sides as
  `both_unknown`; neither is a difference. `health/<part>/<field>` rows are
  pooled as `health/*/<field>` and `stats/<name>` as `stats/*`.
- **Repetitions.** Every repetition of the reference is compared with every
  repetition of the other run and the counts are pooled; `repetition_pairs`
  gives the counts of each pair. Only repetitions with status `completed` are
  read.
- **Snapshots are checked by hash.** Each snapshot must have the SHA-256 that
  its report recorded when the runner validated it. The schema is not validated
  a second time, which keeps a 20-checkpoint pair to a few seconds.

Time-integrated numbers (`medical/blood`, `medical/hunger`) and positions
rarely agree exactly, between two runs of one engine as well. Read them next to
the noise floor, or pass a tolerance.

## Noise floor

The original is not deterministic, so a number alone says little. A run of the
reference's **own engine** among the other runs is marked `same engine: noise
floor`: it shows how far that engine disagrees with itself on this hold. A
reference with several repetitions is also compared with itself
(`reference repetitions against each other`).

`noise_floor` holds, per detail field, the lowest same-engine agreement, or
`measured: false`. The text report then prints `noise floor: NOT MEASURED`.
A gap between a candidate and the reference that is no larger than the noise
floor is not evidence of a difference between engines.

## Rules

A rules file names classes of pairs that a documented cause explains, for
example a load-order artefact of the reference engine. It is data: nothing
about one save lives in the tool. See the
[example](../scenarios/agreement-rules/example.json).

```json
{
  "format": "agreement-rules-0.1",
  "classes": [
    {
      "name": "gate-guards-start",
      "field": "goal/type",
      "reason": "Why the two engines legitimately differ here.",
      "evidence": "Where that is recorded.",
      "when": { "squad_template": ["..."], "values": [["a", "b"]] }
    }
  ]
}
```

`name`, `field`, `reason`, `evidence` and `when` are all required. Every
condition given in `when` must hold:

| Condition | Holds when |
| --- | --- |
| `squad_template: [ids]` | The character's squad in the reference run has one of these templates. |
| `values: [[a, b], ...]` | The two sides hold exactly these two values, in either order. |
| `reference_value: [v]` | The reference holds one of these values. |
| `candidate_value: [v]` | The other run holds one of these values. |
| `candidate_value_not: [v]` | The other run holds none of these values. |
| `related_absent: {related: {id: other_id}}` | The character is a key of `related` and its related character is absent from the reference snapshot. |
| `related_absent: {..., held_value: v}` | As above, and also at later checkpoints for as long as the reference has kept `v` without a break since a checkpoint where the related character was absent. |
| `squad_absent_at_first_checkpoint: true` | No character of the reference's first checkpoint belongs to the character's squad (the squad loaded later). |

Rules never raise a number silently:

- only pairs that **differ** can be set aside; a pair that agrees always counts;
- the first class that matches takes the pair, in file order;
- the number over all pairs is always printed first, the number without the
  set-aside pairs next to it, and the pairs of each class are listed;
- every class is counted on the same-engine comparison too. A class that fires
  between two runs of the reference engine is that engine's own variation; a
  class with 0 pairs there is not shown to be.

## Outputs

The text report gives, for each detail field: one line per run (all pairs, then
without the set-aside pairs, engine, build commit, run), the pairs set aside by
each class, the largest remaining differences as `reference -> other` with one
example character, its squad template and checkpoint, and the squad templates
that hold the remaining differences. A table of every field follows.

`agreement.json` carries the same numbers, with up to three examples per
difference and the counts of each repetition pair. A run's label is its path
without the part all the runs share.

### Ledger

`--ledger FILE` appends one line per run and detail field: scenario, save
fingerprint, both build commits, the counts, the rules file hash and the pairs
of each class. A line already present is not added again, so the command can be
rerun. The file is a plain record for following one hold across MeitouClient
builds; it is not read back by the tool.

## A real example

**Observed** on one hold of a slave-camp save (20 checkpoints, state 0.5), with
a rules file holding the three classes of the [example](../scenarios/agreement-rules/example.json)
adapted to that save:

| Run compared with the original reference | All pairs | Classes set aside |
| --- | ---: | ---: |
| A second run of the original | 1768 of 1959 (90.3 %) | 1768 of 1795 (98.5 %) |
| MeitouClient `c09ed01c` with the adapter and local fixes | 1643 of 1925 (85.4 %) | 1643 of 1698 (96.8 %) |

Between the two original runs the gate-guard class set aside 133 pairs, the
late-gatherer class 31 and the late-owner class 0. So two of the three classes
are the original's own variation on this save, and the third is not shown to
be by this pair.

Limits of this example: one pair of original runs only; the second original
run used a diagnostic build of the probe (same state schema and save
fingerprint); the runs and the rules file are local and not distributed.

## Limits

- One run pair is one observation. Agreement is a distance between runs, not a
  classification of stability; use the [comparator](comparator.md) with five
  repetitions per engine for that.
- Characters without a saved identity are outside the count. A population that
  one engine generates and the other does not appears only as `only in the
  reference` or `only in the other run` for saved characters, and not at all
  for generated ones.
- A rules class is as good as its evidence. The tool checks its shape, not its
  truth.
- The headline field is `goal/type` by default; a high agreement there says
  nothing about positions, health or timing.
