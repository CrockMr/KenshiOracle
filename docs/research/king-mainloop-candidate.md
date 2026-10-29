<a id="kingofrenderthreadmainloop--candidate-écartée-sans-hook"></a>

# KingOfRenderThread::mainloop — candidate rejected without a hook

SDK method `KingOfRenderThread::mainloop(float)` **does not provide the desired work boundary**: verified entry simply updates `TIME` then immediately returns. No hook, engine call, restart or new plugin version added for this avenue. **0.8.17 remains installed**, with 17 MCP tools and three profiled boundaries.

<a id="pourquoi-cette-candidate"></a>

## Why this candidate

[Historical user stacks](user-stack-capture-measurements.md) pass through Ogre and `KingOfRenderThread::startup`. Latter is a long-lived ancestor; name establishes neither exclusive CPU cost nor per-frame frequency. After MainLoop/Renderer measurements, finite `mainloop(float)` declaration merited checking before instrumentation. Absent from all four retained stacks; this limited absence did not prove never called.

Supplied SDK declares `void KingOfRenderThread::mainloop(float time)` in KingOfRenderThread.h line 28. Export/import `?mainloop@KingOfRenderThread@@QEAAXM@Z` present in KenshiLib.lib. Header SHA256 **e93b1b2f0ecdc2f6e51c5e1dc3cd0be88de49589c22ad7d407b220af6ba0397d**, library **d407bf18c807cd3390643227ca4dc3ee4628fedc520870eee250201c04db311d**. Float `TIME` field declared at offset zero in same header. `runtime/king-loop-sdk-0818.json` is a candidate-prevalidation filename: **no0.8.18 produced**.

<a id="vérification-liée-au-build-et-au-processus"></a>

## Verification tied to build and process

Existing SDK map rebuilt with three exact sources/fingerprints: KenshiLib.dll, Steam_1.0.65.br and EXE SHA256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. Entry found through **symbol and slot**, without comment RVA or global delta. No function boundary invented from next symbol or missing unwind region.

In **PID38472/native creation FILETIME 134376841722811092**, path/command/creation checked, loaded stubs and **7622 slot values** verified before/after. Five bytes of King entry, not instrumented by project, read through query/read handle and exactly match file. DUMPBIN v100 decodes only bounded range: float argument written into object, then return. Handles closed, process unchanged, no object modified. First DUMPBIN rejected a range without hexadecimal prefix; corrected syntax retained in evidence, without new game capture.

Evidence **`runtime/king-candidate-live-entry.json`**, SHA256 **49b5aeea530eb3be18717145f6aa187cc95bad471bb8ad87a090f9d6c48136ca**. Retains identities, sources, before/after slot checks, compared read, commands, output fingerprints and cleanup. Bytes/disassembly remain **only under Git-ignored runtime**; no game code added to repository.

Second Renderer range read for context. **Its39 bytes are a fragment**, with outgoing branch: not a complete body or static evidence that all Renderer is short. Actual original-Renderer measurement remains [0.8.17 report](renderer-measurements.md). Only King entry compared to live code; Renderer already has project's service detour.

<a id="décision-et-limites"></a>

## Decision and limitations

Rejecting candidate avoids low-value instrumentation and identical campaign without a useful hypothesis. Verification measures **neither King call frequency nor CPU**, demonstrates no gain and does not resolve all main-thread cost. mainloop name does not guarantee it encompasses a frame.

REA consulted: server available, session initially closed/clean. Targeted native decoding requiring complete Ghidra import, this short diagnostic uses fingerprint-linked parser and local DUMPBIN. User authorizes REA as needed; **separate question** concerned `startup` dossier. Client interrupted request after 450 s, before Ghidra900 s budget; no dossier obtained, zero-record export and session closed/cleaned. [Independent route to Ogre](main-thread-loop-route.md) nevertheless resolved through bounded reads, without new hook.

SDK `Renderer::renderOneFrame` declaration marked without address; do not invent KenshiLib binding to obtain a probe. Next avenues must respect actually provided APIs and three-system limit. Game remains paused during static diagnostic, protected saves and 22 h15 UTC deadline unchanged.
