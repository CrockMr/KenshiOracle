<a id="trajet-du-thread-principal-vers-la-boucle-ogre"></a>

# Main-thread route into the Ogre loop

The four retained historical stacks pass through the same call from `KingOfRenderThread::startup`. Static diagnosis identifies **startup → thunk → Renderer::go → Ogre::Root::startRendering**. This path is tied to the retained observations, **not a CPU attribution**. No hook or plugin change: 0.8.17, 17 MCP tools, three profiled boundaries.

<a id="provenance-et-méthode-bornée"></a>

## Provenance and bounded method

Stacks come from historical PID 33936/Unix creation 1793179386.9010031, main thread 40448/creation FILETIME 134376529869010045. Their controller is `runtime/stacks/heng-20261028T101436907912Z/controller.json`, SHA256 `c51fb4edf498683df6de65a484f07d0dbac7197e521ddfc41c56989c1976cc06`. Verified SDK/stack analysis is `runtime/stacks-085-analysis.json`, SHA256 `ce3ac761e7bb761a2bf03fed1768fc45047c805f51ca3e15cdd46253121385f3`. These are not new stacks from the current process.

EXE/KenshiLib.dll/RVA-table sources are rechecked by fingerprint, without header comments or a global delta. Every stack retains its original return address: diagnosis examines only the call encoding immediately before it. DUMPBIN decoding starts at the observed region's entry; no whole-function boundary is invented from that region, neighboring fragments or a preceding symbol.

All four observations find return RVA 0x86c5ad and its direct call at 0x86c5a8. That reaches a relative thunk at 0xf97a, then entry 0x812890, an **exact** alias for SDK slot 5876 `Renderer::go()`. The supplied Renderer.h declares this method and its `Ogre::Root* root` field at offset 0x68. The short relay loads that field and transfers control through the static import **OgreMain_x64.dll / Root::startRendering**. Addresses are evidence only for the identified build, not a binding to copy into the plugin.

Successive evidence: `runtime/startup-callsite-analysis.json`, `runtime/startup-call-target-analysis.json`, then **`runtime/renderer-go-static-route.json`**, SHA256 **25bf2145d23bd608721be0a0d72137764b0a4e0506dbbd6504a5329bfc2984d9**. Each retains its parents, sources, bounded decoding commands and fingerprints. Scripts read local sources and observations; no target code is executed. The first resolution helper requested the parser's wrong import group and failed before writing a report; the EXE group was corrected and the final result retained. No game observation was repeated for that correction.

Import names are **static declarations**: this diagnosis does not authenticate Ogre's current IAT target in a process. Ogre/D3D11 frames in the stacks are consistent with this path, but four observations provide neither a weighted distribution nor proof of a GPU bottleneck. Whole-thread CPU remains that of separate OS windows; no duration of this loop is measured here.

<a id="ce-quapporte-rea-et-sa-limite-observée"></a>

## What REA provides, and its observed limitation

REA/Ghidra 12.1.4 was opened on EXE SHA256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. A targeted `startup` dossier request triggered import and default analysis; the observed log progressed through RTTI. The startup budget was already **900 s**. The MCP client interrupted the call at **450 s**, before that budget. This is a **client timeout**, not another 330 s provider_timeout or a decompilation result.

The error is retained in `runtime/rea-startup-dossier-result.json`. Export `runtime/rea-startup-evidence.json` contains **zero dossier records**: do not present analysis as complete or infer absent code. `close_binary` succeeded and the final session is **closed, cleanup_pending=false**. No identical relaunch and no security setting changed. Attempt evidence: `runtime/rea-startup-attempt.json`, SHA256 **cc3bbbb261527725500a003a981393969b77ad7de7e6d1b4f4d226a204a6f435**.

A future question genuinely requiring Ghidra first needs a host `mcp_servers.rea.tool_timeout_sec` above 900 s with request/cleanup margin, or the documented CLI transport that avoids this client limit. This does not guarantee analysis will finish within 900 s. No configuration change or user intervention is required for the static conclusions already obtained.

<a id="conséquences-pour-le-profilage"></a>

## Implications for profiling

The [King::mainloop candidate](king-mainloop-candidate.md) only updates TIME; it is rejected without instrumentation. `Renderer::go` and `startup` lead into a persistent loop: their calls do not provide a useful completed-frame boundary without further evidence. The measured [Renderer::update entry](renderer-measurements.md) therefore does not cover this whole loop by name alone. `Renderer::renderOneFrame` has no address in the SDK: do not invent a KenshiLib binding or replace that gap with a manual RVA.

Further improvements must start from existing measurements: reproducible diagnosis separating call wall time, OS thread CPU and point observations; prioritize remaining questions before modifying algorithms. Seven slow false-returning searches at distinct coordinates do not justify a failure cache; the observed BirdManager object does not yet identify its exclusive compute CPU. Completed heavy campaigns are not rerun without a new hypothesis.

After these static reads, separate audit `runtime/renderer-0817-diagnostic-final.json` finds the same PID 38472, a paused copy at 404,3333339691162 h, normal camera/released control, **702/702/738 protected files matching**, identical settings, watchdog without errors, 17 tools and seven SDK roles. No new build: the 721 tests still belong to unchanged production 0.8.17. Raw disassembly and game data remain only under Git-ignored runtime.
