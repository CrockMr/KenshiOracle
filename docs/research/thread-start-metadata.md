<a id="métadonnées-de-démarrage-des-threads-windows"></a>

# Windows thread startup metadata

Windows capture limited to thread metadata works on the paused game with **PROCESS_QUERY_INFORMATION**, without administrator session. It finds **126 threads** and startup procedures. Priority workers **37324 and 39984** share an address in **MSVCR100.dll + 0x21dbc**, also used by previously observed navigation worker 37196. Shared address does not distinguish functions. No CPU stack or exclusive system attribution obtained.

Plugin **0.7.5, v100 x64, 17 tools and three hooks unchanged**. New code is a Windows Python reader, separate from plugin. No save recording, deployment, speed or game-setting change at this step.

<a id="méthode-vérifiée"></a>

## Verified method

Declarations read from installed Windows SDK **10.0.26100.0**, ProcessSnapshot.h and TlHelp32.h. x64 helper notably checks 120-byte PSS_THREAD_ENTRY, Win32StartAddress offset 88 and 1080-byte MODULEENTRY32W. Uses only **PSS_CAPTURE_THREADS=0x80**, context flags zero; no clone, context, memory space or page content requested. Microsoft distinguishes options in [PSS_CAPTURE_FLAGS](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags).

Capture walked with [PssWalkSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalksnapshot). Every entry's PID checked; nonnull context would be rejected without dereferencing. Reserved fields unused. Captures bounded to 4096 threads/4096 modules. Module inventory uses read-only Toolhelp; addresses matched to half-open ranges without code reads or proximity attribution. See [CreateToolhelp32Snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot) and [MODULEENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-moduleentry32w).

Marker, local snapshot and query handle released in finally, return codes retained. PSS descriptor belongs to helper: release uses **GetCurrentProcess** even for a remote target, as specified by [PssFreeSnapshot](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot). No SuspendThread or process write. This does not claim to describe every internal Windows synchronization mechanism.

<a id="validation-progressive"></a>

## Progressive validation

1. `runtime/thread-metadata-self.json`: local helper with known thread. Creation exactly matches GetThreadTimes; handle count before/after **198/198**. Capture/releases successful.
2. `runtime/thread-metadata-remote-helper.json`: second project helper, path/command/parentage/creation verified. Known thread found; releases successful. Identity reread before normal-stop request over stdin, exit **0**, thirty-second safety timeout. No external process stopped.
3. `runtime/thread-metadata-game.json`: single read of identified paused game, capture/releases successful. Session-token read confirms **administrator=false**. Clock/camera unchanged before/after.

Marker/snapshot release returns **0**, process-handle close **true**, in all three evidence files. This metadata collection neither starts ETW nor changes the policy that rejected its pilot.

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
# Require the recorded local evidence, then validate a remote helper.
& ./.venv/Scripts/python.exe tools/research/live_thread_metadata.py
# Refuse without successful remote validation; require the restored, paused copy.
& ./.venv/Scripts/python.exe tools/research/live_thread_metadata.py --game
& ./.venv/Scripts/python.exe tools/research/analyze_thread_metadata.py runtime/thread-metadata-game.json runtime/scenarios/pause-cpu-20261028T041739Z.json
```

Evidence paths local and explicit. First local test performed before these commands and full responses retained; wrappers refuse to assume success if file missing/invalid.

<a id="jointure-avec-le-cpu-déjà-mesuré"></a>

## Join to previously measured CPU

Metadata capture SHA-256 **f48063ab218367c504eb93d9f37f510f5a2dfa1e448c48b6e4f0b7cabb69b868**. CPU source pause-cpu-20261028T041739Z.json, SHA-256 **200b5b7da382777c5b50cfc8c175c4df079300c5ee0e041baf9ab85a32a5ad40**. Report `runtime/thread-metadata-analysis.json` retains both fingerprints.

Join requires consistent PID, executable and process creation, then **exactly identical TID and creation FILETIME** for each thread. Of 120 CPU-interval threads, 119 found in later metadata. TID 34868 remains unmatched; measured CPU delta zero in all three intervals, without implying permanently no execution. Other later entries receive no invented retrospective CPU.

Whole CPU of matched threads, **grouped by startup-procedure module**:

| Startup module | Joined threads | Pause before | x1 | Pause after |
| --- | ---: | ---: | ---: | ---: |
| Kenshi_x64.exe | 5 | 0,825062 | 0,842938 | 0,822489 |
| OgreMain_x64.dll | 16 | 0,750960 | 0,662089 | 0,717670 |
| nvwgf2umx.dll | 55 | 0,179527 | 0,154794 | 0,175209 |
| MSVCR100.dll | 25 | 0,076395 | 0,676649 | 0,072685 |

Numbers are mean logical processors over older CPU intervals. **This does not measure CPU executed inside each module.** Startup routine may call other libraries or be a shared runtime entry. Startup module is not active stack, as distinguished by [Win32StartAddress in PSS_THREAD_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_thread_entry).

Both workers increasing at x1 therefore remain unattributed despite common MSVCR100 origin. TID 32072 has a procedure in nvwgf2umx.dll; this locates its origin without establishing all work. Groups/residuals not renormalized. Temporal-contrast/population limitations remain those in pause-cpu-measurements.md.

<a id="état-et-suite"></a>

## State and continuation

**193 Python tests pass in 4,07 s.** They cover module boundaries, ambiguous ranges, reused thread identities, contradictory process identity and signed residuals. Real local/remote captures separately validate ABI/releases.

Game remains PID 19892 with same path/creation, ready/paused at same game time; normal view, Edge scrolling=true, no active tracked combat. Fresh evidence `runtime/thread-metadata-final.json`. No test helper remains active. Tools write no game file; last full **702/702 source/copy files and 738 snapshot files** check remains `runtime/scenarios/pause-cpu-075-final.json`, fingerprint-linked, without unnecessary identical revalidation. Supervision deadline remains **28 October 22 h15 UTC**.

Administrator ETW pilot still pending; metadata does not replace it. Both MSVCR100 workers require stacks or other function evidence before choosing optimization. Any startup-routine symbol search must distinguish exact address, wrapper and active code; no disassembly or new interception performed here.
