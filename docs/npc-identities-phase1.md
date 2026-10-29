<a id="identités-des-pnj--audit-de-phase-1"></a>

# NPC identities — phase 1 audit

Since **0.9.3**, canonicalization uses save origins and the engine's public resolvers. The three saved Ando/Hisako/Ishida HANDs are linked to loaded objects whose C/CS differ, then published under their saved identity in all nine final 0.9.3 travel captures. All 27 final-batch captures are independently validated; their native/MCP/Python bytes match. The [delivery report](oracle-phase1-delivery.md) distinguishes this series from the 0.9.5 validation devoted to camera restoration.

The historical **0.9.1** audit retained below also supports generation of members on activation for a specific `ville-calme` cohort. It distinguishes that cohort from the three individual states already present in the old save. The internal chain responsible for the container change remains unknown, even though engine resolution of those three pairs is now observed.

State schema **0.1 remains unchanged and neutral**. Full `hand:TYPE:C:CS:I:S` identifiers remain opaque; native code replaces a current HAND with its saved HAND only after a proven complete binding. A name, position, definition or `I/S` pair never becomes a matching key. Without a resolved origin, the current HAND is retained; that absence alone does not prove generation.

<a id="preuve-reproductible-de-laudit-historique-091"></a>

## Reproducible evidence for the historical 0.9.1 audit

The [npc-identity-readonly-091.py](../runtime/oracle-phase1/npc-identity-readonly-091.py) reader and its [npc-identity-evidence-091.json](../runtime/oracle-phase1/npc-identity-evidence-091.json) output remain in `runtime/oracle-phase1/`, ignored by Git. They contain no copy of game files. The JSON retains SHA-256 hashes of saves read, captures compared, the reader and relevant SDK headers, together with exact keys and matches.

From the project root:

```powershell
.venv\Scripts\python.exe runtime/oracle-phase1/npc-identity-readonly-091.py
```

The program only reads the two saves `%LOCALAPPDATA%\kenshi\save\KenshiProbe_test` and `ville-calme`, archived captures and referenced headers. Its only write is the evidence JSON. It does not contact the game. It recalculates save-file hashes after reading and fails if content changed during this pass.

Reading follows the [published FCS format](https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/fcs-mod.md#record), confirmed by the public [FcsReader.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Fcs/FcsReader.cs) code: type-15 header, typed property tables, references and instances. Final slot lists are read according to [SaveFile.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveFile.cs). Every FCS file consulted reaches its exact end, including lists: 373 for the old save and 29 for `ville-calme`. The `.hkt` files and portrait are not decoded.

Characters are linked to states through their instance's state identifiers, as in [SaveGame.BuildCharacters](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveGame.cs). Only `.platoon` files named by the PLATOON index in `quick.save` serve as comparison references; six unreferenced files from the old save are excluded. Every identity comparison uses all five HAND components. Signed file integers are rendered unsigned while preserving their 32 bits, in accordance with the [SDK hand](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Include/kenshi/util/hand.h) fields and [Hand.cs](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/Hand.cs) keys.

This reader is limited to the type-15 files observed here; it rejects other versions. Successful structured reading does not validate the engine's entire semantics. No executable or decompiled code was used for this pass.

<a id="ville-calme--personnages-absents-de-la-sauvegarde-individuelle"></a>

## Quiet town: characters absent from individual save states

The nine captures come from `runs/ville-calme/20261029T000108.688978Z-ed2aa999`. All three repetitions reload the same save. The folder contains 21 `.platoon` files, 92 GAMESTATE_CHARACTER states and 25 PLATOON states.

| Game time | Characters, repetitions 1 / 2 / 3 | HANDs exactly present in saved states, per repetition | Other HANDs, repetitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| Initial | 111 / 103 / 99 | 80 / 80 / 80 | 31 / 23 / 19 |
| 120 s | 111 / 103 / 99 | 80 / 80 / 80 | 31 / 23 / 19 |
| 600 s | 124 / 135 / 132 | 92 / 92 / 92 | 32 / 43 / 40 |

Initially, all 80 HANDs shared by the three captures exactly match saved characters. Their union contains 153 HANDs. All 22 squad HANDs are identical across repetitions and present in `quick.save`.

Every initial character without a saved individual state belongs to these three squads:

| Saved PLATOON state | Saved and observed squad HAND | Observed membership, repetitions 1 / 2 / 3 |
| --- | --- | --- |
| Holy Nation Outlaws_57 | `hand:34:40:1166015616:0:0` | 7 / 1 / 1 |
| Starving Bandits_66 | `hand:34:41:30517578:0:0` | 15 / 11 / 9 |
| Dust Bandits_120 | `hand:34:42:615844736:0:0` | 9 / 11 / 9 |

All three records carry `never been activated=true` and `content file=platoon/`, with no associated character file. Their character serials and membership counts vary across loads while each squad's HAND stays identical. The fourth PLATOON in this state, `Dust Bandits_119` (`C=39`), appears in no initial capture. The [save documentation](https://github.com/VlcekM/MeitouClient/blob/master/docs/formats/save.md#folder-and-state-mapping) specifies that `platoon/` alone represents the absence of a file.

These observations support member creation when squads already saved in abstract form activate. The exact creation point inside loading is not instrumented. They do not establish that every NPC is recreated.

The twelve saved characters missing from initial captures come from `Shinobi Thieves_14.platoon` (8) and `Trade Ninjas_2.platoon` (4). All their full HANDs appear at 600 s in every repetition. Their late appearance therefore does not prove generation of new characters. At 600 s, the character intersection contains 92 HANDs, the union 207; squads have 24 shared HANDs, 29 in the union.

Player character Imai retains saved HAND `hand:1:1:751953152:1:3279785216`. This does not guarantee the same property for every entity.

**Runner status:** the nine dumps constitute state observations. The original campaign failed camera restoration, with an offset of about 0,17248 against a 0,05 tolerance; this audit does not present it as successful overall validation.

<a id="seconde-série-en-ville"></a>

## Second town series

The nine captures from `runs/ville-calme/20261029T001325.437085Z-06ebaeea` are compared to the same saved states. This pass reuses already hashed metadata and the reader's `compare_capture` / `intersections` functions, without decoding the 402 files again. Its results and new capture hashes are in `additional_city_runs` in the same evidence JSON. The earlier reproduction command regenerates the first pass; this supplement is obtained by applying those two functions to the second folder and `saves["ville-calme"]` from the JSON.

| Game time | Characters, repetitions 1 / 2 / 3 | HANDs exactly present in saved states, per repetition | Other HANDs, repetitions 1 / 2 / 3 |
| --- | --- | --- | --- |
| Initial | 101 / 103 / 110 | 80 / 80 / 80 | 21 / 23 / 30 |
| 120 s | 101 / 103 / 110 | 80 / 80 / 80 | 21 / 23 / 30 |
| 600 s | 123 / 125 / 131 | 92 / 92 / 92 | 31 / 33 / 39 |

New initial members still belong exclusively to `Holy Nation Outlaws_57` (1 / 3 / 7), `Starving Bandits_66` (12 / 10 / 15) and `Dust Bandits_120` (8 / 10 / 8), the three saved squads without individual states and never activated. All 22 initial squad HANDs are identical across repetitions. The character intersection contains 80 HANDs initially, 92 at 600 s; their unions contain 154 and 195. This second series therefore reconfirms the distinction between saved characters and members created on activation, without guaranteeing a universally stable identity.

This audit covers dump identities. Overall validation of the second runner's control restoration is reported separately in the [phase 1 validation](oracle-phase1-validation.md).

<a id="ancien-trajet--trois-états-de-personnages-déjà-sauvegardés"></a>

## Old travel run: three character states already saved

The three initial captures from `runs/trajet-escouade/20261028T233134.179400Z-04bb9a8d` each contain 106 characters, including 103 HANDs exactly present in `KenshiProbe_test`'s referenced character files.

The other three rows have matching values in these saved records:

| Observed name, used as description | Saved file and state | Saved HAND | C observed in all three captures |
| --- | --- | --- | --- |
| Ando | `Outlaw_8.platoon`, `18-Outlaw_8.platoon-INGAME` | `hand:1:372:2911010816:4:3090576128` | 12 |
| Hisako | `Outlaw_9.platoon`, `22-Outlaw_9.platoon-INGAME` | `hand:1:373:2914428672:5:1865356416` | 6 |
| Ishida | `Outlaw_10.platoon`, `20-Outlaw_10.platoon-INGAME` | `hand:1:374:3821533184:6:2201171968` | 4 |

For each row, `I` and `S`, name, faction, race and saved position rounded to JSON precision agree in all three captures. `CS` varies on every load. Associated saved PLATOONs carry `imprisoned=true`, `persistent=false`, `canref=false`; character states carry `slavestate=1` and `in something=2`.

An additional check searches directly for the five documented binary keys in each of the three small files: every key occurs only once and gives the same values as structured reading. These files reach their exact ends at 6 165, 7 566 and 6 808 bytes respectively.

Those value comparisons alone in the 0.9.1 audit favored the explanation of a restored state with a container change, without demonstrating the responsible call chain or engine alias resolution. Their JSON retains this historical qualification and every distinct HAND. The 0.9.3 engine evidence below is separate; `I/S` is still not assumed globally unique.

<a id="implémentation-093--origines-et-résolution-publique"></a>

## Implementation 0.9.3: origins and public resolution

The [production oracle_origins.py reader](../mcp-server/oracle_origins.py) belongs to this project and follows the public format in [FcsReader](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Fcs/FcsReader.cs), [SaveFile](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveFile.cs), [SaveGame](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/SaveGame.cs) and [Hand](https://github.com/VlcekM/MeitouClient/blob/master/src/Meitou.Data/Save/Hand.cs). It accepts type 15 only, reads structured records and their trailers to EOF, and explicitly rejects other types. `byteSize` is not used as a skip length.

`read_saved_origins(save_root, save_name)` reads only `quick.save` and the `.platoon` files named by its PLATOON states; `platoon/` alone means no individual file. Every origin retains the full HAND, relative file, state ID, record index and offset; characters also retain the collection, instance and indexed squad HAND. Limits cover file counts, bytes, strings, counts and origins. Unsafe Windows paths, links/junctions, duplicates and ambiguous associations are rejected. File int32 components become uint32 decimal values while preserving their bits.

Reading verifies file hashes before returning. `verify_saved_origins(save_root, manifest)` rereads them and compares hashes after loading, before committing the context. The SHA-256 fingerprint covers sorted relative-path/size/hash triples for `quick.save` and indexed character files; it does not claim to cover zones, portraits or orphan files. No save file is copied or changed. The [reader tests](../tests/test_oracle_origins.py) use synthetic fixtures only: 136 passes, one Windows symlink creation test skipped for lack of privilege, and a separate passing test for rejection of the reparse attribute.

The [MCP loading path](../mcp-server/oracle_runner.py) uses the public `SaveManager::getSavePath()` root as its reference and rejects contradictory configuration. It reads the manifest before `load_save`, waits for a ready paused world, rechecks the source, then sends full HANDs through `begin_saved_origins`, `add_saved_origins` in batches of at most 128, and `commit_saved_origins`. No partial context is published. The requested load name and world epoch determine the context; `SaveManager::getCurrentGame()` is not treated as proof of that name.

The probe constructs a HAND with the public [`hand(index, serial, type, container, containerSerial)`](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Include/kenshi/util/hand.h) constructor, then calls `getCharacter()` or `getPlatoon()`. The returned candidate must match an object in the loaded inventory; its pointer is not dereferenced to obtain an identity. The read command `resolve_saved_handles` separately exposes `saved_id`, `current_id` or `null`, `resolved` and `loaded`. It requires pause and accepts at most 128 full HANDs.

The [native current ↔ saved table](../plugin/OracleSavedOrigins.h) enforces a bijection of full HANDs and rejects collisions. Evidence is built at commit before atomic context publication; bindings are refreshed before captures and retained only for current HANDs still inventoried. Full equality can also retain a dead object still loaded even if the resolver no longer returns it. The cache retains no object pointer. A new load, unavailable world or world transition invalidates this context, including when a world address is reused.

Native canonicalization replaces character and squad IDs, `squad_id`, order targets, members and leaders using proven bindings only, then sorts collections and rejects duplicates. Other references remain under their current HAND. `identity_source`, with name, fingerprint and counters, belongs in the tool response and report, outside common state 0.1. A dump without a prepared context fails with `origin_context_required`. Character camera following also uses the table published at commit. Recovery in 0.9.5 with Imai's canonical follow identity and a deliberate XYZ offset is verified in the [delivery report](oracle-phase1-delivery.md), separately from this initial trial.

<a id="première-preuve-réelle-093-et-limites"></a>

## First real 0.9.3 evidence and limits

The local [identities-smoke-093.json](../runtime/oracle-phase1/identities-smoke-093.json) file, outside Git, contains `completed=true`. The `KenshiProbe_test` context has **1 470 origins**, **138 loaded bindings**, **three remapped characters** and **zero remapped squads**. The three observed public calls resolve these pairs:

| Saved HAND | Current HAND returned in the loaded inventory |
| --- | --- |
| `hand:1:372:2911010816:4:3090576128` | `hand:1:12:1312499968:4:3090576128` |
| `hand:1:373:2914428672:5:1865356416` | `hand:1:6:3035278336:5:1865356416` |
| `hand:1:374:3821533184:6:2201171968` | `hand:1:4:2488159232:6:2201171968` |

The dump's three rows carry the saved HANDs; their corresponding current HANDs no longer appear. Its 106 characters, 35 squads, 114 factions and 12 882 relations form a valid 0.1 state of 1 125 265 bytes, identical in native, MCP and canonical Python output: SHA-256 `ec6ab440861f637f1d1e087fd712b06be0b58e2147e6f44662cf5dd0fe0e9824`. The identity source has fingerprint `sha256:c9a3ec246336efb3ea9fb68f48753f3910131590931caf496ba14826c864379d`. The same trial retains explicit rejection of a dump without preparation.

In this record, `ping.current_save` still says `ville-calme` while the prepared context and verified source name `KenshiProbe_test`. This diagnostic confirms an internal name getter can remain stale after loading; the context's source comes from the explicitly requested load and verified files.

The implementation resolves the old remapping TODO, and engine resolution is observed for these three characters. It explains neither the internal redirect chain nor a universal identity across games, saves or restarts. No absence of a resolved origin is converted into proof of generation. This initial trial does not validate squad remapping, real restoration of canonical camera following, or the final candidate's three repetitions. Those validations and publication status are in the [delivery report](oracle-phase1-delivery.md).

Other public leads still offer no global identity guarantee: `RootObject::getInstanceID()` / `getLayoutInstanceID()` are not demonstrated stable for characters; `Platoon::getPlatoonStringID()` concerns the squad; `getGameData()->stringID` may be shared; `Character::getIDForMemoryTagging()` still returns a HAND. No assumed access to the `HandleManager` singleton, name, position or I/S pair replaces complete evidence.
