<a id="livraison-phase-1--kenshiprobe-095"></a>

# Phase 1 delivery — KenshiProbe 0.9.5

Phase 1 was **delivered and validated on 29 October 2026**: **original Kenshi** oracle, shared state0.1, canonical captures, proven saved identities, MCP-repeated scenarios, and supervision. It retains0.8.20 functionality and the existing directory structure. The comparator and MeitouClient adapter belong to phase 2. No new performance campaign was conducted.

The evidence below is local and ignored by Git; it distributes no save or game data. The [acceptance checklist](phase1-acceptance.md) maps the prompt's eight criteria to files and validations.

<a id="version-et-installation"></a>

## Version and installation

- Final DLL **0.9.5**, successful **Visual C++ 2010 x64/v100** build: `plugin/build/Release/KenshiProbe.dll`, **523 264 bytes**, SHA-256 `75739c8e64e17f3a78f482132c9be659aac7d55db7b3151b907b51944af5b580`.
- PDB: **11 447 296 bytes**, SHA-256 `51fa54bc8c0e96daa80b7dc3d6bb831d126a419d89f050899bbf0286af4aadfe`.
- Real environment: Kenshi **1.0.65 Steam**, RE_Kenshi **0.3.5**, KenshiLib **0.5.0**. Verified deployment: deployment-095.json (local evidence, not published).
- Schema remains **0.1**, without pointers, PID, tokens, source fingerprints, or C++ types. Identity provenance remains protocol metadata.

The0.9.5 fix concerns camera calibration/restoration. State, canonicalization, and identity-resolution algorithms from the final 0.9.3 captures remain unchanged. Evidence for these two DLLs is distinguished below.

<a id="vérifications-hors-jeu"></a>

## Offline verification

Final command from the root, with dependencies from `requirements-dev.txt`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=runtime/oracle-phase1/pytest-delivery-095-final-20261029 -p no:cacheprovider
```

**1 602 tests passed, 1 skipped, 96,51 seconds**. Full log (local evidence, not published). The sole skip concerns creation of an actual symbolic link, denied without Windows privilege/Developer Mode; rejection of simulated reparse attributes is tested. Tests isolate sockets and reject live port47800. Under the Windows sandbox, sockets and the stdio subprocess require authorized execution outside the sandbox; this is not a result from testing without local networking.

The suite covers schemas, defensive parser/protocol, MCP stdio, validation of every snapshot, fake game, scenarios, timeouts, errors and interruptions, recovery lock, watchdog, failed archives, and restart requests. The fake game produces identical bytes for the same state. Origin integration renews raw HANDs on every load and retains the same canonical snapshots across three repetitions.

Native v100 tests: **74 camera checks**, **107 origin checks** on0.9.5; previous unchanged checks include **52 identity**, **38 format**, JSON parser, command ownership, and statistics checks. **59 synthetic C++/Python states** have identical canonical bytes. Modern compilers do not replace v100.

New camera tests cover follow pivots at heights 0, 9,8, and 17,125, an actor moved on three axes after reload, interpolation before stabilization, stale tokens, settings drift, follow/no follow, free mode, and resumption after paused verification. These simulations do not replace the Kenshi tests below.

<a id="trois-exemples-réels-chacun-répété-trois-fois"></a>

## Three real examples, each repeated three times

The final **0.9.3** DLL, SHA-256 `ebce02cd618675e88d1cadf7a239b964b3a4347825ecae5e63c7da87c2d52f91`, ran all three examples through **MCP stdio**, reloading before every repetition: **9 repetitions, 27 snapshots**. Complete batch (local evidence, not published). All three cases completed, with restoration verified; the four protected saves and `settings.cfg` bytes remain unchanged.

| Example and report | Stable / variable fields at first checkpoint | Stable / variable fields at last checkpoint | Characters at last checkpoint, repetitions1 /2 /3 |
| --- | --- | --- | --- |
| Route (local evidence, not published) | 43 050 / 170 | 45 105 / 2 006 | 190 / 180 / 180 |
| Small battle (local evidence, not published) | 39 771 / 16 373 | 39 776 / 32 435 | 253 / 323 / 284 |
| Quiet city (local evidence, not published) | 42 042 / 3 165 | 42 253 / 5 636 | 130 / 132 / 140 |

A variable field may change value or be absent from a repetition. Reports retain these observations and actual temporal overshoots: maxima **0,320435**, **0,320893**, and **0,310593 calendar second**, respectively. These compare Kenshi repetitions, not engines. Population, positions, health, and tasks can diverge despite identical reloading.

The independent audit of 27 files (local evidence, not published) validates schema, counts, hashes, provenance, and byte identity **native = MCP copy = Python canonicalization**. A second delivery audit rechecked them. The route's first checkpoint contains **106 characters,35 squads,114 factions,12 882 relations**.

Ando, Hisako, and Ishida have individual state in the save; their current HANDs change container on load. Full SDK resolution allows publishing their saved HANDs in **all nine route snapshots**. Neither name, address, nor a simple I/S pair is used as a key. In the city, **80** saved-character identities are shared initially and **92** at 600 seconds. Variable membership of the three saved squads without character files supports activation-time generation for that cohort. An unresolved origin alone does not prove generation: its current HAND is retained. [Detailed audit](npc-identities-phase1.md).

<a id="validation-réelle-de-la-restitution-095"></a>

## Real validation of 0.9.5 restoration

The 0.9.5 recovery test (local evidence, not published) **passes**. It first verifies a deliberate `[2,1,-3]` offset, observed as an additional `[2,1,-3]` offset, then reloads and restores exactly the original journal's controls. Recorded controls remain unchanged, and `restore_required` becomes false only after verification.

The recovered reference includes center `[-50978.796875,1541.7958984375,2932.4765625]`, position `[-51489.6640625,2067.15087890625,2005.222900390625]`, signed zoom `-1181.855224609375`, quaternion, canonical Imai follow target, strategic mode, enabled scrolling, pause, and prepared selection1.

This repair addresses a real failure after restart: actor height had changed by **0,936035**, and a stable pose remained incorrect. Candidate0.9.4 then incorrectly treated the additional offset as the entire center−actor distance; its restoration failed. Evidence of that failure (local evidence, not published). These failures remain retained; reference and tolerances were not relaxed.

Protocol 0.9.5 prepares and observes a stable locked camera, then applies `current offset + requested center − observed center`. No constant height bias or actor movement. After release, a second window compares against the fixed reference: **three distinct frames over at least 0,5 second**, timeout **10 seconds**; center/position/zoom tolerances **0,05**, quaternion **0,0001**, selected speed **0,000001**. [Detailed contract](protocol.md).

<a id="rejeu-ville-sur-la-dll-livrée-095"></a>

## City replay on the delivered0.9.5 DLL

The final MCP series (local evidence, not published) is **complete**: **three repetitions, nine captures**, each schema-valid and byte-identical to the native file and its Python canonicalization. An independent audit rechecked all nine files, their hashes, and constant `ville-calme` provenance, fingerprint `sha256:1a7624e7e712526e03b37a3ee8d78bcd5499a0780b8eac5a1e7b0ddaf5c678c5`. All **32 MCP tools** are present. Stable/variable report (local evidence, not published).

| Checkpoint | Stable fields | Variable fields | Characters, repetitions1 /2 /3 |
| --- | --- | --- | --- |
| Initial | 42 029 | 3 748 | 111 / 106 / 118 |
| Two minutes | 41 792 | 4 294 | 111 / 106 / 118 |
| Ten minutes | 42 243 | 6 124 | 138 / 137 / 139 |

Maximum temporal overshoot is **0,121766 calendar second**. Two-phase restoration is verified, with **8 baseline observations and 8 after commit**. All four saves and settings are unchanged. The series named in this report represent **36 captures and 12 successful repetitions**, including nine captures/three repetitions directly on the delivered DLL.

<a id="watchdog-et-état-final"></a>

## Watchdog and final state

The real0.9.5 watchdog test (local evidence, not published) **passes**. It verifies path, PID, creation time, and command line of the owned process before its controlled exit: **45812 → 16548**. Supervision archives the log under `crashes/20261029T022312.138729Z`, reason `process_exit`, without archive error; archived-log SHA-256 `076366d35c5a3edbc28869a7e0120332da93b06cc63ec83e04248d598705f9fc`. The new game starts with another instance; recovery reloads `ville-calme`, prepares origins, and restores the verified camera/time reference.

The final read-only audit (local evidence, not published) confirms: built and installed DLL at the stated hash, listener **127.0.0.1:47800**, active watchdog, five historical hooks and three systems retained, world ready **in pause**, prepared selection **1**, compliant Imai follow target and pose, camera lock released, no pending token, and `restore_required:false`. The **four protected saves** and `settings.cfg` SHA-256 match the starting manifest. No game executable, data, or save appears among Git-publishable files.

Earlier failures, including the 0.9.3 watchdog test (local evidence, not published) that archived/restarted successfully but then failed restoration, remain archived. Their status is not rewritten. This batch stops after this check; no phase 2 or additional campaign starts.

<a id="non-testé-ou-non-démontré-universellement"></a>

## Not tested or not universally demonstrated

- MeitouClient adapter and cross-engine comparator: outside phase 1.
- Exhaustiveness of all in-memory objects, unloaded-region state, and atomicity against all internal workers.
- Engine determinism, stability of every identity across all saves, mods, and restarts. References without proven bindings remain current; real remapping of a squad with a different alias is not demonstrated in these scenes.
- All camera offsets/modes in all regions; following non-character objects, concurrent manual input, and immobility after the verification window.
- Loads triggered manually through the UI during a scenario; restoration of an unsaved game or a save other than the explicitly chosen one.
- Producing an actual engine-crash minidump: controlled exit proves log archiving and restart; optional dumps and copy failures are covered by synthetic tests. The frozen-heartbeat threshold is tested offline and has separate historical evidence; no new real freeze is induced for this batch.
- Installation on another machine, another game/SDK version, and Debug configuration. One actual symlink test remains skipped for Windows privilege.

<a id="todo-du-code-de-production"></a>

## Production-code TODOs

Two markers remain, independently inventoried in `plugin/`, `mcp-server/`, and `launcher/`:

1. **`ORACLE-ORDER-ENUM`**, `plugin/OracleState.h`: add a verified symbolic name if a future SDK exposes a task missing from the audited table. Until then, `order:null`; no invented type.
2. **`ORACLE-CAMERA-NONCHARACTER`**, same file: restorable follow targets are loaded characters. Any other target type requires a verified public inventory and remains explicitly rejected.

The former identity-canonicalization TODO is implemented. The [field-by-field table](state-coverage.md) distinguishes **Verified**, **Observed**, and **Unknown**; [open questions](research/open-questions.md) retain limitations and discoveries. The [installation guide](first-run.md) allows reproducing the first dump and scenarios with one's own local saves.
