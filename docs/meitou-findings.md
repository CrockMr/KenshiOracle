# MeitouClient findings from the oracle's live checks

The oracle compared the original game and MeitouClient on the owner's local saves, first in the
[state 0.5 live check](state-coverage.md#extension-additive-05), then in the hour-long holds that followed. Several goal differences
turned out to be MeitouClient defects. This page links each difference to its cause and to the upstream change that addresses it. It
records what the oracle found. It is not a MeitouClient changelog.

## Evidence and limits

- **The runs:** one paused hold per engine, no orders, checkpoints from 0 to 3 960 s. Two local saves (evidence not distributed):
  `oracle-base-cage-blesse` (Rebirth: caged and mining slaves, an injured caged prisoner) and `oracle-base-ville` (Sho-Battai, a big
  town). Meitou ran private builds: the pinned base with the [patch series](../integrations/meitou/README.md), later MeitouClient
  `c09ed01c` with the oracle adapter and the fixes below. Differences are pair counts of the same character at the same checkpoint
  (**Observed**, N = 1 per engine and build).
- **The causes** are read in MeitouClient's code (**Verified** there) or found with local diagnostic builds, traces and probes. The
  original's side comes from MeitouClient's own documentation of the decompiled game, and from live hooks on the original.
- **The follow-up holds** ran the same scenario with the fix applied in a private build, one fix at a time.
- **Statuses** are those of 2026-11-12.
- **Reproducibility:** the holds after the 0.5 check ran on private builds where the adapter was carried by hand onto
  later MeitouClient commits, the last one `c09ed01c`. That port is not published. The
  [patch series](../integrations/meitou/README.md#upstream-drift) has since been rebased onto `9a19748b` (2026-11-12), which
  contains the merged fixes below. One hold has run on it (2026-11-12, N = 1): 96.3 % of the Rebirth goal pairs agree by the
  count used under "Where Rebirth stands", against 96.8 % on the last private build. The private builds carried local fixes
  that the series does not, so the earlier figures are not reproduced from this repository.

## Findings at Rebirth

| Finding | What the oracle showed | Cause in MeitouClient | Upstream change |
| --- | --- | --- | --- |
| D. Bonedogs | Native: the 7 Bonedogs `sleep_on_floor` all hour. Meitou: `attack_enemies_and_neutrals` or `idle`, and one dies. | The load-time wild fill put a homeless bandit squad into a sector whose town is a nest. | [MeitouClient#255](https://github.com/VlcekM/MeitouClient/pull/255), merged |
| D, part 2: dogs idle | After #255 the dogs were `idle` instead of asleep. | State 72 `isFullyRested` held true for healthy NPCs, so their sleep goals counted as done. | [#257](https://github.com/VlcekM/MeitouClient/pull/257), merged |
| E. Mine slaves | Native: `auto_labouring_mines` (482 pairs). Meitou: `idle` or `null`; 18 agree. | A loaded slave ignored the save's `slaver` handle, so it had no owner or master. | [#256](https://github.com/VlcekM/MeitouClient/pull/256), merged |
| E, side effect | With owners, Meitou slaves walked into their cages by day. | The captive sweep read the slave's own lists, not its master's Slave AI Goals. | Part of #256 |
| F. Slavers | Native: `gather_slaves_from_cages` (90) and `work_the_slaves` (53). Meitou: `stay_in_home`. | Caged NPCs loaded with their town's saved platoons were never bound to their cages. | [#259](https://github.com/VlcekM/MeitouClient/pull/259), merged |
| F, 188 | No Meitou workmaster ever shouted at a slave. | The slave list held only the squad's own members, not the slaves that obey the squad. | [#265](https://github.com/VlcekM/MeitouClient/pull/265), merged |
| A. Sleepers (through `order`) | Meitou `get_out_of_bed` (361) where native is `use_bed` (180) or `null`. | The save's interior beds were not matched; a committed goal kept a plan whose done first step repeated. | [#263](https://github.com/VlcekM/MeitouClient/pull/263), [#264](https://github.com/VlcekM/MeitouClient/pull/264), merged |
| I. Medics | Native: `job_medic` (24). Meitou: `stand_at_shopkeeper_node` or `stay_in_home`. | Guards on duty did not leave their post to treat. | Issue [#163](https://github.com/VlcekM/MeitouClient/issues/163), closed |
| G. Shoppers | Native `shopping`, Meitou `relax_in_town_package` (106 of 136). | A town with no bar gave the bar package an outdoor table. | [#271](https://github.com/VlcekM/MeitouClient/pull/271), merged |
| H. Guards | Native `stand_at_guard_node_hometown_outside`, Meitou `..._homebuilding_in_out` (140). | 157 Static town guard did not hold a guard post of its town. | [#268](https://github.com/VlcekM/MeitouClient/pull/268), merged |
| Slaver pace | Meitou workmasters paused for an hour between shouts. | 188 dropped its slave before a line was said. | [#275](https://github.com/VlcekM/MeitouClient/pull/275), merged |
| Miners' place | 96 Meitou slaves at unfed stone processors; native slaves only quarry. | 189 took workplaces it cannot run. | [#289](https://github.com/VlcekM/MeitouClient/pull/289), merged |
| Bed window | Garrison sleepers woke and walked about at night. | A committed goal outlived its hours. | [#295](https://github.com/VlcekM/MeitouClient/pull/295), merged |
| 183 processing | On a newer master, 445 `slave_watching` pairs: processed slaves processed again. | The processing goal did not skip slaves already processed. | [#300](https://github.com/VlcekM/MeitouClient/pull/300), merged |
| Gather walk | Cages emptied slowly. | Slaver jobs finished the walk they were on before turning to their target. | [#301](https://github.com/VlcekM/MeitouClient/pull/301), merged |
| Stay home | Workmasters sat at home (`stay_in_home`) while slaves waited. | The AI did not weigh slaver goals against its other goals. | [#373](https://github.com/VlcekM/MeitouClient/pull/373), merged |
| Medic on top | The caged prisoner on an open top floor was not bandaged. | The medic's finder dropped a location on the floor above. | [#381](https://github.com/VlcekM/MeitouClient/pull/381), merged |
| Gate guards' start | Some native gate guards hold 157 all hour where Meitou's hold 38. | The original makes a gate's guard posts only once the gate's door has loaded (streaming, not a Meitou defect). | Docs [#382](https://github.com/VlcekM/MeitouClient/pull/382), merged |
| Off-screen pace | Meitou characters out of view walked at half the native pace; the cages emptied half an hour late. | The original moves a character out of view with twice the elapsed time. | [#400](https://github.com/VlcekM/MeitouClient/pull/400), merged |
| Cages at once | Meitou's gatherers emptied every cage at the same moment. | Gatherers of different squads could not go for the same cage. | [#401](https://github.com/VlcekM/MeitouClient/pull/401), merged |
| Slaver running | Meitou workmasters walked behind moving slaves. | A walk toward a moving character runs in the original. | [#402](https://github.com/VlcekM/MeitouClient/pull/402), merged |
| Mine slaves' detour | Some Meitou slaves walked all hour round the north of the town. | The navmesh cut the ground under Rebirth's trestle bridge. | [#403](https://github.com/VlcekM/MeitouClient/pull/403), merged |
| Miners against the rock | Meitou miners stood against the rock and never mined. | A worker had to reach 30 from the building's centre; the original takes the building's `use range`, doubled once stopped. | [#427](https://github.com/VlcekM/MeitouClient/pull/427), merged |
| Escapes | A native slave far from its owner out of town escapes; Meitou had no such rule, and a first version escaped 7. | The original's current town keeps a character up to 1.5 times the town's radius. | [#428](https://github.com/VlcekM/MeitouClient/pull/428), merged |

The cage trial before the 0.5 check led to [#237](https://github.com/VlcekM/MeitouClient/pull/237) (escaped slaves lie low),
[#239](https://github.com/VlcekM/MeitouClient/pull/239) (prisoners of generated interior cages), [#240](https://github.com/VlcekM/MeitouClient/pull/240)
(treating a caged patient on its floor) and [#241](https://github.com/VlcekM/MeitouClient/pull/241) (ending a kitless treatment). All
four are merged.

**Where Rebirth stands** (hold with #400 to #403 and #427, **Observed**, N = 1): 95.9 % of the goal pairs agree, leaving out the pairs
that depend on the original's loading order (gate guards' start, slaves whose owner loads late).

**The original against itself** (**Observed**, one pair of original runs of the same hold, the second on a diagnostic build of the
probe): 90.3 % of the goal pairs agree over all pairs, 98.5 % by the same count as above. A later MeitouClient hold on `c09ed01c`
reads 85.4 % and 96.8 % against the same reference. So the room left above MeitouClient on this hold is under two points, and the
gate-guard and late-gatherer exclusions also fire between two original runs (133 and 31 pairs); the late-owner one does not (0).
[Agreement between runs](agreement.md) describes the count.

**Five repetitions on each engine** (2026-11-12, **Observed**, one campaign each, MeitouClient on upstream `9a19748b` with the
adapter and no local fix): the original's repetitions agree with each other on 94.1 % of the goal pairs by that count (10 run pairs,
91.9 % to 96.8 %), and MeitouClient's with the original's on 94.6 % (25 run pairs, 92.0 % to 98.0 %). On this hold the goal
differences that remain are therefore within the original's own run-to-run variation, and the single pair above overstated the
room left. The largest part of that variation is a town squad choosing between `shopping`, `follow_squadleader` and `patrol_town`.

## Findings at Sho-Battai

- **Pairing:** only the 38 characters stored in the save have the same handle on both engines. The town's people are made at load with
  different handles, so per-character pairs cover little; the comparison by squad template and goal is the useful one there.
- **Saved squads the game never made** (Meitou: 32 of the save's 45 squads at 66 s, plus 21 rolled; the samurai stood with no goal all
  hour): a town squad was read as travelling, the save's never-made desert squads were dropped, and the desert sectors filled
  themselves beside them. [#450](https://github.com/VlcekM/MeitouClient/pull/450), merged: 43 of 45, 7 rolled (native 1), the samurai
  guard and patrol as the original's.

## Merged since, not yet detailed here

Five more changes came out of the same holds and were merged upstream on 2026-11-09 and 2026-11-10. Their findings are not
written up on this page yet; the pull requests carry the oracle numbers.

- [#472](https://github.com/VlcekM/MeitouClient/pull/472): a slave just taken out of a cage no longer treats people by himself.
- [#475](https://github.com/VlcekM/MeitouClient/pull/475): a slave a guard takes out of a cage walks to work instead of standing in the cage.
- [#479](https://github.com/VlcekM/MeitouClient/pull/479): a slave a guard takes out of a cage stays in his own squad.
- [#481](https://github.com/VlcekM/MeitouClient/pull/481): animal packs sleep together instead of members walking after their sleeping leader.
- [#489](https://github.com/VlcekM/MeitouClient/pull/489): a loaded save no longer gets extra desert squads on top of the ones it already holds.

**Five repetitions at Sho-Battai** (2026-11-12, **Observed**, one campaign per engine, MeitouClient on upstream `9a19748b`): for the
38 stored characters the goal types agree in 99.1 % of the pairs between the engines and in 98.3 % between the original's own
repetitions. The town's people are still outside any per-character count.

## Still open

- **Rebirth, loading order:** in the original, five gatherers chase a slave all hour whose cage record still names him; his owner loads
  late. Not modelled (39 pairs).
- **Rebirth, random draws:** one Holy Sentinel never shops on Meitou. The original draws each shopping list with the C runtime's
  `rand()`, so which shoppers get an empty list cannot match (17 pairs).
- **Rebirth, owners loading late:** the original's slaves plan with their own lists until their owner loads (left out of the agreement).
- **Sho-Battai turrets:** the native samurai man the turrets during a fight near the town, then 3 stay on them with no fight; Meitou
  mans them only while enemies are near. The fight comes from a roaming squad the original makes after load. The meaning of the `*`
  on the turret goal's state 6 is **Unknown**.
- **J. Sleepers:** the native probe reports no goal during part of the bed time. What the original holds then is **Unknown**.
- **Order `stand_at_node` against `move_on_free_will`:** Meitou still walked where the original already stood. Not re-measured since.
- **Wild spawns during a hold:** Meitou's wild tick can bring in squads the original does not (the open part of D); #450 caps the
  load-time fill by the island's room.
