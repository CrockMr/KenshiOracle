> Active state: **0.8.1**, selected target AI::update4Frame; [new measurements and startup selection](ai-target-selection-measurements.md). Periodic0.8.0 measurements below remain historical.

<a id="profilage-ciblé-aiperiodicupdate--080"></a>

# Targeted AI::periodicUpdate profiling — 0.8.0

**5 984 completed AI::periodicUpdate calls linked exactly to SDK role world_ai_non_render in final x1 window at Heng.** Their accumulated inclusive time divided by600 service frames is **0,701594 ms/frame**. No calls recorded in two final pause windows. Second simulation-sensitive worker still lacks function attribution: this entry does not capture it in these windows.

Version **0.8.0**, compiled/linked v100 x64 and validated through real MCP, retains **17 tools and three system probes**. AI probe replaces PhysicsActual::_NV_backThreadUpdate; others charsUpdate/NavMesh::findPath. GameWorld/Renderer service callbacks unchanged. No engine algorithm changed.

<a id="signature-et-collecte"></a>

## Signature and collection

AI/AI.h publicly declares void AI::_NV_periodicUpdate(float frametime), nonvirtual wrapper. Hook resolved by KenshiLib::GetRealAddress on wrapper, linked to SDK library then actually observed; virtual periodicUpdate itself not passed to GetRealAddress, per core/Functions.h. No RVA or layout recoded.

Compilation exposed header error: AI.h declared class CharacterMessage while Character.h defines this enum. prepare_deps.py replaces incorrect declaration with SDK Character.h include; idempotent fix in Git-ignored dependency. First failed compilation not installed; subsequent compilation/linking successful.

CallTelemetry.h shares bounded counters with old PhysicsTelemetry.h interface, retained for native tests. Hook measures **completed outer calls** only. TLS-depth RAII guard lets nested calls reach original but avoids counting duration twice; nested_entries_skipped_total counts them separately. C++ unwinding restores depth after exception without swallowing game exception. Outer calls not completing normally not counted as completed.

QPC brackets original; inclusive wall time may include awaited delegated work. KENSHI_PROBE_AI_THREAD_CPU=1 enables two GetThreadTimes per outer call, with TID/creation FILETIME. Guard protects counter deposit, never original execution. Eight identities per bucket retained; unlisted bucket keeps excess counters. Calls, maxima, CPU availability and partitions reconciled without clamping. Completed call deposited into completion-frame bucket; may start beforehand. No AI pointer retained.

Startup CPU read measures about 0,232 µs/request in this launch (200 requests). Not calibration of complete instrumentation cost. CPU counters quantized, reads contribute to observation; no gain/exclusive cost inferred from this number alone.

<a id="preuves-et-protocole"></a>

## Evidence and protocol

- Deployment archive: crashes/20261028T061944920384Z-deployment-080, reason deployment_0.8.0, old 0.7.9 DLL/config/preferences/log. Old game7716/watchdogs12552/37596 identities checked before stopping; only this project's processes affected.
- New game **19296**, smoke runtime/ai-080-smoke.json: AI active, physics disabled, three probes, seven SDK roles, correct optional native parameter.
- Raw: **runtime/scenarios/pause-cpu-20261028T062209Z.json**, SHA-256 **05f3d92f9b9e129e560d5096248c197d42bf38820fa401bdfa3508cf826161bf**.
- Analysis: **runtime/ai-080-analysis.json**, recomputed by analyze_ai_periodic.py, with endpoint SDK identity/unknowns retained.
- Final state: **runtime/ai-080-final.json**.

Controller reloads KenshiProbe_test, prepares Heng, allows streaming to stabilize, then runs pause/x1/pause with three seconds stabilization and twenty requested OS seconds per phase. Observes scene/camera/speed/clock every 0,5 second, collects bounded inventory/final600-frame statistics plus broader context. SDK roles read paused before/after sequence, no intervening load. Identities bracket each CPU scene and stay stable. Copy reloaded paused at end. No pytest during measurement.

| Phase | Process CPU / real time | Mean logical processors | Observed population | AI calls in final 600 frames | Inclusive AI mean/frame |
| --- | --- | ---: | --- | ---: | ---: |
| Pause before | 34,859375 s / 20,359 s | 1,712234 | 399 stable | 0 | 0 ms |
| x1 | 48,312500 s / 20,344 s | 2,374779 | 420..440 | 5 984 | 0,701594 ms |
| Pause after | 36,406250 s / 20,391 s | 1,785408 | 440 stable | 0 | 0 ms |

Simulation clock stationary paused,+0,186449 hour at x1. Signed process-minus-threads residuals:+0,062500 / +0,015625 / −0,062500 s; two threads absent at second x1 endpoint, explicitly excluded. Population/time/caches evolve: descriptive contrast, not causal phase experiment or version comparison.

<a id="fonction-et-thread-entier"></a>

## Function and whole thread

Final x1 window covers frames **15597..16196**,600 frames, all within phase. Mean service frame 7,396405 ms; statistics-request interception ends after CPU heartbeat, window not exactly aligned with 20,344 s OS interval.

All AI calls on **TID 18336,creation FILETIME 134376419978624433**, world_ai_non_render identity at both SDK/OS-thread endpoints. Inclusive wall total **420,956201 ms**, maximum call **0,844700 ms**. Call CPU **250 ms user +203,125 ms kernel**,5 984 available reads, none unavailable. No overflow/nested entry observed in this window.

**453,125 ms call CPU exceeds420,956 ms wall sum here.** Short-call CPU measurements quantized and include read effects; values retained raw, without clamping or conversion into exclusive coverage. They prove neither acceleration, core saturation nor exact per-small-call CPU duration.

**Whole thread** consumes6,671875 s CPU over x1 OS interval, or 0,327953 mean logical processor; about 0,047583 then 0,045210 in pauses. Function/OS windows differ: do not divide totals to claim exclusive thread share.

Other worker, **19228 / creation 134376419978623026**, changes from **0,002302 to 0,326417 then 0,001533 logical processor**. Absent from retained function rows; role remains unknown, “other worker” does not mean “all remaining AI”. Main GameWorld/Renderer service, TID 38532, stays around 0,744450 /0,744999 /0,737917 logical processor. No number transferred to old reused PID/TID.

<a id="validation-et-restauration"></a>

## Validation and restoration

**241 pytest pass in 4,00 s.** Native v100 x64 tests: partitions, merging, overflow, partial CPU, reused TID, restoring nested depth after exception. Python tests: old physics history unchanged, new AI counters, incompatible reprocessed probes, exact CPU identities, changed SDK creation refused for attribution, bracketed scenes. AI buckets absent/None in older captures.

Game 19296, watchdog wrapper **20820**/child **14244** at final check, to recheck before stopping. **702 KenshiProbe_validation files,702 KenshiProbe_test and 738 old-snapshot files compliant**; settings.cfg byte-identical to beforehand, guards false. Copy paused, normal reference view, Edge scrolling=true, tracked combat inactive, temporary control released. Fresh watchdog/zero error, autoload successful, deadline/activation **1793225700** unchanged. Controller finished; old snapshot on disk, in-memory ownership no longer assumed. RE_Kenshi panel not visually checked, other applications uncontrolled.

<a id="prochaine-hypothèse"></a>

## Next hypothesis

AI::_NV_periodicUpdate covers one entry on identified thread; no automatic optimization follows. Worker 19228 needs another entry or CPU stacks. AI/AI.h also exposes **void AI::_NV_update4Frame(float)**: verify binding then test **replacing** periodicUpdate, never as fourth probe. Startup function selection, explicitly reported in metadata, would avoid rebuilding one DLL per target; do not present update4Frame statistics as periodicUpdate. Retain old fields null when corresponding probe absent. Administrator ETW pilot still pending; do not repeat question/blocked attempt without user-side change.
