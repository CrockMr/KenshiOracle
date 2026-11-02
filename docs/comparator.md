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
- Canonical **0.2**, **0.3** or **0.4** snapshots, matching SHA-256, within their
  campaign directory. All snapshots of a campaign use one state schema, equal to the
  report's `state_schema` when recorded, and both campaigns use the same one;
  a 0.2, 0.3 or 0.4 campaign is never compared with a campaign of another
  version. The 0.4 metrics are listed in
  [state coverage](state-coverage.md#extension-additive-04).
  Paused clock, requested time reached, `actual_at`, overshoot and snapshot
  clock consistent with repetition origin.
- Original: audited Kenshi 1.0.65/RE_Kenshi 0.3.5 build, GUI/CRT evidence of six
  neutralized booleans at campaign/repetition/snapshot levels, and effective
  restoration of the player's profile after a cold restart.
- Meitou: distinct uint64 seeds applied before loading and consistent across
  ready state, repetition provenance and every snapshot's provenance.
- Verified control restoration for both campaigns.
- Build commit: a campaign with `build_commit_known:false` (`"unknown"`) is
  refused, and so is a commit that changes between the report and any
  repetition's setup receipt; every setup receipt must carry `build_commit`. A report without `build_commit` (written before
  0.11) is refused for `scenario-0.2` and stays comparable for scenario 0.1,
  with the limitation `build commit not recorded`.
- Scene setup (a `scenario-0.2` with a `setup` block): every repetition's
  `setup` receipt has `receipt_format:"scene-setup-0.1"`, the declared target,
  `verdict:"passed"` and no failure; its `setup_hash` equals the hash
  recomputed from `scenario.setup` (rule in
  [scene setup](scene-setup.md#receipt-report-and-comparator)); its
  `alias_map` holds exactly the declared spawn and member aliases plus
  `player` or `player/1..n`, binds no character twice, has the same key set
  in every repetition, and equals every capture's `setup.alias_map`; its
  `members` hold exactly one row per bound character alias (not the spawn
  squad aliases). The receipt's `steps` and `dumps` are not re-verified: the
  comparator relies on `verdict:"passed"`.

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
In state 0.4, a squad with a proven saved HAND also gets an individual
`/squads/<id>/money` metric, and the carried character `carrying_id` is a
reference handled like `order/target_id`.
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
seconds. On MeitouClient this ratio is **Verified** in code (`Simulation.TickSeconds`
1/30, `SecondsPerGameHour` 1200/11), and checkpoint stops on 1.1-calendar-second
steps are **Observed** and consistent with it. On the original the engine reports
the same hour length (**Verified**) and the calendar advances about 33 calendar
seconds per real second at x1 (**Observed**); no simulated-time counter is read,
so simulated-time equivalence there is **Unknown**; see
[time units](protocol.md#time-units).

<a id="scene-scope"></a>

## Scene scope (scenario-0.2 with setup)

With a `setup` block, the comparator classifies only the scene, as frozen in
[scene setup](scene-setup.md#receipt-report-and-comparator); the code is
[oracle_scope.py](../mcp-server/oracle_scope.py). A scenario without
`setup` keeps every metric described above.

Characters in scope at a checkpoint are the alias ids, the player ids and every
character within `scene_radius` (X/Z, inclusive) of `scene_center`, read from
that checkpoint's snapshot. Ids come from each repetition's `alias_map`, never
from HAND proof, and a spawned id never appears in a metric path.

| Prefix | Metrics | Use |
| --- | --- | --- |
| `/scene/` | `/scene/squads/<spawn>/present`; `/scene/cohort/<cohort>/size`, `present`, `missing`; `/scene/intruders/count` (in-radius characters outside the alias and player cohorts; null when a position is unknown); `/scene/relations/<a>/<b>/value` for each declared pair, both directions | classified, in `findings` |
| `/scene/outcome/` | per cohort `survivors`, `dead`, `unconscious` and `health/current_total`, `stun_total`, `maximum_total`; the player's individual fields under `/scene/outcome/characters/alias:<alias>/`; engagement of each cohort over the whole scenario | `scene_outcome`, one observation per repetition, never classified |
| `/background/` | the metrics of the sections above with this prefix: population, clock, every other relation, faction starting cohorts and faction engagement without the cohort members, saved characters other than the players, saved-squad money (state 0.4; setup alias squads excluded), saved-squad trajectories and id-based moves outside the cohorts; and, per checkpoint, `/background/nearest_squad/distance`, `faction_id` and `faction_name` (below) | `background_metrics`, never classified |

Cohorts are `player` (the `player` or `player/<n>` aliases) and
`<spawn alias>/<template>`. Spawned members are interchangeable: they are
compared only as these (alias, template) aggregates, never one by one, so the
engines' reply order and ids do not matter. In values, a reference to an
aliased character or squad reads `alias:<alias>` (members:
`alias:<spawn>/<template>`).

`setup_members` lists, per target and repetition, the receipt's member facts
(`alias`, `template_id`, `faction_id`, `part_max`, `blood_before`,
`blood_after`, `rng_key`, without the engine id). The maxima are facts: there
is no verdict on the fight outcome. `scene_scope` records the centre, radius,
declared pairs and alias keys. The report's limitations state that outcome and
background metrics are not classified. `report.md` adds a short section with
the outcome and background counts, the cohort outcome per repetition and the
part maxima total per alias and repetition (at most 100 rows each; the full
data stays in `report.json`).

**Nearest squad outside the scene.** At every checkpoint the comparator
records the X/Z distance from a player character to the nearest positioned
member of the nearest squad, excluding each spawn alias squad and every player
character's own squad, with that squad's `faction_id` and faction name.
Distances are rounded to 0.1 world units; all three values are null when no
player has a known position or no other squad has a positioned member. The
values are background facts, one observation per repetition: they are never
classified, never become a finding and never count toward a class. They show
where the roaming population starts relative to the scene, which a yes-or-no
intruder count hides. `report.md` lists them per checkpoint in a
"Background: nearest squad outside the scene" table. A scenario without a setup
block has no such metric.

The two campaigns need not bind the same player alias form: one may bind
`player` and the other `player/1..n`. The `player` cohort aggregates either
form, so a different player count shows as a `/scene/cohort/player/size`
finding and as outcome rows present on one side only.

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

<a id="root-cause-groups"></a>

## Tests, root-cause groups and drafts

The code is [oracle_triage.py](../mcp-server/oracle_triage.py) and
[oracle_stats.py](../mcp-server/oracle_stats.py). Grouping runs after
classification and never changes a class.

**Per-finding test.** Every finding whose base classification is
`stable_divergent` or `variable_outside_range` (known deviations included)
carries `test`, an exact two-sided permutation test of its original values
against its Meitou values (difference of means for numbers, total variation
distance for booleans and strings; dict `test`, `kind`, `statistic`,
`p_value`, `splits`, `exact`, `minimum_p_value`), and `strength`: `strong`
when `p_value` is below 0.01, else `weak`. With five repetitions per side the
smallest attainable p-value is 2/252 (about 0.0079): only a complete
separation of the two samples is strong. Other findings carry neither key. The
test treats repetitions as exchangeable and metrics as independent; it
qualifies one metric, is not corrected for the number of metrics or
checkpoints, and proves no cause.

**Groups.** The divergent findings form root-cause groups:

1. One metric's divergent findings across checkpoints are one *member*; its
   checkpoints are listed in time order, `whole_scenario` last. The member's
   p-value is the smallest over those checkpoints.
2. The member's *entity* is the smallest unit one cause plausibly explains:
   `faction:<F>` for `/population/by_faction/<F>/`,
   `/population/by_squad_template/<F>/` and `/combat/starting_cohort/<F>/`;
   `squad:<id>` for `/characters/<id>/`, `/squads/<id>/` and
   `/trajectory/saved_squad/<id>/`; `scene` for `/scene/`; otherwise
   `family:/<a>/<b>`, the first two path parts. A character's squad is the most
   frequent original value of its `squad_id` field, else the container part of
   its saved handle (`hand:1:C:CS:I:S` gives `hand:34:C:CS:0:0`). On three real
   campaign pairs every recorded saved `squad_id` equals that container squad
   (**Observed**).
3. The *disagreeing set* is the Meitou repetitions that disagree with the
   original at the member's first divergent checkpoint: beyond the tolerance
   for a stable original, outside [min, max] widened by the tolerance (or
   outside the observed set) for a variable one.
4. The group key is (entity, disagreeing set, onset). Onset is `load` when the
   first divergent checkpoint is the scenario's earliest checkpoint, else
   `simulation`; the group's first checkpoint is its earliest member's. A
   known deviation never shares a group with an unexplained member.
5. A key whose disagreeing set is a proper subset of another key's set, with
   the same entity and onset, joins the smallest such superset.
6. A whole-scenario trace member (checkpoint `whole_scenario`: trajectories, moves, engagement)
   has no checkpoint of its own: it joins its entity's simulation key whose set
   contains its own, else its metric family's key.

Rules 4 to 6 relax a key that held the exact first checkpoint: on real
campaigns that key split one squad's drift over every checkpoint, every
subset of repetitions that left a variable range and every trajectory. The
headline of a group is its member with the lowest p-value, then the earliest
tested checkpoint, then the lexically first metric; the group's `strength` and
`p_value` are the headline's. Groups are ordered strong before weak, then by
size times the number of disagreeing repetitions (descending), then load
before simulation, then entity and set; known-deviation groups come last. Ids
are `g<rank>-<hash>` (for example `g001-4cd97d82`), the hash being of the
key, so a rerun on the same campaigns gives the same ids.

**Drafts.** `issues/` holds one English draft per **strong** group that is not
a known deviation, named by its group id, and `issues/README.md`, which lists
every group: strong ones with their draft, weak ones (headline, size,
p-value) and known deviations, neither drafted. Each draft states the
scenario, the save and its start-save fingerprint, both build commits (or
`build commit not recorded`), the state schema, N per side, the Meitou seed of
each repetition, the group key and onset, the first divergent checkpoint with
its time, the headline test (p-value, minimum attainable p-value, exact or
sampled), a headline table repetition, seed, value, disagreement and snapshot
link with original and MeitouClient rows labelled, the tolerance, the member
metrics (at most 20, then "and N more"; the complete list is in
`report.json`) and a one-line reproduction hint (save, the seed of a
disagreeing repetition, checkpoint). Links are relative. No issue is
published.

**Clock.** `/clock/*` fields are recorded in `background_metrics` as
`/background/clock/*` in every comparison, never classified or drafted: the
load nudge and the checkpoint overshoot make them differ between engines by
construction. A limitation line in each report says so.

<a id="outputs"></a>

## Outputs and format version

`report.json` has `format_version` **0.3** (0.2 before groups). It adds
`groups` (each with `id`, `key`, `entity`, `disagreeing_repetitions`,
`first_checkpoint` `{name, at}` with `at` null for `whole_scenario`, `onset`,
`headline` `{metric, checkpoint, p_value}`, `members`, `strength`, `p_value`,
`size`, `known_deviation`, `drafted`), per-finding `group` (null outside a
group), `test` and `strength` on divergent findings, `state_schema`,
`meitou.repetition_seeds` (repetition to seed) and, without a setup block,
`background_metrics` holding the clock. `summary` counts `groups`,
`strong_groups`, `weak_groups`, `known_deviation_groups` and `drafts` (strong
groups drafted). Findings, the preview and detail pages are in chronological
order: checkpoint `at`, then checkpoint name, then metric, `whole_scenario`
last.

`OUTPUT` contains:

- `report.md`: summary, N on both sides, sorted classes, the root-cause group
  tables (strong with draft links, weak and known deviations; at most 100 rows
  each) and a preview limited to the 20 earliest stable divergent findings,
  linking all details.
  Its limitations state the computed share of faction relation metrics
  (`/relations/` and `/scene/relations/`) among the compared metrics, adding
  that they are the majority of that total only when they are; the count of
  identical fields is never an overall parity score.
- `details/index.md` and pages: discrepancies/coverage, available N, ranges,
  medians, out-of-range observations, tolerances and snapshots. At most 100
  indicators per page, targeting 200 KiB where a row's size permits.
- `report.json`: equivalent detailed observations/statistics, also including
  parities summarized by count in Markdown.
- `issues/`: `README.md` and one English draft per strong root-cause group, as
  described above. No issue is published.

With small N, ranges/medians describe only the sample; a permutation p-value
qualifies a group's headline metric and is never presented as proof of a
cause. An original N = 5, 15-snapshot campaign is
validated locally (local evidence, not published),
with cold profile restoration. The
Meitou N = 5 campaign (local evidence, not published)
also completed its 15 snapshots and restoration. These links point to
Git-ignored evidence, not distributed files. The [validation report](phase2-validation.md)
presents the real comparison of these batches, divergence families and
confidence limitations; results do not establish general parity.
