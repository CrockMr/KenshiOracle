<a id="objet-birdmanager-vérifié--plugin-087-inchangé"></a>

# BirdManager object verified — plugin0.8.7 unchanged

Thread 18796 in this campaign does carry a **BirdManager** object: stack context, object's SDK prefix, thread ID, vtable and RTTI name agree within the same minidump. Completes [earlier static matching](worker-stack-static-085.md), which lacked dynamic vptr.

CPU capture preceding snapshot attributes **2,828125 s CPU over 8,110 s**, about **0,349 logical processor**, to whole thread. Does not measure exclusive cost of a BirdManager function, separate computation/synchronization or demonstrate performance gain.

<a id="source-et-conditions"></a>

## Source and conditions

Controller `runtime/worker-objects/20261028T111210121084Z/controller.json`, completed=true, admin=false, SHA-256 **546d1bb32add420fe5b3dbc4efcfb5e725834c64df27b4838c70103adfd7d33c**. Game PID **28920**, native creation FILETIME **134376583442008762**; EXE SHA-256 **504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e**. Addresses/identities below concern this lifetime only.

KenshiProbe_test copy reloaded with camera lock, prepared at Heng, then advanced x1 after warmup. CPU measured before any DbgEng capture/analysis. Four threads with largest CPU deltas then selected by TID **and creation FILETIME**. Game paused before both minidumps/unwinding. No pytest or compilation during CPU window.

Installed plugin remains0.8.7, DLL SHA **eb6760d01e382efaddb0b3274349f6a30d506ee80a2fbc79e10a7f8c778abdba**: still17 MCP tools/three system probes. No new hook or reconstructed BirdManager API call. RTTI-metadata addresses are observations of identified binary, not a new SDK interface.

<a id="chaîne-de-preuve"></a>

## Evidence chain

1. New `tools/research/dump_contexts.cpp` reader, compiled v100 x64, uses [DbgEng GetContextStackTrace](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dbgeng/nf-dbgeng-idebugcontrol4-getcontextstacktrace) only on recorded files. Retains per-frame contexts, omits volatile registers whose restoration this API does not guarantee.
2. Static evidence `runtime/re-worker-087-static/threadproc-this-proof.json` verifies **RBP contains this** at exact ThreadWannabe::threadProc frame whose PC is RVA0x25fd3a or 0x25fe08. RCX→RBP copy dominates these paths; RBP not reassigned before epilogue. Not saved stack RBP, which belongs to caller. Prefix offsets from ThreadClass.h: vptr+0, handle+8,TID+0x10,running+0x14. No derived-class layout invented.
3. Discovery dump contains four thread contexts and verified SDK table. Unwound frame for thread **18796 / creation 134376583564582384** gives candidate this **0xc229fb70**. External read limited to 24 bytes verifies prefix TID, identity stability and OS lifetimes. Stored object handle remains numeric value alone, never independent lifetime evidence.
4. Second dump contains contexts, SDK table, two candidate 24-byte prefixes and three known RTTI/vtable ranges. In **this confirmation file**, same frame gives same RBP, prefix TID 18796 and vptr **0x7ff6e999ad48**, or EXEBase+0x16aad48. Table preamble, four slots, Complete Object Locator and `.?AVBirdManager@@` name match source-file metadata, relocation verified. All7622 SDK pointers also match this EXE base in both dumps.
5. Other ThreadWannabe object carries TID **38140 / creation 134376583564583798**, at 0x5cfe1e0 with different vptr. SDK role world_ai_non_render joined separately. A ThreadWannabe frame is therefore not assumed BirdManager.

Discovery dump **155884 bytes**, confirmation **157118 bytes**. Helper capture times0,299612 and 0,237697 s; not game-suspension duration measurements. Second adds only six explicit ranges, **61122 bytes**: SDK table60976,vtable40,locator24,type descriptor34,two24-byte prefixes. No full dump or heap scan.

Final reader also reunwound historical active0.8.5 minidump: **24/7/9 PC/SP frames** remain identical to original reader. Evidence `runtime/contexts-087-reader-validation.json`, reader SHA **16682a8cbc0fc4574ed4f329b75b47db9ad13550d008901c160a2601aa83db86**. No live process attached by DbgEng; no Ghidra provider opened.

Both new files also reunwound offline with reader fingerprint matching acquisition: PC/SP/RBP for **22/9/8/8 discovery frames** and **26/9/8/8 confirmation frames** identical to retained observations. Separate evidence `runtime/worker-objects/20261028T111210121084Z/offline-replay-validation.json`.

<a id="cpu-et-limites-dattribution"></a>

## CPU and attribution limits

| Thread / creation FILETIME | Whole CPU | Mean logical processors over 8,110 s |
|---|---:|---:|
| 19312 /134376583442008777 |6,187500 s|0,762947|
| Non-render SDK role 38140 /134376583564583798 |2,921875 s|0,360281|
| BirdManager object18796 /134376583564582384 |2,828125 s|0,348721|
| 34312 /134376583466414538 |0,890625 s|0,109818|

Process totals **18,9375 s CPU over 8,125 s**, or 2,330769 logical processors. Process/thread counter endpoints sequential: durations differ, signed residual **−0,25 s**, retained unclamped. No identity omitted at endpoints. Scene measurements enclose8,117921 s and+0,0743103 simulated h, population 418 to 450; streaming/population evolve during window.

Both captures **follow CPU window and are paused**. They attest the object linked to this thread at that instant, without assigning every preceding CPU quantum to bird code. Some thread work may be waits, synchronization or other calls. No CPU percentage inferred from stack counts; no causal contrast with another version/town. Other applications' load neither fixed nor quantified.

<a id="reproduction-hors-jeu-et-restitution"></a>

## Offline reproduction and restoration

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_worker_object.py runtime\worker-objects\20261028T111210121084Z\controller.json --expected-sha256 546d1bb32add420fe5b3dbc4efcfb5e725834c64df27b4838c70103adfd7d33c --output runtime\worker-object-087-analysis-recheck.json
```

Analyzer checks files/joins offline; retained DbgEng contexts are observations, not registers it reunwinds itself. Exact-fingerprint source binaries required for static matching. Minidumps/raw outputs stay under Git-ignored runtime; no game binary or disassembly in this report.

Choose a new output path on every recalculation: analyzer rejects overwrite. Final revalidation `runtime/worker-object-087-analysis-v2.json`, verified=true. Also checks initial dump-context bytes, PID/second-resolution creation in MiscInfo, x1/pause scene chronology and recomputed progression. Precise process FILETIME remains external evidence from recorded handles/bindings, not presented as dump field. QPC/monotonic domains not assumed identical. Targeted tests include corrupting SDK-table bytes,TID,vftable,locator,RTTI name; rejected even after updating declared SHA.

**442 tests pass in 21,13 s** in final suite. New cases also check metadata ranges, reused/contradictory identities, inconsistent scenes and rejection of+0,5 s process-creation discrepancy. Separate reader compiled v100 x64; no plugin recompilation/installation needed for campaign.

After capture, paused simulation time stayed exactly **404,4983215332031 h** during object verification. Copy then reloaded at **404,3333339691162 h**, identical to initial reference, camera released. `runtime/worker-object-087-final.json` confirms pause, normal camera, Edge=true/ownership false,17 tools/seven SDK roles/three probes, fresh watchdog without error,WPR inactive. **702/702/738 files** source/copy/snapshot compliant, settings.cfg identical to pre-deployment, no campaign controller remains active.
