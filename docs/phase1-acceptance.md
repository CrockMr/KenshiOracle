<a id="phase-1--contrôle-dacceptation-de-la-livraison-095"></a>

# Phase 1: delivery 0.9.5 acceptance check

This checklist maps the eight phase 1 criteria below to code and local evidence as of 29 October 2026. **All eight criteria are attested within documented scope; no blocking required gap remains identified.** The full suite, explicit camera recovery, three `ville-calme` repetitions and real watchdog recovery with final restoration under 0.9.5 are complete. Coverage limitations below remain explicit.

Deployed DLL **0.9.5** has SHA-256 `75739c8e64e17f3a78f482132c9be659aac7d55db7b3151b907b51944af5b580`; deployment-095.json (local evidence, not published) confirms it loaded with the world ready and paused. The earlier **27 real 0.9.3 snapshots** use `ebce02cd618675e88d1cadf7a239b964b3a4347825ecae5e63c7da87c2d52f91`, recorded in delivery-live-batch-093.json (local evidence, not published). This evidence is not reassigned to the new DLL. Initial `identities-smoke-093.json` and `live-trajet-093.json` trials also remain separate. Large evidence files and game data are local, Git-ignored.

<a id="les-huit-critères-du-prompt"></a>

## The prompt's eight criteria

| Criterion | Checked evidence | State at this review |
| --- | --- | --- |
| **1. Pytest: schemas, protocol, MCP, scenarios, watchdog** | Final full output (local evidence, not published): **1 602 passes, one skip, 96,51 s**. Tests reject real port 47800. Skip concerns the Windows symlink test in `test_oracle_origins.py`, lacking privilege; synthetic reparse-point checks pass. | **Attested on final 0.9.5 sources.** Skip and reason remain explicit. |
| **2. Valid fake game, same states byte-identical** | Schema 0.1, golden bytes, sorting, shared rounding, Unicode, explicit null. FCS integration renews raw identities over five loads and retains identical snapshots for each of two checkpoints across three repetitions. `native-canonical.json` also retains the historical comparison of **59 synthetic states** in C++/Python. | **Covered by final suite.** Identical bytes do not prove engine determinism. |
| **3. v100 x64 probe and example structure** | [Project](../plugin/KenshiProbe.vcxproj): `PlatformToolset=v100`, x64 configurations, examples' KenshiLib/Ogre/Boost dependencies. C++ entry point `startPlugin`, RE_Kenshi manifest, Win32 thread/lock/clock APIs. Deployed build recognized as 0.9.5. No C++11 `thread`, `mutex`, `atomic` or `chrono` include. [GPLv3 license](../LICENSE). | **Checked.** Dedicated native scripts remain reproducible through `tests/*-v100.cmd`. |
| **4. Protocol, coverage, open questions, first run** | [Protocol](protocol.md), [coverage](state-coverage.md), [open questions](research/open-questions.md), [installation](first-run.md) present. Coverage cites SDK declarations and separates Verified, Observed and Unknown. Protocol/installation explain automatic registry and two-phase 0.9.5 restoration; delivery report retains final evidence and history. | **Attested**, with documented certainty levels and limitations. |
| **5. One-page README: purpose and architecture** | [README](../README.md) presents original Kenshi side, plugin, MCP, watchdog, schemas, scenarios, identity contract and installation links. Comparator and C# adapter remain phase 2 work. | **Checked**, 0.9.5 version stated without erasing history. |
| **6. Real dump valid against state.schema.json** | **27 captures in 0.9.3**, then **nine town captures in 0.9.5**, independently rechecked: schema, canonicalization, SHA-256 and equality with native files. Provenance stays outside common contract and its fingerprint matches each series' report. | **Attested on both versions**, with separate evidence. 0.9.5 town series confirms nine compliant files after reloading. |
| **7. Real scenario repeated at least three times, stable/variable report** | In 0.9.3: travel (local evidence, not published), battle (local evidence, not published) and town (local evidence, not published), each three repetitions/nine snapshots. In 0.9.5: new town run (local evidence, not published), three repetitions, nine snapshots, two-phase restoration verified and protected saves unchanged. | **Attested in 0.9.3 for all three examples and in 0.9.5 for ville-calme with modified restoration.** |
| **8. Final report: tested, untested and every TODO** | [Delivery report](oracle-phase1-delivery.md) combines final suite, three examples with versions, watchdog recovery, final town restoration, unperformed trials and two exact code TODOs. Historical reports retain failures/limitations. | **Attested**, without attributing an older DLL's results to the new one. |

<a id="contraintes-et-invariants-vérifiés-dans-le-code"></a>

## Constraints and invariants verified in code

- **Neutral common state 0.1.** Clock, loaded characters, per-part health, immediate task, squads, factions and directional relations defined in [schema](../schema/state.schema.json). No address, PID, wall clock, adapter name, token or source fingerprint enters this state. Keys/lists and numbers follow documented canonical encoding.
- **Persistent origins.** Project-owned reader accepts public FCS type 15, bounds volumes/counts, reads only `quick.save` and indexed platoon files, rejects ambiguities/unexpected paths. Files hashed during reading and rechecked after loading. Public `SaveManager::getSavePath()` root authoritative; conflicting configuration fails before loading.
- **SDK-proven aliases.** Five complete components reconstruct public `hand`; `getCharacter()` / `getPlatoon()` compared with loaded census without dereferencing an external candidate. Binding must be bijective and same-type. No name, position, definition, address or I/S pair serves as identity. Unresolved origin retains current HAND and is not automatically called generated.
- **Atomic registry publication.** `begin/add/commit_saved_origins` use a session-bound token, complete count and batches of 1 to 128, at most 100 000 origins. Commit constructs/checks a candidate before swapping; ambiguity retains old context and pending token. World transitions invalidate context and revoke source name outside explicit probe loading.
- **Consistent references and commands.** Canonicalization affects only IDs, squad, task subject, members and leader. Saved order/follow inputs resolve to loaded actors before mutation. Following exposes the canonical cache at commit. In 0.9.5, preparation retains pause/lock; stable observation measures the actual pivot, then one commit applies additional `current offset + requested center − observed center`. Pose checked after release; requested resume follows. Base height is not an assumed constant.
- **Thread and protocol.** Listens only on 127.0.0.1, configurable port, identified JSON lines, line limits and defensive parser. Network does not read engine objects; forwards commands under `CRITICAL_SECTION`. Public GameWorld/Renderer hooks execute them and publish heartbeat. Logs prefixed `[KenshiOracle]`. Independent mapping counts **27 native commands including heartbeat, 32 MCP tools and no missing mapping**.
- **Procedurally reproducible scenarios.** Reload before each repetition, explicitly known speed, same-source checks, relative calendar times, actions ordered before checkpoints, overshoots retained and identity-based variability. Different instance invalidates execution. Restoration registry disarmed only after stable control verification.
- **Deadlines and supervision.** Transport defaults to 10 s; load/run_until operations 120 s and campaign 1 800 s, configurable and bounded. Watchdog monitors only its owned process, respects startup/loading grace and archives before restart. Archive, state-publication or diagnostic failures remain nonfatal. Request read bounded; errors published, acknowledgment survives denied unlink, same token cannot cause restart loops and an observed new token is preserved.
- **Scope retained.** `get_frame_stats` keeps default `aggregates`; no additional performance campaign. Executables, saves, data and local dependencies Git-ignored. New native calls come from public headers; no decompiled code added.

<a id="récupération-caméra-095-attestée"></a>

## Attested 0.9.5 camera recovery

recovery-camera-095.json (local evidence, not published) reports `completed:true` and `nondefault_offset_verified:true`. Fix tested with requested displacement **[2, 1, −3]**: observed center moves from `[-50978.796875,1541.7958984375,2932.4765625]` to `[-50976.796875,1542.7958984375,2929.4765625]`. Subsequent recovery checks the original reference retained in the registry, recovers character following and disarms `restore_required`. It checks two windows, before/after commit, without altering the reference to make the trial pass.

<a id="ville-calme-095-attestée"></a>

## Attested ville-calme 0.9.5

delivery-ville-calme-095.json (local evidence, not published) confirms three completed repetitions, **nine captures**, 32 advertised MCP tools, exactly restored settings and four unchanged protected saves. The runner report (local evidence, not published) retains variability, overshoots and observations from both restoration windows.

Independent reread of nine files validates schema 0.1, every report SHA-256 and **copy = native source = canonical bytes**. Every capture retains `save_name:"ville-calme"` and the same provenance fingerprint `sha256:1a7624e7e712526e03b37a3ee8d78bcd5499a0780b8eac5a1e7b0ddaf5c678c5`. Instance stays `45812:1232830552` throughout the series. Final restoration recovers character following, pause, expected center and null camera token, with lock released.

<a id="watchdog-et-restitution-finale-095-attestés"></a>

## Attested watchdog and final restoration 0.9.5

watchdog-runtime-095.json (local evidence, not published) reports `completed:true` and `stage:"city_restored_in_pause"`. Controlled exit of owned process **45812** triggers a `process_exit` archive, then restart as **16548**. Directory `crashes/20261029T022312.138729Z` retains `reason.txt` and log; independently reread SHA-256 `076366d35c5a3edbc28869a7e0120332da93b06cc63ec83e04248d598705f9fc` matches evidence.

Recovery reloads `ville-calme`, prepares origins then verifies paused pose against the registry's original reference. Settings and four protected saves unchanged. This controlled exit validates recovery, not a spontaneous engine crash or proof of minidump creation.

The final read-only audit (local evidence, not published) confirms `completed:true`, `settings_match_preflight:true`, `guard_required:false`, same 0.9.5 DLL, **127.0.0.1:47800** listener, paused world and prepared selection **1**. Imai following restored, camera lock released and `camera_restore_token` null. Four protected saves unchanged; list of Git-publishable game files empty. No required validation remains pending in this checklist.

The **two exact code TODOs** remain `ORACLE-ORDER-ENUM` (future task type absent from audited enumeration) and `ORACLE-CAMERA-NONCHARACTER` (following an object other than a loaded character). Identity remapping is implemented; its old TODO must no longer be presented as missing code. The [delivery report](oracle-phase1-delivery.md) retains each series' checks, versions and limitations.

Not universally demonstrated: completeness of every in-memory object, atomicity against internal workers, game determinism, identity across all saves/restarts, every camera mode/offset, support for every UI-initiated load. A bounded batch's success must not erase these limitations. MeitouClient adapter and cross-engine comparator remain outside phase 1.
