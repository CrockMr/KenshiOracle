<a id="audit-hors-jeu-des-appels-retenus"></a>

# Offline audit of retained calls

analyze_navigation.py reads JSON measurements without connecting to the game. It indexes responses, manifests and quality notes by SHA-256, identifying a call by process/creation time/thread/start QPC timestamp. Contradictory observations for one identity cause an error, never silent merging.

Run from root with usual PYTHONPATH:

```powershell
.venv/Scripts/python.exe tools/research/analyze_navigation.py --root runtime/measurements --output runtime/navigation-analysis.json
```

Initial audit through 0.6.2 grouped35 observations into **22 distinct calls**:13 duplicates came from overlapping windows/context reads. Eighteen retained calls returned false and four true. **Not a navigation failure rate**: only above-threshold calls still in the buffer are represented.

Four distinct calls occur in windows with per-window camera guards, fourteen under older endpoint-only checks, four only in transition contexts. Seven have individual CPU, including four false returns described in navigation-diagnosis.md. x1 condition with drifting camera retained for traceability but excluded from controlled group. Restoration failure after the next pair does not erase completed measurements; recovery remains separate evidence.

Tool also searches key/parameter pairs recurring with different XYZ. None in this first small vector set; absence establishes neither mesh stability nor cache safety. Full arguments available for only some slow calls, world coordinate frame not established.

SDK NavMesh::findPath signature returns boolean and hkArray<EdgePathNode,...>&, with no detailed termination code. Other reads such as pathExists, validateFaceKey, isInterior or getWorldShift are not reason codes; locking invariants unproven here. Next version therefore counts returns of **all** calls and observes output-array size, without inventing false-return cause or rerunning engine computation.

After 0.6.3 campaign, audit contains44 observations, **27 distinct calls and 17 duplicates removed**. Nineteen false/eight true remain retained above-threshold calls, not a global rate. Nine context-only calls stay separate from stabilized windows. Each provenance also states whether call precedes, crosses or follows preparation frame:180 ms call in last x5 read precedes preparation, hence not attributed to new-scene work. See simulation-clock-measurements.md for new complete counters/clock throughput.

<a id="intégration-explicite-des-captures-de-bataille"></a>

## Explicit battle-capture integration

Auditor now accepts `live_battle.py` format without converting it to stabilized town window:

```powershell
.venv/Scripts/python.exe tools/research/analyze_navigation.py --root runtime/measurements --battle-root runtime/scenarios --output runtime/navigation-analysis-with-battles.json
```

Running on existing data produces **62 observations,45 distinct calls and 17 duplicates removed**. Eight battle files retain fingerprints/provenance; two lacking final windows excluded with explicit reasons. Six completed captures contribute18 retained calls in distinct `battle_tail` phase. Older town groups stay separate. Total27 false/18 true still concerns retained above-threshold sample, not all engine calls.

Two false returns have nonempty output arrays: **0→19** elements,140,917 ms wall/140,625 ms CPU in two-actor battle; **0→6**,130,579 ms/125 ms CPU in ten-actor battle. Subsequent validity/use of elements not attested. False alone does not establish “no path elements provided” or justify failure-cache design without retaining other semantics.

Battle camera checks named `per_observation`, distinct from `per_window`. Audit notably marks `ends_after_last_observation` when final statistics extend beyond last camera read; it does not certify unobserved frames. Preparation frame comes from first scene after creation and stays labeled accordingly. Call still lacks character identity even when it ends after preparation.

Retained-call identity now requires PID **and** creation time; PID alone rejected. PID disagreement between battle capture/resources also rejected. Seven added tests cover nonempty outputs, phases, observation bound, identity, cross-format deduplication, missing capture and invalid camera.

Four groups share keys/parameters but have different XYZ. Confirms keys alone do not describe complete geometric arguments. Even identical captured arguments do not prove mesh, door or streaming stability; no cache safety established.

<a id="contexte-supplémentaire-du-relevé-cpu-par-thread"></a>

## Additional per-thread CPU context

Campaign `battle-20261028T025346Z.json` adds a 3600-frame diagnostic read, separate from 600-frame battle tail. Auditor retains `battle_diagnostic_context` phase, its own observation bounds and truncation flag: **66 slow calls counted, only 32 retained**. Calls visible in both phases merged by identity without borrowing the other phase's camera bounds.

Updated audit contains **97 observations,77 distinct calls and 20 duplicates removed**:30 false/47 true among retained calls, still no inferred global failure rate. Nine battle files indexed, two without windows excluded;21 calls in their measurement tails,32 in new context,50 distinct calls in union of battle phases. Five false returns have nonempty outputs; seven groups share keys/parameters with different XYZ. Expanded context becomes neither controlled battle window nor character identity.

Three tests check context/tail deduplication, separate bounds and truncation provenance. See thread-cpu-measurements.md for thread-role scope/limitations.
