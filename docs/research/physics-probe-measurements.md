<a id="sonde-physique-076--remplacement-dune-sonde-existante"></a>

# Physics probe 0.7.6 — replacing an existing probe

The **PhysicsActual::_NV_backThreadUpdate(float,bool)** probe is linked in v100 x64, installed and observed in-game. It replaces charsUpdateUT: **three system probes remain active**, alongside charsUpdate and NavMesh::findPath. The original body and arguments are unchanged. This is an additional measurement, without engine optimization.

At Heng, the function is observed on **thread 34744**, distinct from GameWorld/Renderer **8612**. Its creation identity exactly matches the Windows CPU observation from the same process. The entire thread consumes approximately **0,043 logical processor at x1** in this capture; this target is less costly here than the principal workers still unidentified. This does not measure all physics or work it might delegate.

<a id="déploiement-et-preuves"></a>

## Deployment and evidence

- Public declaration: `references/KenshiLib_Examples_deps/KenshiLib/Include/kenshi/PhysicsActual.h`, nonvirtual method; GetRealAddress/AddHook mechanism checked in core/Functions.h. No RVA is copied into the plugin.
- **Visual C++ 2010 x64/v100** compilation and linking succeeded. Native PhysicsTelemetry tests passed under v100, including accumulation, partial CPU availability, overflow and reused TIDs.
- Deployment archive: `crashes/20261028T045306717729Z-deployment-076`, old 0.7.5 DLL, log, configuration and preferences. Its reason is `deployment_0.7.6`, not an engine crash.
- Identities reread before shutdown: old game 19892, watchdogs 21824/10472, paths/commands/creation times checked. Only these project processes were stopped. At the final check, new game **19920**, watchdog wrapper **36144**/child **19296**; automatic bootstrap and copy loading.
- `runtime/deploy-076.json` retains DLL hashes and identities; `runtime/physics-076-smoke.json` confirms 0.7.6, three probes, absent charsUpdateUT and the first 300 physics calls while paused.
- Raw town evidence: `runtime/scenarios/pause-cpu-20261028T045548Z.json`, SHA-256 **2dad2c394101224206352c7195e3f15d39d51f04ee7292060ea2471fb3801617**; summary `runtime/physics-076-analysis.json`.
- Complete final state: `runtime/physics-076-final.json`.

Restarting clears the old in-memory snapshot association. The **738 files of KenshiProbe_test_scene_20261028T022539600581Z are preserved**, but older scripts requiring battle_tracking_restored must not assume that property remains available. No old snapshot was overwritten or recreated under the same name.

<a id="mesure-native"></a>

## Native measurement

The live_pause_cpu pause/x1/pause procedure is reused for a **new profiling hypothesis** with the new hook: the same view and town within this run, three seconds of settling before each requested twenty-second interval. No pytest runs during the intervals. Each final window below contains **600 frames and 600 physics calls**, without overflow or unavailable CPU readings.

| Phase | Mean inclusive physics duration per frame | Maximum call | User CPU of retained calls | Kernel CPU of retained calls | Whole-thread CPU over the OS interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pause before | 0,088694 ms | 0,299900 ms | 0 ms | 0 ms | 0,009223 logical processor |
| x1 | 0,560210 ms | 1,079000 ms | 62,5 ms | 62,5 ms | 0,042877 logical processor |
| Pause after | 0,112456 ms | 1,115900 ms | 31,25 ms | 0 ms | 0,013027 logical processor |

Per-call GetThreadTimes counters are quantized: **zero does not prove no computation occurred**. Hook CPU sums cover only calls whose reads succeed. Whole-thread CPU covers an approximately twenty-second OS interval; the 600 frames form a shorter final window, slightly later than its heartbeat boundary. These columns do not share exact boundaries and must not be divided to claim exclusive function coverage.

Physics identities use a TID and exact decimal creation FILETIME (`134376368000459413` in this process). All three CPU-thread joins succeed. Inclusive time is assigned to the call's ending bucket; execution can begin before the window. Neither other functions on that thread nor additional workers are attributed to this method alone.

Whole-process CPU in this run: **1,735513 / 2,153826 / 1,779278 average logical processors**; populations **396 stable / 419–442 / 442 stable**. The principal unattributed workers are now 33728 and 38832, with creation identities specific to this new process. They are not equated with old TIDs 37324/39984 from behavior alone. These numbers demonstrate no improvement over 0.7.5: instrumentation, process, population, streaming and caches differ. The RE_Kenshi panel was not visually verified after this startup; this observation does not qualify a performance comparison between versions.

<a id="contrat-et-validation"></a>

## Contract and validation

Historical fields charsUpdateUT_mean_ms and per_frame.charsUpdateUT_ms are **null**. Ping exposes probe state and system_hook_count=3. Physics adds totals, a maximum, available/unavailable CPU partitions and at most eight detailed identities; `unlisted` retains totals not individually detailed. Partitions are validated with physics + navigation. See protocol.md for units, KENSHI_PROBE_PHYSICS_THREAD_CPU and the semantics of calls spanning frames.

**207 Python tests pass in 4,00 s**, in addition to the native v100 tests. They check partition consistency, nonfinite or negative counters, identity overflow, removed telemetry remaining null, and rejection of a physics/CPU join with a different creation time. Optional fields remain readable in older reports without a physics probe.

The final check verifies **702 KenshiProbe_validation files, 702 KenshiProbe_test files and 738 old-snapshot files**, all matching their references. settings.cfg is byte-identical to its predeployment state. The initial copy is reloaded paused, with the normal reference view, Edge scrolling=true, no active tracked battle or temporary control. Fresh watchdog, zero publication errors; configuration and activation remain bounded to **October 28 at 22 h 15 UTC**, without extension.

The administrator CPU-stack pilot remains pending. A public avenue to examine next is ThreadClass.h: threadID, threadHandle and name are declared, and GameWorld exposes AINonRenderThread(). Observing these roles could provide further identities without a fourth hook, after checking types, linking and reading conditions. No new attribution of these two workers is assumed.
