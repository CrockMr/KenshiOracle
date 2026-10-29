<a id="etw-et-restauration-de-caméra--082"></a>

# ETW and camera restoration — 0.8.2

**The administrator WPR pilot is valid: 30 932 992-byte trace, zero lost events and zero lost buffers.** The first Heng capture was rejected before any mutation or trace because the camera had drifted between trials. Protected loading in 0.8.2 fixes that transition; the targeted x1 capture still needs rerunning in the administrator context.

<a id="pilote-réellement-enregistré"></a>

## Pilot actually recorded

- Folder runtime/etw/KenshiProbePilot_fd5e0c834b34; controller.json and validation.json verified.
- ETL SHA-256 **3e875f46bf7ec889b6b1a39e50addde5d1e3f0cc003ab2d6de9582b6e7b64511**, WPR profile identical to the source file.
- PID **37552**, path and creation match the 0.8.1 evidence; paused before/after, WPR start/stop 0 and cleanup_required=false.
- ETL interval **07:00:41.3974028..07:00:44.4739986 UTC**, or 3,0765958 real trace seconds for two requested seconds, with additional WPR boundaries.
- xperf -a tracestats -timespan actual: **0 lost events, 0 lost buffers**. Global profile: 13 890 Sampled Profile events, including 10 731 with an associated stack in the report; this does not prove every stack is complete.
- Stack report filtered to the game: **4 510 observations**. Function names are unresolved in this initial export, produced without enabling symbols. ntdll roots must not be confused with CPU-consuming leaves.

The most observed module leaves include ntkrnlmp.exe (1 365), OgreMain_x64.dll (1 072), nvwgf2um.dll (497), D3D11.dll (282) and RenderSystem_Direct3D11_x64.dll (242). These counts concern available stack observations from this **paused** pilot; they establish no exclusive cost for all physics/AI/rendering, gain comparison or attribution of the unknown active worker.

The xperf files trace-stats.txt, processes.txt, trace-span.txt and kenshi-stacks.txt remain local. The last is HTML despite its suffix. System metadata remains in runtime/etw, ignored by Git; public project reports do not enumerate other processes.

<a id="capture-heng-et-incident-de-caméra"></a>

## Heng capture and camera incident

The manual launch runtime/etw/KenshiProbeHeng_8e95c2f721f3 stopped on Camera moved during measurement during the initial precondition: **no world mutation, no WPR start**, source/copy/snapshot/preferences conforming. This was not a privilege rejection.

SDK readings gave mPos=[1,1], mPosAbs=[1280,720], Edge scrolling=true; the camera could move even while paused. These alone do not determine the pointer's physical position. The view drifted from its historical reference toward about [48352,930,-14493]. A recentering click through Computer Use and ordinary restoration did not correct the result read after loading. The RE_Kenshi General panel was visible when the window of this PID was captured; it was left open. No terminal or UAC dialog was controlled through the UI.

The existing lock was released at the beginning of load_save; loading frames could therefore read the edge again. **0.8.2 adds load_save(name,lock_edge=true)** for KenshiProbe_test or a snapshot actually owned by the plugin. The original preference is retained and scrolling disabled before the load request, throughout loading. **set_camera_free(...,release_edge=true)** explicitly restores the captured value without requiring another load; simultaneous lock and release are rejected. Old defaults retain their behavior; non-disposable saves cannot request this lock. The implementation reuses SDK OptionsHolder, without a new offset or hook.

The DLL remains **v100 x64, 17 tools and three probes**, AI::update4Frame target unchanged. This is a test-control fix, without engine optimization. The TLS cache separating identity from per-call CPU remains an improvement to make.

<a id="validation-effective"></a>

## Effective validation

**289 pytest tests pass in 4,51 s**, covering named WPR sessions, rejection of a foreign session, emergency cancellation after failure, ambiguous startup and protected camera parameters. v100 x64 compilation/linking succeeded.

runtime/camera-082-smoke.json establishes a real protected load, canonical view **[50759.15625,997.840759,-14012.985352]**, two stable reads two seconds apart, identical pause and clock, then release restoring Edge scrolling=true and ownership=false. The camera can respond to edge input again after restoring the preference; stability must be checked during the measurement window, not assumed indefinitely after release.

Deployment archive **crashes/20261028T073800679070Z-deployment-082**, old DLL 0.8.1/config/preferences/log. Global WPR idle verified, game 37552 and watchdogs 1484/2012 reread before stopping; only project processes touched. Current game **31368**, watchdog wrapper **17928**/child **1060** during runtime/camera-082-final.json; identities must be reread before action. Copy paused, normal mode, temporary control released, watchdog fresh without error, deadline/activation **1793225700** unchanged. **702/702/738 files** of source/copy/old snapshot conform.

The settings.cfg preferences match the prior state, but **file bytes are not identical**: autosaveindex and continue advanced from 0/autosave0 to 1/autosave1, consistent with an engine autosave. Raw differences remain in the final check; no other field is excluded from comparison, no autosave is deleted and the file was not overwritten to hide this difference. Do not claim byte-identical preferences and metadata for this check.

<a id="scénario-prêt-et-action-restante"></a>

## Ready scenario and remaining action

Script tools/research/live_etw_heng.py is standalone: paths resolve from its location, with no PYTHONPATH or Set-Location required. It checks for no foreign WPR session, PID/path/creation and protected saves, loads the copy with locking to define a **fresh canonical reference**, prepares Heng, stabilizes x1, captures ten seconds, verifies camera/speed/PID, stops only its own instance, rereads roles and restores the copy under lock, then releases it. The OS window includes WPR startup/shutdown and requests; it is not identical to ETL boundaries. Logs retain errors and cleanup_required, never assumed success.

An automatic launch through Start-Process -VerbRunAs returned **« L'opération a été annulée par l'utilisateur »**. No capture process started; runtime/etw-admin-launch.json has launched=false. The PowerShell message « launched » with an empty PID came from a non-terminating error and proves nothing. No new UAC prompt will be automatically retried without new authorization. My processes still lack system profiling privilege; success of the user-run pilot does not give them an administrator token.

Historical command in **administrator PowerShell**, from the repository root:

```powershell
& .\.venv\Scripts\python.exe tools/research/live_etw_heng.py
```

The new job's results must be checked before treating the capture as successful. Own DLL 0.8.2 symbols are preserved under runtime/symbols/0.8.2 for future analysis, with hashes; no game binary or SDK source is copied into Git.

<a id="réanalyse-hors-jeu-reproductible"></a>

## Reproducible reanalysis outside the game

Modules etw_analysis.py and export_etw.py validate the controller and trace hash before exporting. They retain commands, results, output hashes and xperf hash in a new timestamped analysis folder, then verify the trace again. They reject losses, an ambiguous PID or one not covering the whole trace, and attribution by an ambiguous or partial-lifetime TID. An explicitly partial analysis retains its incomplete status; it does not validate the x1 scenario. Symbols remain disabled.

From the project root, for the already available pilot:

```powershell
& .\.venv\Scripts\python.exe tools\research\export_etw.py runtime\etw\KenshiProbePilot_fd5e0c834b34\controller.json --top-threads 0
```

This path neither starts nor stops a WPR session. Its real execution under Python -I, with absolute paths, succeeded: runtime/etw/KenshiProbePilot_fd5e0c834b34/analysis-20261028T083738995195Z/analysis.json, completed=true, 4 510 observations. PID/process exports and loss counters agree with the initial record. The 27 new tests also cover trace changes during processing and export errors; they do not replace a real Heng capture.

The user stated they cannot intervene if a window appears. The administrator capture is therefore deferred; no manual action is expected now and no new UAC launch is attempted. Work outside the game continues. The watchdog heartbeat read around 08:41 UTC is fresh for PID 31368, without publication error. The process inventory available from the sandbox is partial; it does not prove the global absence of Windows sessions.
