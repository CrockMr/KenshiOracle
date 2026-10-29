# HavokCharacter::update — 0.8.10

Probe finds **528882 completed calls** on the non-render SDK role at Heng x5. Across 2832 selected frames, **105,071372 ms inclusive wall time**, mean **0,037101 ms/frame**, maximum **0,059500 ms/call**. No completed call in pause windows. Observed cost cannot explain the whole worker's CPU and is not exclusive CPU cost.

Version 0.8.10 compiles in **v100 x64**, installed and verified through real MCP. **544 tests pass in 21,96 s**, native selector/bucket/depth trials successful. Still 17 tools/three probes charsUpdate/findPath/Havok; Medical replaced in the single selectable slot, no engine algorithm changed or gain claimed.

<a id="pourquoi-cette-fonction"></a>

## Why this function

Twelve engine RIPs previously captured on the non-render role in separate series 0.8.9 annotated in `runtime/worker-rip-089/annotations.json`. Raw source retains SHA **3d8cab8cf198d92ef47033ad7f56ab79f60c12d1a66fd196608a12c90657875d**. Project tools verify the same historical process39204/native creation 134376639120505830, retained bases/modules, SDK exports/stubs and all loaded-table values before/after annotation. Binding verified at annotation time, without claiming the table was read during historical capture.

Five regions join named SDK entries: NavMesh::getClosestPoint, Character::getCharacterMemoryTag, Blackboard::getMissionTown, HavokCharacter::update and Character::isInCombatMode. Each observed once; five other regions lack SDK aliases and two addresses lack unwind regions. No neighboring-symbol search replaces these unknowns. .pdata metadata retain irregular ordering and possible ambiguities; an unwind region does not necessarily define an entire source function body. Counts give no per-function CPU frequency.

HavokCharacter.h:98 declares **public void update(float time)**, nonvirtual, nonstatic, nonconst. Header 7012 bytes, SHA **0cc4b2e36748a9259d1f728d79974638950c8a2350c4f77a7bffa8099294dcf9**. Independent sdk_stack_mapping subagent review: unique export/slot3912, actual entry0x147f90 and region `[0x147f90,0x148a77)` containing RIP 0x1483a9. Header's historical comment0x147eb0 differs; none of these numeric addresses copied into plugin.

REA skill applied for native verification. Opening confirms EXE SHA **504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e**, but first Ghidra query expires during import/analysis at 330 s. No Ghidra containment result claimed; no memory error confirmed. Full diagnostic `runtime/worker-rip-089/rea-container-timeout.json`. Following remediation, temporary next-start deadline raised to 900000 ms, then session closed: open=false/cleanup_pending=false, recovery-cleanup/after-close evidence retained. No identical import relaunched; independent signature/SDK matching sufficient for this probe. Python-tool annotations are not presented as REA Evidence.

<a id="implémentation-et-déploiement"></a>

## Implementation and deployment

`KENSHI_PROBE_FUNCTION_TARGET=havokCharacterUpdate`, original/wrapper typed `void(HavokCharacter*,float)`, float argument forwarded unchanged, original called once. GetRealAddress resolves `&HavokCharacter::update`; AddHook retains typed trampoline. Existing depth guard/buckets reused; collection lock does not cover original call. No cast from AI*, no object/layout change. Ping advertises `havok_character_update_profiling`, generic statistics use actual name; Medical/Zone/AI/charsUpdateUT/physics aliases inactive.

Per-call CPU disabled; thread creation retained through independent TLS cache. The 528882 calls have no CPU measurement, totals null rather than measured zeros. Instrumentation has unsubtracted cost. Build reports EdgeCache class/struct mismatch in SDK headers; compilation/linking succeed without new dependency correction.

Archive `crashes/20261028T140020118382Z-deployment-0810`, evidence `runtime/deploy-0810.json`, previous game39204/helpers14112/33564 freshly verified before stopping only them. DLL0.8.9/config/settings/log preserved. First watchdog fails before launching a game because new script omitted PYTHONPATH; logs `runtime/watchdog-0810-first-launch.*.log` retained. Script corrected with absolute paths, hidden launch successful; first smoke timed out during this absence of game, not an engine crash. Second smoke succeeds: `runtime/havok-0810-smoke.json`.

Owned 0.8.10 symbols under runtime/symbols/0.8.10: DLL SHA **b2e0a24dadf6ebc0b1f75e8d5fbdad9e1cbf9ba082a7782061a669335c2b8c19**, PDB **d61f24277080dd68bf4b799c5fa35499c3874268b1abb7bf6d066305f6a6e4f3**. No game file, SDK, save or decompiled code in owned-source checkpoint.

## Heng pause/x5/pause

Raw `runtime/scenarios/pause-cpu-x5-adaptive-20261028T140511Z.json`, completed=true, SHA **60d74111457fa6d932efd5bf41d19fbf8fee96c3c497f0e57ba535ec8355f34a**. Final analysis `runtime/havok-0810-analysis-stable.json`, reproducible with analyze_profiled_function.py. First `runtime/havok-0810-analysis.json` report retained. No test/build during measurement.

Replay revealed unstable ranking when multiple threads share maximum quantized CPU. Sort now adds TID then creation as tie-breakers, including at the twelve-row cutoff. Two tests check ties and Python processes with different hash seeds. `runtime/havok-0810-canonical-compatibility.json` replays seven reports: all counters/retained rows recomputed from raw; only tie ordering of first Havok report changes, no membership change. Six earlier historical reports retain fields. Analysis correction required neither new game trial nor DLL.

| Phase | Frames/count | Mean process CPU | Simulated progression | Full inventories |
|---|---|---:|---:|---:|
| Pause before |7622..10842/3221|1,796779 logical processors|0 h|400→400|
| x5 |11260..14091/2832|2,388037|+0,933182 h|423→456|
| Pause after |14541..17365/2825|1,744572|0 h|456→456|

OS durations 20,375/20,375/20,313 s, process CPU 36,609375/48,65625/35,4375 s. Signed residuals **−0,015625/+0,046875/−0,046875 s**, one identity without second endpoint in first pause and two in last, none omitted at x5. Active clock +0,933181763 h over 20,361778 s; inventories agree with bracketing scenes, but population/streaming evolve. Mean callback intervals 6,319963/7,177477/7,178946 ms and p99 9,5978/11,5935/11,0167 ms do not guarantee displayed FPS.

All x5 Havok calls on **TID39604/creation FILETIME 134376698083790089**, joined to Windows counters and SDK role world_ai_non_render. Zero nested entries skipped/truncation. Whole thread consumes **6 s CPU** over 20,375 s, including 4,046875 user/1,953125 kernel. No exclusive coverage computed between wall calls and this OS window. Main/render thread34996/creation134376697962686336 consumes 16,078125 s CPU at x5; worker 5844 consumes 5,09375 s, function unknown. Do not transfer old TIDs or BirdManager name to it.

Final pause windows have zero Havok calls. Final 3600-frame context still contains 64462 calls because it overlaps active phase; this is not Havok activity during the final paused window. Compact window payloads 48456/57444/48469 bytes, contexts 48459/58551/48933, below 64 KiB in these captures. Navigation counts 1227 calls at x5; this does not define exclusive cost of the non-render worker.

<a id="état-final-et-suite"></a>

## Final state and continuation

`runtime/havok-0810-final.json` confirms game **19264/Unix creation 1793196196.268632**, paused copy/multiplier0 at **404,3333339691162 h**, normal camera/temporary control released/Edge=true. 702/702/738 source/copy/snapshot files compliant, settings identical to before this deployment, guards false. Fresh watchdog without error, WPR inactive, no remaining controller, 17 tools/seven roles/three probes. No administrator access requested. Helpers17784/32436 identified in audit; recheck exe/command/creation before stopping. Deadline28 October 22 h15 UTC unchanged.

This method's low duration under measured conditions does not exclude future peaks. Continue with a heavy-combat condition or a broader correctly resolved SDK boundary, separating initial bursts from steady operation. Function names, RIP counts and whole-thread costs do not suffice to claim a bottleneck or optimization; successive campaigns are not a causal comparison.
