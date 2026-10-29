<a id="environnement-visible-après-rechargement-du-snapshot"></a>

# Visible environment after reloading the snapshot

Two reloads of the same battle snapshot, **kept paused**, produce update lists of **172 then 147 characters**. Yet the two tracked actors have exactly the same positions, medical values and game time. The new audit shows that the visible environment already differs before any speed activation; cohort stability alone therefore cannot qualify a combat-cost comparison.

The plugin remains **0.7.5, v100 x64, 17 MCP tools and three system hooks**. The Python collector reuses existing get_scene_state and list_characters through a real MCP stdio session. No new hook, deployment, NPC creation or save writing.

<a id="preuves"></a>

## Evidence

- Raw evidence: `runtime/scenarios/environment-preflight-20261028T034733Z.json`, SHA-256 **ba8afb2e688d7bb9b61f15f4041e0673fdd0e0975ac39caab24e1955a40dcd1c**.
- Analysis recomputed from raw responses: `runtime/environment-analysis.json`.
- Fresh final state: `runtime/scenarios/environment-preflight-075-final.json`, hash-linked to complete-manifest evidence.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_environment_preflight.py
& ./.venv/Scripts/python.exe tools/research/analyze_environment.py runtime/scenarios/environment-preflight-20261028T034733Z.json
```

The first command still requires ownership of snapshot `KenshiProbe_test_scene_20261028T022539600581Z` within the same plugin session. It does not activate battle simulation and reloads the initial copy paused at the end. This pilot's save parameters are explicit in the script; it creates no replacement snapshot. The second command runs offline and rejects a recorded summary that no longer matches the raw evidence.

## Observation

Each reload is observed twice, approximately 0,3–0,4 second and then 2,0 seconds after readiness. Each capture brackets the inventory with two scene reads, separated here by two frames. All four captures are complete for the requested update list, paused, with matching time, camera and population count at their boundaries. **They are not atomic captures of the entire game world.**

| Faction | Reload 1, two captures | Reload 2, two captures |
| --- | ---: | ---: |
| Bloodraiders | 1 | 1 |
| Drifters | 1 | 1 |
| Fogmen | 74 | 48 |
| Mercenary Guild | 7 | 7 |
| Mongrel | 85 | 86 |
| Nameless | 2 | 2 |
| Skeletons | 1 | 1 |
| Tech Hunters | 1 | 1 |
| **Total** | **172** | **147** |

Within one reload, both inventories have exactly the same name/faction multiplicities and positions. Across reloads, label differences are: 26 fewer Fogman/Fogmen occurrences and one fewer Ex-Servant/Mongrel; one additional Outlaw/Mongrel and one additional Shinobi Citizen/Mongrel. These are differences in the observed list; they prove neither spawning, death nor movement of identified actors. This observation does not establish the cause of the variation.

Ten label groups repeat in each inventory. Names and factions are therefore not individual identities. Analysis retains multiplicities, sorts rows before hashing and separates the label fingerprint from the position fingerprint; reordering alone does not create an artificial change. Earlier snapshot-paused-settling-075 observations already had counts stable over five seconds but different across reloads (172 then 162). Waiting without new evidence is not presented as a remedy.

All four captures find the two reference actors with zero medical, spatial and clock differences, at **404,3666667938232 hours**. The environmental difference is thus visible even though the preceding cohort guard accepts the starts. This reinforces limitations already observed in the x1/x5 quartet without causally explaining its damage or CPU times.

<a id="garde-ajouté-aux-futurs-essais"></a>

## Guard added to future experiments

`live_snapshot_horizon.py` now collects this environment **before any speed command**. The first accepted environment is the reference; an incomplete, changing, unpaused capture or one with different labels/positions is retained with an exclusion reason, then the campaign stops and restores the copy. No new reload loop opportunistically searches for a state that passes the guard.

This pilot's query limit is **250 rows**. A response shorter than total_update_list is not considered exhaustive, even if the cause is something other than that limit. Protocol or response-size errors propagate; the collector does not claim a complete list after an error. Scene fields bracket reads without supplying persistent identity or every AI/equipment state. The heavy-inventory-measurements.md follow-up subsequently validates 412 rows with the existing limit of 500, now used by default in the horizon controller; the 64 KiB network limit remains independent.

The guard is tested offline and replayed against the four existing native captures: **accepted, accepted, rejected, rejected** relative to the first. This replay is explicit in the report. No new battle quartet was run to repeat the already-established comparability failure; integration of the guard into a future native battle run remains unobserved. Even equal visible state would not prove complete determinization.

<a id="validation-et-état-laissé"></a>

## Validation and state left behind

**165 Python tests pass in 4,01 s.** New cases cover repeated names, row order, label variation at equal count, distinct positions, incomplete/nonfinite data, changing clock/pause/camera, process identity and summary/raw disagreement.

Complete manifests still match: **702 files for KenshiProbe_validation, 702 for KenshiProbe_test, 738 for the snapshot**. settings.cfg is identical after the pilot and recovery guards remain false. PID 19892, its path and creation time are verified; a ready paused game, normal source camera, Edge scrolling=true, no active tracked battle or temporary control left. Fresh watchdog, zero publication errors, unchanged configuration/activation deadline **October 28 at 22 h 15 UTC**. No campaign helper remains active.

Administrator CPU-stack capture is still pending, without a new trace. Further work must establish a comparable environment and task criterion, or attribute other threads by stacks if the pilot becomes available. Neither the cause of inventory variation nor an optimization gain is claimed.
