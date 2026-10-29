<a id="inventaire-borné-dans-une-ville-chargée"></a>

# Bounded inventory in a populated town

Existing **500-row** limit permits a complete capture of **412 characters** observed in the update list near Heng. Intermediate capture limited to 250 remains correctly excluded. No plugin rebuild or loss of combat-snapshot ownership needed for this case.

Plugin **0.7.5, v100 x64, 17 MCP tools and three system hooks** unchanged. New collector uses only existing commands through real MCP stdio. Pilot checks coverage/admission; no performance or combat-cost comparison.

<a id="preuves-et-reproduction"></a>

## Evidence and reproduction

- Raw: `runtime/scenarios/heavy-inventory-20261028T040208Z.json`, SHA-256 **00c964cc855ef5c77b432eaadc2b2bcc38c171a3faa9882b991d633a21f8ad39**.
- Recomputed analysis: `runtime/heavy-inventory-analysis.json`.
- Final state/manifests: `runtime/scenarios/heavy-inventory-075-final.json`.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_heavy_inventory.py
& ./.venv/Scripts/python.exe tools/research/analyze_environment.py runtime/scenarios/heavy-inventory-20261028T040208Z.json --output runtime/heavy-inventory-analysis.json
```

Pilot reloads initial copy, prepares Heng, allows ten seconds of x1 streaming and three seconds stable readiness, then pauses. Collects limits **500, 250, 500**, without combat activation, then restores copy paused in finally. It neither saves the reconstructed scene nor retries until a desired population appears.

<a id="résultat"></a>

## Result

| Capture | Requested limit | Rows received | Total update list | Complete coverage | Admission |
| --- | ---: | ---: | ---: | --- | --- |
| First | 500 | 412 | 412 | yes | accepted |
| Intermediate | 250 | 250 | 412 | no | rejected |
| Last | 500 | 412 | 412 | yes | accepted |

Both full lists have exactly the same labels/multiplicities/positions. All three captures paused at **404,4196109771729 game hours**, with population/camera matching bracketing scene reads. Each inventory spans two or three frames; not an atomic snapshot of the whole game world. Thirty-seven name/faction groups repeat in full captures: labels still not persistent IDs.

JSON result **reserialized after reading** is44 112 bytes per full list versus 27 042 for partial. Not exact original network sizes: number formatting/envelope differ. Verified native network code independently enforces65 536 bytes including LF; above it returns explicit error instead of oversized response. Native responses succeeded in this pilot. No guarantee another 500-row list with longer names fits.

Report recomputes summaries from raw responses. Guard replay gives **accepted/rejected/accepted**, without inferring exhaustive difference from 250 intermediate rows. Relative timestamps absent in this format remain null; raw frames/clocks retained.

<a id="évolution-du-contrôleur-et-limites-restantes"></a>

## Controller changes and remaining limitations

Future `live_snapshot_horizon.py` controller now requests **500 rows by default**, configurable through `--environment-limit` from 1 to 500. Historical250-row Mongrel preflight stays separate evidence. Total exceeding received rows prevents admission; size/protocol error propagates and causes restoration, without claiming exhaustive collection.

Two independent limits remain: **500 rows and 64 KiB native response**. A scene above 500 entries, or oversized response below that cap, would require another bounded collector. Splitting reads of an unfrozen list would not prove consistency; possible pagination must copy values at an identified instant without retaining game pointers across frames. No such native change initiated without evidence it is necessary for currently observed scenes.

Environment guard in complete combat run not replayed natively; admission functions tested, and new real urban captures processed by those same functions. Historical quartet does not acquire this guard retrospectively.

<a id="validation-et-état-laissé"></a>

## Validation and state left

**168 Python tests pass in 4,00 s.** New cases cover complete450-row inventory, truncation501 to 500 and urban format with intermediate partial inventory. Plugin unchanged; no engine function optimized.

**702 KenshiProbe_validation files,702 KenshiProbe_test files and 738 managed-snapshot files** remain compliant with reference manifests. settings.cfg identical after pilot, recovery guards false, snapshot ownership preserved in same process. PID 19892, path/creation verified; initial copy reloaded paused, normal reference view, Edge scrolling=true, no active tracked combat or temporary camera control. Fresh watchdog, zero publication errors, config/activation boundary unchanged **28 October 22 h15 UTC**.

Administrator CPU-stack capture still pending. Next independent diagnostic could measure CPU distribution while paused/running in the same town, with fixed view/control inventories, to describe work remaining while paused. This would observe scope, without automatically attributing remaining CPU to rendering or a delta to a particular function.
