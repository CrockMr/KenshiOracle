# MeitouClient findings from the state 0.5 live check

The [state 0.5 live check](state-coverage.md#extension-additive-05) compared the original game and MeitouClient on one save. Several of
its goal differences turned out to be MeitouClient defects. This page links each difference to its cause and to the upstream change
that addresses it. It records what the oracle found. It is not a MeitouClient changelog.

## Evidence and limits

- **The run:** one paused hold per engine on the owner's local save `oracle-base-cage-blesse` (Rebirth: caged and mining slaves, an
  injured caged prisoner; local evidence, not distributed). Meitou ran the [patch series](../integrations/meitou/README.md) on its
  pinned base `88ae71a1`. Differences are pair counts of the same character at the same checkpoint (**Observed**, N = 1 per engine).
- **The causes** are read in MeitouClient's code (**Verified** there) or found with local diagnostic builds and probes. The original's
  side comes from MeitouClient's own documentation of the decompiled game.
- **The follow-up holds** ran the same scenario on the pinned base with the fix applied in a private build (**Observed**, N = 1 each),
  one fix at a time.
- **Statuses** are those of 2026-11-03.
- The pinned base predates every change below, so a series built on it still shows these differences.

## Findings

| Finding | What the oracle showed | Cause in MeitouClient | Upstream change |
| --- | --- | --- | --- |
| D. Bonedogs | Native: the 7 Bonedogs `sleep_on_floor` all hour. Meitou: `attack_enemies_and_neutrals` or `idle`, and one dies. | The load-time wild fill put a homeless bandit squad into a sector whose town is a nest. | [MeitouClient#255](https://github.com/VlcekM/MeitouClient/pull/255), merged |
| D, part 2: dogs idle | After #255 the dogs were `idle` instead of asleep. | State 72 `isFullyRested` held true for healthy NPCs, so their sleep goals counted as done. The original's evaluator is false off the player's side. | [MeitouClient#257](https://github.com/VlcekM/MeitouClient/pull/257), merged |
| E. Mine slaves | Native: `auto_labouring_mines` (482 pairs). Meitou: `idle` or `null`; 18 agree. | A loaded slave ignored the save's `slaver` handle, so it had no owner or master. | [MeitouClient#256](https://github.com/VlcekM/MeitouClient/pull/256), merged |
| E, side effect | With owners, Meitou slaves walked into their cages by day. | The captive sweep read the slave's own lists, not its master's Slave AI Goals. | Part of #256 |
| F. Slavers | Native: `gather_slaves_from_cages` (90) and `work_the_slaves` (53). Meitou: `stay_in_home`. | Caged NPCs loaded with their town's saved platoons were never bound to their cages, so no gatherer found an occupant. | [MeitouClient#259](https://github.com/VlcekM/MeitouClient/pull/259), open |
| F, 188 | No Meitou workmaster ever shouted at a slave. | The slave list held only the squad's own members; the original's holds the slaves that obey the squad. | [MeitouClient#265](https://github.com/VlcekM/MeitouClient/pull/265), open |
| A. Sleepers (through `order`) | Meitou `get_out_of_bed` (361) where native is `use_bed` (180) or `null`. | The interior beds of the save were not matched, so the bed goal aimed at another bed. A committed goal kept a plan whose done first step repeated. A bound sleeper was placed standing, and a loaded sleep had no goal provenance. | [MeitouClient#263](https://github.com/VlcekM/MeitouClient/pull/263) and [#264](https://github.com/VlcekM/MeitouClient/pull/264), open |
| I. Medics | Native: `job_medic` (24). Meitou: `stand_at_shopkeeper_node` or `stay_in_home`. | Guards on duty did not leave their post to treat: the NPC Medic goal was not scored as in the original. | Issue [MeitouClient#163](https://github.com/VlcekM/MeitouClient/issues/163), closed by the maintainer's own commits |

The cage trial before the 0.5 check led to [MeitouClient#237](https://github.com/VlcekM/MeitouClient/pull/237) (escaped slaves lie
low), [#239](https://github.com/VlcekM/MeitouClient/pull/239) (prisoners of generated interior cages), [#240](https://github.com/VlcekM/MeitouClient/pull/240)
(treating a caged patient on its floor) and [#241](https://github.com/VlcekM/MeitouClient/pull/241) (ending a kitless treatment). All
four are merged.

## Follow-up holds (Observed, N = 1 each)

- **D:** no non-saved character for the whole hour, as on the original. The 7 dogs `sleep_on_floor` from 66 s.
- **E:** 32 of 32 slaves owned from 66 s, 25 to 30 mining. The original shows 32 by 198 s and 22 to 29 mining.
- **F:** the caged slaves went from 9 to 2 (original: 9 to 3), but mid-run more slowly: 7 stay caged until 1980 s, while the original
  is at 4 by 1254 s. Why is **Unknown**.
- **188:** 9 workmasters shouted at slaves of their lists, which hold 1 to 4 slaves each. The original shows `work_the_slaves` for 2
  to 5 Sentinels at each checkpoint.
- **A:** the 24 saved sleepers stay in bed all hour, with goal `go_home_and_go_to_bed` and order `use_bed`, as on the original.

## Still open

- **Captive jobs were not goals on Meitou.** Gathering, shouting, getting into a cage and similar slave work run as MeitouClient
  captive jobs, outside the AI's goal. Patch 0008 reported the mind's goal, so a Meitou slaver's goal never read
  `gather_slaves_from_cages` or `work_the_slaves`, even while it did that work. This was a projection gap of the adapter, not a
  behaviour difference. [Patch 0009](../integrations/meitou/README.md) reports the goal a running job runs. In one hold with the
  fixes above and patch 0009 (**Observed**, N = 1), Meitou's Holy Sentinels read `gather_slaves_from_cages` (7 at 66 s, down to 2
  as the cages empty) and `work_the_slaves` (1 to 3 at several checkpoints), where the original shows 4 to 6 and 2 to 5.
- **G. Shoppers:** native `shopping`, Meitou `relax_in_town_package` (106 of 136). Not diagnosed.
- **H. Guards:** native `stand_at_guard_node_hometown_outside`, Meitou `..._homebuilding_in_out` (140; the reverse 39). Not
  diagnosed.
- **J. Sleepers:** the native probe reports no goal during part of the bed time (198 pairs where Meitou reports
  `go_home_and_go_to_bed`). What the original holds then is **Unknown**.
- **Order `stand_at_node` against `move_on_free_will`** (54): Meitou still walks where the original already stands. The cause is
  **Unknown**.
- **Wild spawns during a hold.** In that same hold, Meitou's wild tick brought in a Starving bandit mob (7) and 2 escaped servants
  from a nearby sector, and 9 Wolves from a nest, about 10 km from the focus. The earlier holds had none, and neither does the
  original in an hour (**Observed**, N = 1 each). Why the original spawns nothing there is **Unknown**: this is the open part of D.
