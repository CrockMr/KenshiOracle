<a id="ogrerootrenderoneframe--mesures-0818"></a>

# Ogre::Root::renderOneFrame — 0.8.18 measurements

The **no-argument** original measures **7,064655 ms wall per active frame at Heng**, versus **7,067360 ms** between callbacks. Entry provides a broader boundary than previously measured GameWorld/Renderer entries, notably including callbacks, nested services and waits. **No exclusive CPU, GPU time, displayed FPS or engine gain inferred.** Earlier campaigns remain separate cohorts; their times are not subtracted from these.

Version 0.8.18 remains **v100 x64,17 MCP tools and three profiled systems**: charsUpdate,findPath,Root. Root replaces Renderer selection; MainLoop/Havok not profiled. Three dedicated detours plus two service detours give **five effective installations**, versus four in Renderer mode reusing its service hook. Sample **696 bytes**, chars history **2523600** unchanged.

<a id="api-export-et-binding-réellement-vérifiés"></a>

## Actually verified API, export and binding

Supplied SDK declares **bool Ogre::Root::renderOneFrame(void)** in Include/ogre/OgreRoot.h:558; distinct Real overload at 566. Header SHA256 **0ddff53cd07d4da38def00844dc17c0a6d49c633a6385ff47c81c3bb1bda5a62**. OgreMain_x64.lib already linked by project, SHA256 **97db9603acaa5ff19fa58f73bf7362e7298f99e96b36243563beba0334337928**; no-argument import/export symbols match **?renderOneFrame@Root@Ogre@@QEAA_NXZ**. Overload ending `_NM@Z` not selected. Generic KenshiLib::AddHook mechanism comes from Functions.h, SHA256 **0c8a1a51f4446b43fb43aebfdf9878dcb2c93ed593c79651945272f56c639c8b**; KenshiLib library SHA256 **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**.

REA supplied complete evidence this time **without Ghidra import**: inspect_native_exports examines9329 DLL exports, two named nonforwarded overloads. Evidence **ev_168b7ae2bbf871a451c524f994080184164bf758fa762a30795664b1e69309ae**, bundle `runtime/rea-root-exports-evidence.json`, SHA256 **4eeacad16803ff2abc5d352b0a762cf83f0a9dacfded2e48842f327f975f692d**. Original Ogre DLL SHA256 **7d3888d21398647519f10a89b1f300d8606f761ad159e6021a797b1b9b3df5f6**. Table alone does not prove execution; subsequent preflight/actual calls supply other evidence.

Before installation, `runtime/root-export-binding-preflight.json` checks same historical0.8.17 process by path/command/creation, loaded module, all export-directory bytes and 32 entry bytes against file. Headers differ only in ImageBase, observed equal to loaded base; field explicitly checked, every other byte required identical. Initial comparison rejected, diagnostic `runtime/root-header-comparison.json` retained; no additional difference hidden. Handles closed; preflight calls no game function.

Plugin uses **GetModuleHandleW/GetProcAddress on already loaded module**, then generic AddHook: no LoadLibrary, GetRealAddress applied to Ogre export, manual address or copied game code. Exposes observed UTF-8 path, symbol and hexadecimal address. Controller checks in new process that address equals loaded base + exact export RVA from identified file. Coordinates are evidence, not plugin constants.

`OriginalBoolInvocation` forwards pointer, calls once and returns original bool. Native tests: false/true, expected object/call count, missing exports/module/null, UTF-16 surrogate pair/invalid surrogate, address unchanged under numeric-grouping locale. Address formatted with classic locale. Helper does not invoke the Windows export used in resolution test; bool calls belong to our owned mock.

<a id="périmètre-et-contrôle-de-cadence"></a>

## Scope and cadence check

Existing profiler retains completed outermost calls, TLS creation and eight identities. Timer ends before recording lock. **No service inside original Root excluded**: work, waits, other mods and project hooks/commands reached inside remain included. `hook_source=loaded_ogre_export`, `leading_service_excluded=false`, module/symbol/address and exact scope state this. Spans may cross bucket bounds. Per-call CPU disabled; CPU fields null, no false zero or GPU estimate.

**777 Python tests pass before installation**, then **778 in 24,00 s** after consolidator integration; native v100 assertions successful, final build linked. No test/build during real acquisition. Real MCP smoke `runtime/root-frame-0818-smoke.json`:17 tools,60 completed calls, mean 6,329167 ms, compliant flags/counts/scope/binding, game paused. Cadence `runtime/root-frame-0818-cadence.json`:72 frames over 505,178 ms, tail10 mean **7,586990 ms**, before activation. Rejected0.8.14 not reinstalled.

<a id="campagne-heng-pausex5pause"></a>

## Heng pause/x5/pause campaign

`tools/research/live_root_frame.py` reloads KenshiProbe_test under pause protection/Edge lock, checks DLL/export/binding, prepares Heng 10 s x1 then waits for readiness. Three requested 12 s windows, each after 3 s warmup; requested 0,5 s observations and complete inventories limit 500. Copy reloaded paused, camera control released at trial end.

| Phase | Frames/calls | Mean Root ms/frame | Max call ms | Mean interval ms | Interval p99 ms |
|---|---:|---:|---:|---:|---:|
| Pause before | 2046/2046 | 6.092581 | 17.320100 | 6.094736 | 7.6277 |
| x5 | 1775/1775 | 7.064655 | 21.655600 | 7.067360 | 10.9783 |
| Pause after | 1850/1850 | 6.776492 | 21.410600 | 6.779735 | 9.8829 |

Equal aggregate call/frame counts do not prove a call in every unshown frame; individual series retains100 final rows. No skipped nesting, overflow or unknown Root identity in windows. Root joins **T37428/creation FILETIME 134376890854440932**, CPU identity at both endpoints, same game_thread/service_thread at bracketing heartbeats. **Whole-thread** CPU:9,15625/9,796875/10,140625 s; OS windows12,5/12,578/12,578 s. Not CPU of function alone.

Process CPU22,96875/30,625/21,953125 s, or **1,837500/2,434807/1,745359 logical processors**. Signed residuals+0,078125/+0,21875/0 s. None omitted before/active; final pause: **T25724 andT32984 not observed before**, hence omitted without invented consumption. Root thread verified in all three windows. Observed populations385..385/429..448/433..433; game_total_hours0/**+0,5762119293212891**/0. No assumed stationarity or deterministic NPC state.

Main requests n2046/57324 bytes,n1775/62323,n1850/57315, one attempt each. Compact re-encoded bytes, not exact TCP/MCP size. Native64K limit/adaptive budget unchanged. OS, scene and bucket windows distinct; nearby Root/callback means do not make spans identical or justify “outside Root” subtraction.

<a id="provenance-audit-et-rejeu"></a>

## Provenance, audit and replay

Complete capture **runtime\scenarios\root-frame-20261028T192845606379Z.json**, SHA256 **28779a39bfabb747fdd5d800b4793b63fd08a8e6932484ddfdb2a19b95c20d0d**; analysis `runtime/root-frame-0818-analysis.json`. Replay rechecks version/flags, three systems/five installations, exact module, no-argument overload, resolved address and CPU joins. Raw file unchanged.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_root_frame.py runtime\scenarios\root-frame-20261028T192845606379Z.json --expected-sha256 28779a39bfabb747fdd5d800b4793b63fd08a8e6932484ddfdb2a19b95c20d0d --output runtime\new-report-root.json
```

A **new manifest** `docs/research/performance-cohorts-root.json` adds Root to five earlier cohorts: **six cohorts/nineteen windows**, historical manifest unchanged. SHA256 **bbff14d3734e95c916f20b8fd74d7f51de600b99afd8cb030daaa427d34ebb2e**; report `runtime/performance-cohorts-root-v1.json`, SHA256 **c2d851ded75f276d9f028fc472aaed6fd37f5b234f964424cd0d7f7f83f70c00**, same-named Markdown table. Evidence `runtime/root-cohorts-replay-proof.json`: seeds0/8675309 byte-identical, older five-cohort diagnostic still byte-identical, canonical Root result equal to specialized replay. Same consolidation CLI with this manifest/SHA; no new acquisition.

Owned DLL **317952 bytes/SHA25624ff0bfc91e86f543c6add0a758cd93648d38408334c3536aec274f7f16ddec9**, PDB **10398720/SHA256938435e25b0a67a2ae9254447ff6e64bba93ace52b291aadbfeb7734fc310d89**, under `runtime/symbols/0.8.18`. Archive **crashes/20261028T192441333577Z-deployment-0818**, evidence `runtime/deploy-0818.json`, old 0.8.17 preserved. Only project processes stopped after fresh verification. Rollback prepared, unused; it does not reset sources.

Audit **runtime/root-frame-0818-final.json**: game **PID8412/Unix creation 1793215485.444091**, copy paused at 404,3333339691162 h, normal camera/control released/Edge=true, battle inactive. **702/702/738 files** source/copy/snapshot compliant, settings identical to beforehand, guards false, fresh watchdog without error, WPR inactive, no remaining controller. Helpers **6396/Unix creation1793215484.518235,24624/Unix creation 1793215484.4811432**: freshly recheck identities before stopping. No game file or decompiled code in Git; native outputs/Evidence/captures remain under ignored runtime.

<a id="question-suivante"></a>

## Next question

With this boundary observed, assess **existing per-call CPU mode** (`KENSHI_PROBE_FUNCTION_THREAD_CPU`), documenting GetThreadTimes cost/quantization before interpreting sums. A new cohort must declare mode and preserve CPUoff replay; not a deterministic A/B. CPU deltas also enclose measurement code/nested work: no exclusive engine attribution. No new MCP tool or simultaneous probe needed. Autonomous deadline22 h15 UTC/23 h15 Paris unchanged; no manual intervention expected.
