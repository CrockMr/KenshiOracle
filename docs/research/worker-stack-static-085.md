<a id="worker-heng-085--rapprochement-statique-de-la-pile"></a>

# Heng worker 0.8.5: static stack association

The sampled path reaches a virtual method of **BirdManager**, a class identified by the binary's RTTI. It derives from **ThreadWannabe**, then **ThreadClass**. Its body includes a neighbor search using distance and orientation. This supports bird-simulation work at that instant; the observation neither measures its CPU share nor demonstrates an available optimization.

The [subsequent dynamic campaign](worker-object-validation.md), using unchanged plugin 0.8.7 and new process/thread identities, later verified the object's vptr in the same minidump as its context. The limitations specific to the historical static analysis below are retained.

<a id="périmètre-et-identité"></a>

## Scope and identity

Static analysis only, on October 28, 2026. Target: `Re_Kenshi/RE_Kenshi/Kenshi_x64.exe`, 36 713 984 bytes, SHA-256 `504b362cde850d56afb1cea6f5b7b0ee014d9dd7b47e188599d91c804502cd3e`. Preferred VA `0x140000000`; every number below is an RVA, independent of ASLR. This analysis opened no game process and added no hook, injection or game-file modification.

Earlier dynamic source, read offline: `runtime/stacks/heng-20261028T101436907912Z/controller.json`, sample 1, TID 10688, creation FILETIME `134376529988181936`, game PID 33936. Recorded stack: RIP `0x2602a6`, return `0x262cd0`, next return `0x25fe08`. The controller reports valid capture and offline analysis; all 7 622 SDK pointers are verified in this same dump. The first two bodies have no SDK alias. Return addresses are retained without a PC-1 adjustment.

<a id="chaîne-vérifiée-dans-le-fichier"></a>

## Chain verified in the file

1. The RIP's unwind data leads from `[0x260210,0x2602e8)` to `[0x2601ec,0x260210)`, then to primary region `[0x2601c0,0x2601ec)`. The caller's data leads from `[0x26287b,0x263664)` to `[0x26281b,0x26287b)`, then `[0x2627f0,0x26281b)`. These are fragments, without an invented whole-function boundary.
2. The call at `0x262ccb` reaches thunk `0x46254`, which jumps to `0x2601c0`. Its return address is exactly `0x262cd0`: static consistency with the stack.
3. Within `ThreadWannabe::threadProc`, the virtual call at slot `+0x10`, at `0x25fe04`, returns to `0x25fe08`. Arguments come from the float at `this+0x40` and boolean at `this+0x44`. The SDK declares `backThreadUpdate(float,bool)` at this same slot in `Include/kenshi/PhysicsActual.h:107`; it declares the base fields in `ThreadClass.h`.
4. Static vftable `0x16aad48` has thunk `0x23bd7` in slot `+0x10`, jumping to `0x2627f0`. Slots `+0x08` and `+0x18` respectively reach `0x25fca0` and `0x25fbe0`, actual SDK entries for `threadProc` and `forceLoopMT`. No historical RVA comment is used for this join.
5. The pointer before that vftable identifies Complete Object Locator `0x1816d48`: signature 1, offset 0, constructor displacement 0 and consistent self-RVA. Its TypeDescriptor `0x1c53d98` carries RTTI name **BirdManager**. Hierarchy `0x1816d78` contains BirdManager, ThreadWannabe, ThreadClass in order; all PMD displacements are `(0,-1,0)`.

The slot, RTTI and targets together support the interpretation **BirdManager override of ThreadWannabe::backThreadUpdate**. BirdManager is not declared in the local KenshiLib headers: this is not a new SDK API, and no BirdManager prototype or layout is added. The dynamic object's vptr was not read; class attribution for this sample remains a supported static association, without claiming to exclude all shared compiled code.

<a id="comportement-minimal-du-trajet"></a>

## Minimal behavior of the path

The body at `0x2601c0` walks a pointer array with a count at `+0xc0` and storage at `+0xc8`. It skips the requester itself and candidates whose state at `+0x38` is 0, 4 or 5. Named Ogre imports establish Vector3 subtraction, `Quaternion::zAxis`, `Vector3::dotProduct` and `Vector3::squaredDistance`. It selects a candidate with a strictly positive dot product and squared distance below the best threshold, initialized to the squared float parameter. The observed RIP is a floating-point comparison against that threshold.

The dot product uses the **candidate's** Z axis and candidate-minus-requester vector; this does not prove the candidate lies in front of the requester's orientation. After selection, the body follows `+0x30` links and returns null if the chain reaches the requester. Neighbor selection with cycle prevention is an algorithmic interpretation, not a recovered original function name. State meanings remain unknown.

Caller `0x2627f0` traverses group records spaced `0xf0` bytes apart and internal pointer lists. Imports attest vector/quaternion calculations, frustum planes and geometric operations. Direct calls through thunks reach exact SDK entries `UtilityT::getApproxTerrainHeightFromRenderer` (`0x9b1180`) and `UtilityT::random(float,float)` (`0x9b0db0`), declared in `Include/kenshi/util/UtilityT.h:107` and `:83`. This adds context without demonstrating that every path executed in this sample. Bird and BirdGroup types also occur in the file's RTTI names; their presence alone validates no complete layout.

<a id="preuves-et-limites"></a>

## Evidence and limitations

Git-ignored local outputs under `runtime/re-worker-085/`: `unwind-chains.json`, `call-resolution.json`, `static-vtable-refs.json`, `rtti-chain.json`, `static-validation.json`, three bounded dumpbin outputs and reproduction scripts. `manifest.json` records sizes and SHA-256, sources and tool version. `validate_static.py` rechecks the target hash, three direct branches, four vftable slots, the thread's virtual slot and hierarchy names/order. No game code or disassembly is copied into this document.

REA `inspect_with_objdump(file_headers)` returned `capability_unavailable`: objdump absent, without a new Evidence ID. No new Ghidra import was required; no native session was opened and no provider cleanup was required. Microsoft dumpbin fallback **10.00.30319.01**, bounded reads only. One initially blocked sandbox command was cleanly interrupted; commands outside the sandbox completed. No analysis helper remains owned by this subtask. Earlier REA Evidence for SDK exports remains `ev_140eb033dfeac2b7ffb9f8b9b438236f7b28d39172e5740dd25b977c7a08403d`; it is not presented as Evidence for the game's RTTI.

The first dumpbin range begins in the middle of an earlier instruction; helper analysis begins at its established entry `0x2601c0`. The caller range is bounded and does not establish a complete CFG. The global `.pdata` table is not fully sorted and has overlaps; selected fragments and instructions were examined directly, without treating the lookup index as general Windows validation. These data alone imply no CPU share, call frequency, active bird count, exclusive cost, gain or original helper name.

Format sources: [Microsoft: x64 unwind and chaining](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170); [Microsoft/Clang compiler tests for x64 RTTI ABI](https://github.com/microsoft/clang/blob/master/test/CodeGenCXX/microsoft-abi-rtti.cpp). These sources explain decoding; game-specific observations come only from the identified file above.
