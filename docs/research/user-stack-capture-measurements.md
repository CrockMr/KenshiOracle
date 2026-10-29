<a id="piles-utilisateur-sans-administrateur--plugin085"></a>

# User-mode stacks without administrator privileges — plugin 0.8.5

Stacks from the three targeted Kenshi threads were recorded without administrator privileges, an ETW session or an additional hook. Four filtered minidumps were then unwound offline, after restoring the paused copy. The remaining worker's active path statically reaches a BirdManager virtual method; its dynamic object still needed confirmation.

That uncertainty was subsequently resolved in a [separate object-verification campaign](worker-object-validation.md), using unchanged 0.8.7. This report's numbers and identities remain those of the 0.8.5 captures; exclusive CPU time for a BirdManager function remains unknown.

The 0.8.5 DLL and its three probes are unchanged. These captures establish neither a performance improvement nor a statistical allocation of CPU time by function.

<a id="méthode-effectivement-validée"></a>

## Validated acquisition method

thread_minidump.py calls MiniDumpWriteDump from an external helper and filters threads through IncludeThreadCallback. Every selection must retain the exact PID, game path, TID and creation FILETIME. The file includes contexts and stacks for the three threads, creation information and a verified SDK-metadata range. Module code/data segments and per-thread instruction windows are excluded; no full memory dump is taken. The .dmp files remain local under runtime, ignored by Git.

The [Microsoft MiniDumpWriteDump documentation](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/nf-minidumpapiset-minidumpwritedump) recommends an external call; [IncludeThreadCallback selection](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ne-minidumpapiset-minidump_callback_type) limits the included threads. The library may temporarily interrupt them for capture, so this observation is neither passive nor cost-free.

The tools/research/dump_stacks.cpp helper compiles as **v100 x64** and uses DbgEng only on recorded files: OpenDumpFile/GetStackTrace, never AttachProcess or launching an inferior process. Symbol paths are local and network-search variables are ignored. Unwinding and name formatting happen after the copy returns to pause, outside the observed interval.

<a id="la-carte-sdk-est-liée-au-build-exact"></a>

## The SDK map is bound to the exact build

Not every header RVA comment matches the installed binary. For example, charsUpdateUT has 0x7857d0 in its comment, whereas this build's table gives 0x785ea0. No global delta is applied.

The [official KenshiLib contract](https://github.com/BFrizzleFoShizzle/KenshiLib/blob/RE_Kenshi_mods/Source/core/Functions.cpp) binds a stub to a table index, then to the EXE base. Steam_1.0.65.br is an int32 array here, despite its extension. sdk_address_map.py checks AMD64 PEs, exports, FF25 stubs, the table and section bounds. It retains all aliases.

Exact sources:

| File | SHA-256 |
|---|---|
| Re_Kenshi/KenshiLib.dll |5b6240622d06801dc39896e385efb834b8e1fe2fcdf86067d071ae7a04f6c83b|
| RE_Kenshi/RVAs/Steam_1.0.65.br |573c395997ed8d93dd837e27f89a440323089edd1ba93f68291631b448f9cbd0|
| RE_Kenshi/Kenshi_x64.exe |504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e|

The 7622 verified stubs correspond to 7630 entries, of which the final eight point to non-executable data and are not used to name functions. Exports name 7618 slots, retaining aliases. loaded_sdk_map.py also checks loaded headers, stub bytes and the 7622 actual pointers. Each x1 minidump then contains that table: all 7622 values read from **that same file** match ExeBase+RVA. The evidence is not merely an assumption about the installed file.

The game's 77508 .pdata regions contain two ordering regressions and 413 overlaps. The parser retains their original order and indices; a separate lookup index does not repair them. An overlap remains ambiguous; a name is added only when the SDK entry exactly equals the start of the unique region. Chained fragments and functions without a region remain explicit. The [Microsoft x64 documentation](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64) describes these unwind regions; they are not automatically entire source functions. No preceding symbol is used to invent an end boundary.

<a id="captures-à-heng-x1"></a>

## Heng x1 captures

Controller: **runtime/stacks/heng-20261028T101436907912Z/controller.json**, completed=true, admin=false, SHA-256 **c51fb4edf498683df6de65a484f07d0dbac7197e521ddfc41c56989c1976cc06**. The four dumps contain 149869/152789/152693/147941 bytes. Each file retains its three exact creation times, verified SDK table and fingerprint. Unwinding HRESULTs are 0, without reaching the 64-frame limit.

The helper's captures take 0,234250/0,226660/0,217172/0,232056 s respectively, totaling 0,910138 s. These durations include more than any thread suspension: they do not measure how long the game was stopped and are not subtracted to claim corrected throughput.

The enclosing OS interval is 7,438 s, clock +0,063837 h, with speed 1 and camera checked at both boundaries of each capture. Process CPU is 2,235144 average logical processors, signed residual −0,03125 s and no boundary omissions. This context includes capture interruptions and observation requests; no causal contrast with the preceding campaign is calculated.

| Thread and creation FILETIME | Stack observation |
|---|---|
|40448 /134376529869010045|Main/render thread; stacks pass through Ogre and KingOfRenderThread::startup. startup is a persistent ancestor, not evidence of a restart or exclusive cost.|
|34252 /134376529988183642|SDK role world_ai_non_render. One stack contains MedicalSystem::periodicUpdate, another ZoneManager::updateRendertimeThread. Other captures wait in ThreadWannabe::threadProc. The role name therefore does not isolate all AI work.|
|10688 /134376529988181936|One capture is active at RVA 0x2602a6 then 0x262cd0, before ThreadWannabe::threadProc. The other three wait in that common loop. There is no exact SDK alias; the vftable and RTTI statically connect this path to BirdManager.|

The two workers each accumulate 2,03125 s of CPU during this interval; that does not attribute their CPU time to functions visible in a few captures. Stack counts are never converted into CPU percentages.

Worker 10688's active region is 0x260210..0x2602e8; its unwind chain leads back to 0x2601c0. The caller's chain leads back to 0x2627f0. These are metadata fragments, without an assumed whole-function boundary. The original return address is retained without a −1 adjustment.

The [complementary static analysis](worker-stack-static-085.md) checks calls and returns, the SDK slot `ThreadWannabe::backThreadUpdate(float,bool)`, the vftable and the BirdManager → ThreadWannabe → ThreadClass RTTI hierarchy. The helper performs geometric neighbor selection, probably with cycle prevention. The dynamic object's vptr was not read and shared compiled code is not excluded. This association neither names every function, supplies a BirdManager SDK API nor attributes all thread CPU to the bird system. Confirm the object, then quantify its cost before proposing an optimization.

<a id="reproduction-hors-jeu-et-contrôles"></a>

## Offline reproduction and checks

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_thread_dumps.py runtime\stacks\heng-20261028T101436907912Z\controller.json --output runtime\stacks-085-analysis.json
```

This command rechecks fingerprints, threads, the SDK table in each dump, scene bounds and SDK/CPU joins. It neither attaches to a process nor unwinds stacks again; DbgEng observations are retained in the results. Installation sources with their exact fingerprints are required to recompute the map. No game binary is distributed in the repository.

**366 pytest tests pass in 5,08 s**; 40 new SDK-parser tests cover PE/stubs/imports/.pdata/aliases/overlaps. Minidump tests cover incomplete data and legitimate unused directory slots. The x64 ABI was also checked by v100 compilation: ADDRESS64=16, KDHELP64=112, STACKFRAME64=264, CONTEXT=1232, offsets Rsp 152/Rip 248.

Two earlier approaches remain documented:

- PSS VA cloning works on our helper but fails on Kenshi with 1450, “ressources insuffisantes” (insufficient resources); the exact cause is unknown, not an administrator-permission rejection. No clone was retained and the same attempt was not repeated unchanged. See stack-pilot-20261028T094933567322Z.json.
- Lightweight PSS without cloning succeeds but provides only RIPs, not stacks. The first normal paused minidump was acquired correctly; its controller rejected repeated unused 0/0/0 directory slots. The corrected parser accepts them, with a test. The original completed=false is retained and its offline revalidation required no new capture: minidump-pilot-20261028T100423984944Z.validation.json.

User-mode capture avoids administrator intervention for this stack question. It validates neither a new ETW capture nor kernel-stack coverage. The copy was reloaded paused, the camera released, and the 702/702/738 source/copy/snapshot files and settings.cfg match. This campaign's older restoration still set speed through several commands and briefly unpaused. That limitation was later fixed by the [restoration validated on 0.8.7](../pause-preserving-speed-validation.md); the historical measurements above remain those of 0.8.5. No complete NPC-state identity is claimed.

The independent final check **runtime/stacks-085-final.json** confirms unchanged PID 33936/creation time, pause/normal mode, Edge=true and released camera control, 17 tools/seven SDK roles, three probes, a fresh watchdog without errors and WPR inactive. The 702/702/738 files match and settings.cfg bytes are identical to the predeployment 0.8.5 reference. Helpers 13460/14864 remain bounded to 1793225700; no capture controller remains active. Fingerprints for the v100 reader, DbgEng/DbgHelp and the sources observed after capture are in runtime/stacks-085-toolchain.json; that timestamp is not presented as an earlier attestation.

The static map's runtime_binding_verified field remains false by construction. Annotation field loaded_table_in_same_dump_verified and sdk_binding_from_dump checks supply evidence specific to each file, separately. This distinction prevents reusing process validation as a universal property of the map.
