# Mod-free campaigns on a fresh city save

Local campaigns of October 30-31, 2026. They repeat the quiet-town comparison
with **no gameplay mods** on either target and with a save created under that
profile. Labels: **Verified** (checked against hashed inputs, code or the
snapshots), **Observed** (read from a run, not re-derived), **Unknown**.
Five repetitions per side describe these runs only; they do not establish a
distribution or generalize to other saves or installations.

All times below are game **calendar seconds** (in-game hours x 3600), as in
scenario `at` and `clock.elapsed_seconds`. One simulated second is 33 calendar
seconds, so 120 / 300 / 600 calendar s are about **3.6 / 9.1 / 18.2 simulated
seconds** after the paused load. See [time units](protocol.md#time-units) for
the status of that ratio on each target.

Evidence, saves, snapshots and private diagnostic builds stay outside Git.

## Minimal profile

| | Original | MeitouClient |
| --- | --- | --- |
| Data files | `gamedata.base`, `Newwworld.mod`, `Dialogue.mod`, `rebirth.mod`, then the zero-record `KenshiProbe.mod` observer descriptor | The same four base files; empty `mods.cfg` |
| Evidence of loading | Native load receipts for the five files, in that order (**Verified**) | Parser and full apply receipts for the four files; 147 indexed resource locations, no mod or Workshop path (**Verified**) |
| Native add-ons | Kenshi 1.0.65, RE_Kenshi 0.3.5 with the six reference options off (see [original reference](original-reference.md)); other native plugins and helpers quarantined; residual RE_Kenshi hooks remain ([deviations](rekenshi-deviations.md)) | No game mod DLL in the captured process inventory |
| Simulation settings | Player settings; autosave and edge scrolling disabled for control | Default simulation preferences; only edge scrolling and autosave disabled for control |
| Seeds | Native randomness not controlled | Seeds 0..4 applied before each load |

The four base-file hashes match between targets (**Verified**). Both record
54,951 records after the last file; MeitouClient reports 55,116 after its
derived additions (counters of different scope). The probe and MeitouClient
binaries were private diagnostic builds with content receipts, not published
releases. The profile does not certify every loose asset against a stock
distribution (**Unknown**), and RE_Kenshi residual hooks keep the original
outside any unmodified-vanilla claim.

## Fresh city save and scenario

`oracle-clean-ville-calme` was created by **New Game** under this profile,
without Load or Import (operator attestation correlated with the supervised
session, not machine proof of every UI action). A read-only dependency
inspection of its 12 files found **0** unresolved external definition targets
among 25,225 reference occurrences, and **0** mod or Workshop asset-path hints
in its string and filename fields (**Verified**, within the inspected
metadata). The same immutable save is used
by every run below.

Scenario `ville-calme-clean-300`: paused load, speed 1, no orders,
**5 repetitions**, checkpoints at **0 / 120 / 300 / 600** calendar s. The first
certified campaign (October 30) used 0/120/600; the follow-up added the
300 s checkpoint, and all results below come from four-checkpoint runs. Each
repetition reloads the save; configuration and protected saves were restored
and verified after every campaign (**Verified** by the campaign audits).

| Target | Build | Run |
| --- | --- | --- |
| Original | Kenshi 1.0.65, RE_Kenshi 0.3.5, diagnostic KenshiProbe | accepted follow-up campaign, reused for every comparison |
| MeitouClient `1df4493` | fork `076d8abd` | follow-up campaign, seeds 0..4 |
| MeitouClient `08340c7` | fork `118b1648` | follow-up campaign, seeds 0..4 |
| MeitouClient `100c6cae` | fork `16ec56af` | five-repetition campaign of October 31, seeds 0..4 |

`16ec56af` is the published series tip `5ed31178` plus private diagnostic and
test commits; the published series was validated by tests, not by this campaign.
No published MeitouClient release contained `100c6cae` at the time, so that
campaign used a master commit.

## Loaded characters per checkpoint

Count of `characters` in each snapshot (loaded actors, not world population).
Original repetitions and MeitouClient seeds are independent ensembles, not
paired random streams.

| Calendar s | Simulated s | Original, repetitions 1-5 | MeitouClient seeds 0-4, all three builds |
| ---: | ---: | --- | --- |
| 0 | 0 | 107, 107, 107, 107, 107 | 82, 121, 99, 125, 83 |
| 120 | 3.6 | 107, 107, 107, 107, 107 | 82, 121, 99, 125, 83 |
| 300 | 9.1 | 150, 130, 133, 132, 131 | 82, 121, 99, 125, 83 |
| 600 | 18.2 | 150, 130, 126, 125, 131 | 82, 121, 99, 125, 83 |

- **Verified** (recounted from the 80 snapshots): the counts above; on
  MeitouClient each seed keeps the same count on `1df4493`, `08340c7` and
  `100c6cae`, and the character identity sets of `08340c7` and `100c6cae` are
  equal at all 20 checkpoints.
- **Observed:** the original's first positive net change lies between 120 and
  300 calendar s in 5 of 5 runs (+23 to +43); from 300 to 600 three runs are
  unchanged and two lose 7. MeitouClient shows no net change in any interval.
- **Observed:** every capture holds 11 actors with a proven saved origin;
  other origins are null (unproven, not evidence of birth).
- Net count changes are not births, deaths or spawn counts, and four samples do
  not show whether a change was abrupt or gradual (**Unknown**).
- Beyond 600 calendar s (about 18 simulated s) nothing was measured
  (**Unknown**).

Actual stops: the original overshoots by 0.00 to 0.27 calendar s. MeitouClient
stops on the first 1.1 calendar s tick past the target (121.0, 300.3, 600.6),
except two late stops on `08340c7` (303.6 and 605.0; cause **Unknown**).

## Comparator classes

[Comparator](comparator.md) defaults, original first, N = 5 per side, 88,524
findings each. The `100c6cae` row and a re-run of the `08340c7` row were
produced with the current public comparator from the campaign snapshots
(**Verified**); the `1df4493` row was recomputed from hashed inputs in the
earlier offline analysis (**Verified**).

| Original vs | Stable divergent | Stable identical | Variable outside range | Variable compatible | Not comparable |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1df4493` | 233 | 87,171 | 150 | 57 | 913 |
| `08340c7` | 233 | 87,171 | 153 | 54 | 913 |
| `100c6cae` | 233 | 87,171 | 152 | 55 | 913 |

No metric is attributed to a known deviation. As in every comparison, these
counts overlap and are not a bug count or a parity score.
`/population/loaded/total` is stable divergent at 0 and 120 s and variable
outside range at 300 and 600 s on all three builds.

### What changed between builds

- **`1df4493` to `08340c7`** (**Verified**, recomputed from hashed inputs in
  the earlier offline analysis): 121 checkpoint metrics changed on
  the MeitouClient side, none at the initial capture: saved-character positions
  of 10 saved characters, 21 saved-squad trajectory metrics, the two late clock
  stops and 12 dependent combat-window bounds. Three metrics (two positions of
  one saved character and the final z of its squad's trajectory) moved from
  compatible to outside range. No population, faction,
  squad-template, relation or combat-cohort value changed.
- **`08340c7` to `100c6cae`** (**Verified**): again 121 changed MeitouClient
  metrics of the same kinds (positions, trajectories, clock, combat-window
  bounds). Those three position and trajectory metrics return to compatible, and two x positions of
  another saved character become outside range. No population, faction,
  relation or squad-set change.
- Whether these position changes come from source changes or from run-to-run
  host timing is **Unknown**: five runs per build cannot separate the two.

## Open question H1: two late town platoons

- **Verified** (save data): the save lists `Shinobi Thieves_0` (char count 8)
  and `Trade Ninjas_1` (char count 4) as persistent, never activated, non-resident
  platoons with a home building and **no `.platoon` file**. Their home buildings
  and saved positions lie in zones adjacent to the player's zone, outside the
  area immediately around the player.
- **Observed** (original, 5 of 5): both are absent at 0 and 120 calendar s and
  present at 300, with their saved handles and 9-11 and 3-5 members. A finer
  original run (checkpoints every simulated second) shows both absent at 4 and
  present at 6 simulated seconds in all five repetitions, with members built
  from the template rather than the saved count.
- **Verified** (snapshots): neither appears on MeitouClient `1df4493`,
  `08340c7` or `100c6cae` up to 600 calendar s.
- **Unknown:** the original's exact activation mechanism.
  [MeitouClient's documented rule](https://github.com/VlcekM/MeitouClient/blob/master/docs/game/factions-squads-towns.md)
  (an unloaded platoon activates after a 5 s dwell) fits the timing; that it
  is the cause is an inference.

With 12 to 16 members, these two platoons account for only part of the
original's +23 to +43 increase (**Observed**). The rest of the increase comes
from other squads, including other saved squads that also first appear between
120 and 300 calendar s in some runs (**Observed**); they are outside H1, as are
the unfiled platoons already present at load. A fix is
proposed to MeitouClient upstream separately and is not part of this
repository.

## Other open question

The initial character height after load and spawn differs between the engines
on another mod-free save; it is tracked in the
[open questions](research/open-questions.md#original-and-meitouclient-on-mod-free-saves).

## Earlier figures obtained with mods

The following published figures come from the older saves used by the
`ville-calme`, `petite-bataille` and `trajet-escouade` scenarios (the
`ville-calme`, `KenshiProbe_test` and `KenshiProbe_test_scene_*` saves),
before this profile existed:

- [Phase 2 validation](phase2-validation.md): the quiet-town N5 comparison
  (291 stable divergences, loaded population 103 vs 137..159, the
  height and relation examples) and the Meitou battle/travel runs.
- [Quiet-town phase 1 supplement](oracle-ville-calme-validation.md) (101 / 103 /
  110 and 123 / 125 / 131 characters), the
  [phase 1 validation](oracle-phase1-validation.md),
  [step 0 milestone](phase2-step0-validation.md) and
  [saved NPC identities](npc-identities-phase1.md) counts.

Those figures are **mod-affected**. The `ville-calme` save itself references
definitions from a Workshop mod (`Lively Bars.mod`), and the two test saves
reference several more (**Verified**, save inspection). The original
reference processes of those campaigns registered mod resource locations
(**Observed**, process logs); their effective load order on either target is
**Unknown**. They remain valid descriptions of those runs, but they are not
mod-free baselines and are not comparable with the counts above: both the
profile and the scene changed, so no difference can be attributed to mods
alone.

[Research notes](research/README.md) that measured on the older `ville-calme`
/ `KenshiProbe_test` saves inherit the same mod caveat (**Observed**); they
concern performance, not cross-engine parity.
