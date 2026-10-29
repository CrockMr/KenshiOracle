<a id="identité-de-thread-sans-cpu-par-appel--083"></a>

# Thread identity without per-call CPU — 0.8.3

Joining AI calls to Windows CPU counters now works when both per-call CPU reads are disabled. Real Heng validation retains 30 450 calls attributed by TID/creation time. It does not measure a game performance gain.

<a id="changement"></a>

## Change

ThreadIdentity.h contains zero-initialized POD state held in TLS by each native thread. Creation FILETIME is read only once, on the first outer call; no game handle or pointer is retained. A failure or zero creation time remains unknown for that lifetime. New threads have new TLS even when Windows reuses a TID. Buckets retain the TID/creation pair; an unknown identity is serialized as null and is never joined by TID alone.

KENSHI_PROBE_AI_THREAD_CPU=1 retains both CPU reads per call. With 0 or omission, cpu_user_total_ms/cpu_kernel_total_ms are null, cpu_available_calls=0, and calls are unavailable for per-call CPU. Identity and wall time continue to be collected. ping.ai_thread_identity_mode and systems.ai_profiled_function.thread_identity_mode equal tls_creation_once; ping.ai_thread_identity_independent_of_cpu is true. The probe remains AI::update4Frame, alongside charsUpdate and findPath; 17 MCP tools, three probes, and v100 x64.

Omitting lock_edge from the native set_camera_free command now uses optionalFlag, as the MCP path does. Omission and rejection of a string were also verified directly through the native protocol.

<a id="preuve-réelle"></a>

## Real evidence

Raw: runtime/scenarios/ai-identity-20261028T085329926232Z.json. SHA-256 **d608b29f4288317b611640def64461b1bcd7fb84de47a3720c98bf6dbc60ef21**. completed=true, MCP stdio transport, PID33512/creation 1793177385.19762.

- Final window: frames 18396..18995, 600 frames, 30 450 outer calls, no nested entries or thread truncation.
- Inclusive wall time: 17,974197 ms accumulated, 0,029957 ms/frame; maximum single call0,045300 ms.
- TID37396/creation 134376509972635536, exact identity in buckets, both SDK world_ai_non_render reads, and OS counters. Call CPU null, no call declared CPU-measured.
- Enclosing OS window 10,546 s: process 24,265625 s CPU, whole thread 3,125 s CPU, or 0,296321 logical processor with that denominator. The thread recording has its own duration10,532 s; its normalized values are therefore not numerically identical. Signed CPU residual+0,0625 s, no boundary omissions.
- Clock between scenes: +0,0965366 h over 10,533826 s, x1 observed at every read, camera stable under lock.

These bounds differ from the final 600-frame window. No exclusive coverage ratio or cost of the function alone is calculated from whole-thread CPU. Instrumented timings and outside load are not calibrated; these numbers demonstrate no gain over 0.8.1/0.8.2. Worker 39360/creation 134376509972634106 also represents2,90625 s CPU in this interval, but this probe does not identify its function. Thread 17004 consumes more; no exclusive role is inferred from that ranking alone.

The first scenario, runtime/scenarios/ai-identity-20261028T085158063881Z.json, is retained with completed=false: its statistics request arrived after the scene boundary, with last_frame8567 versus scene_after8558. Restoration and files were compliant. The controller now collects statistics before the scene boundary and before closing the OS recording; the second test validates this correction. No threshold was relaxed.

<a id="validation-et-état-laissé"></a>

## Validation and final state

**291 pytest tests pass in 4,44 s**, including disabled CPU with known/unknown identity and rejection of an unknown identity mode. The native tests/test-thread-identity-v100.cmd test passes with eight Windows threads over two generations, cache read only once, isolated TLS states, and explicitly unknown failures. v100 x64 compilation/linking succeeded. The first sandbox compilation failed with C1902; authorized compilation outside the sandbox succeeded. A pytest process blocked in the sandbox was stopped after strict verification of process 9804's path/command/creation time/directory; its wrapper had already exited. The suite outside the sandbox then completed normally.

Archive crashes/20261028T084930198333Z-deployment-083: previous DLL 0.8.2, log, config, and settings. WPR inactive and identities verified before stopping only the project's processes. Separate0.8.2 and 0.8.3 symbols retained under runtime/symbols with fingerprints. No game or SDK file added to Git.

Initial autoload had made the copy available unpaused; the first precheck rejected it before mutation. runtime/identity-083-startup.json retains this observation and the immediate explicit pause that followed. Automatic pause before readiness still applies to owned snapshots, not KenshiProbe_test: **fix on the next native change**, while retaining this automatic-recovery limitation. Do not assume autoload leaves the copy paused.

runtime/identity-083-final.json verifies PID33512, copy in pause/normal mode, camera control released and Edge=true, 702/702/738 source/copy/snapshot files compliant, settings identical to the predeployment state, guards false, 17 tools, seven SDK roles, watchdog without error, and WPR inactive. Helpers at the last check28140/33880: recheck their identities before stopping them. Deadline/activation1793225700 unchanged.

The Heng ETW capture remains deferred, without an additional manual request or a new UAC dialog. The next possible entry point for the remaining worker is GameWorld::charsUpdateUT(), declared by the SDK, with its actual GameWorld* prototype without float, replacing only the AI probe. Never add a fourth probe or assume a function for RenderTimeBackthread.
