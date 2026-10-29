<a id="mesures-reproductibles--protocole-initial"></a>

# Reproducible measurements — initial protocol

Collector tools/research/benchmark.py records separate N-frame windows, raw responses, and context. It changes neither pause, speed, nor camera. Results under runtime/measurements/ are local; publish only an aggregate report under docs/.

<a id="préparation"></a>

## Preparation

1. Preserve KenshiProbe_validation and work on the KenshiProbe_test copy. Record the mod-list hash and plugin/game versions.
2. Load the same save before every scenario. Keep the camera at its loaded position, constant resolution, identical video settings and VSync. Also record other applications and, if possible, their CPU load.
3. Set speed and reread it through ping.frame_speed_multiplier; the UI's visual label may stay at 1x. Pause must be recorded explicitly.
4. Allow a fixed warmup in real seconds. When comparing scenes with evolving simulation, note that the same real warmup represents different simulated durations at different speeds. Reset the save between tests and repeat conditions.

<a id="collecte"></a>

## Collection

Example from the root with the Python environment configured:

```powershell
.venv/Scripts/python.exe tools/research/benchmark.py --label gut-x1 --save KenshiProbe_test --scene 'Gut, caméra de chargement' --frames 300 --samples 3 --warmup 10 --output runtime/measurements/gut-x1.json
```

The collector waits at least N+2 new frames between windows. It checks frame count and absence of pause/speed changes during the wait. Observed bounds before/after the request are retained. The detailed series is limited to the last 100 frames, but aggregates cover N.

With plugin 0.4.0, first_frame/last_frame and series identifiers make this verification explicit: the collector rejects inconsistent identifier counts or a window overlapping its predecessor. Earlier versions remain readable through observed bounds. tools/research/live_suite.py accepts `--order 5 1` to reverse the pair; plugin versions and context are retained in every result.

Do not calculate a global percentile by averaging window percentiles. Present each window and its variation. Historical charsUpdate and charsUpdateUT times are inclusive and potentially overlapping; their sum does not measure all CPU or attribute cost to pathfinding. Since0.7.6, the physics probe replaces charsUpdateUT, whose fields remain null; the same inclusive-cost and partial-coverage principle applies. See physics-probe-measurements.md for new windows and thread identities.

<a id="campagne-à-préparer"></a>

## Campaign to prepare

- Outdoor validation scene: Gut, existing save with two player characters. Useful for pipeline validation; battle load not prepared.
- Populated city: tools/research/live_city_suite.py Heng rebuilds the scene from KenshiProbe_test with prepare_town_scene. Before each condition: normal camera mode, reload, group moved to Heng, ten seconds of streaming at x1, wait for world_ready, target speed, five seconds of warmup, then three300-frame windows. Population and camera recorded before/after; reject fewer than 50 characters within 2000 units of center or a PID change. Reverse with --order 5 1. The helper restores camera mode before the final load, then leaves the game paused. The copy is unchanged on disk; the scenario is rebuilt, not saved. Caches and streaming are not reset.
- Large battle: save, character count, and initial order remain to be defined.
- Speed1 then 5 for every scene, with multiple repetitions and alternating condition order.

Keep frame frequency distinct from simulation throughput. VSync may limit FPS without identifying a CPU bottleneck; a pathfinding conclusion requires targeted measurements and controlled conditions. Do not change user settings without preserving their initial state and being able to restore it.

<a id="diagnostic-des-threads-et-du-cpu"></a>

## Thread and CPU diagnostics

With0.6.1, the collector also verifies findPath thread categories and retained slow calls. live_city_suite.py accepts --samples and --frames to extend observation. It retains a diagnostic read of at most3600 frames in context after streaming: this may include frames before preparation and pauses; its identifiers are explicit, and it must not be confused with post-warmup measurement windows.

Helper resources.py uses psutil, declared in requirements-dev.txt, to read overall CPU counters for only the game process identified by path and creation time. PID reuse, a different path, or regressing counters fail the measurement. process_resources covers the interval enclosing collect(), including its MCP calls and waits; it is not precisely aligned with each frame window. User/system times are consumed CPU seconds, while hooks measure wall milliseconds.

Option `live_battle.py --thread-cpu` adds two Windows thread readings, matched by TID and creation time; raw endpoints, errors, and read durations are retained. Disappeared threads are excluded with a reason, never assumed to have zero initial counters. GameWorld/observed navigation worker/other groups count each thread once; role labels may overlap. A worker's whole CPU is not a function's exclusive CPU. The signed process-minus-thread-sum residual remains visible without normalization. The28 October campaign has94/63 ms reads and three threads absent at the second boundary; see thread-cpu-measurements.md.

Separate context `thread_attribution_statistics` may cover up to 3600 frames and retains at most32 slow calls. Read its truncation flag; it does not replace the final 600-frame window or identify all workers. analyze_navigation.py now retains both phases and their own observation bounds, then deduplicates by call identity.

one_cpu_percent can exceed100 %:150 % represents an average of 1,5 busy logical processors. machine_capacity_percent divides that value by the system-reported total logical-processor count. This is neither occupancy of each physical core nor CPU attribution to findPath. The process includes engine, rendering, and other loaded modules; outside application load remains unquantified.

Since the 0.6.2 campaign, live_city_suite enables enforce_scene_stability: the collector rereads the scene after every window and rejects a camera-mode change or center/position movement exceeding five units from the starting read. Final position and population are also checked. This adds one read per window to the enclosing interval; it is not per-frame camera monitoring. An error is retained in the manifest, then restoration is attempted. A floating panel or physical input may alter the view: do not retain a condition failing this guard as a controlled comparison.

With0.6.3, every controlled window adds simulation_progress between two scene reads: game-hour progression, QPC duration, and game hours per real second. The first is the population read before collection, subsequent ones are end-of-window reads. These intervals enclose requests and small gaps between windows; they do not exactly match the N statistics intervals. A non-finite/regressing clock or zero real duration fails measurement. Older plugins without these fields remain readable. Simulation throughput must be compared separately from FPS and CPU times.

analyze_navigation.py audits retained slow calls offline, removing repeated observations and retaining provenance/camera checks. It infers no false-return rate from this above-threshold sample alone; new navmesh_findPath_results counters must provide proportions among all completed calls in a window.

<a id="horizon-simulé-commun-depuis-un-snapshot"></a>

## Shared simulated horizon from a snapshot

`tools/research/live_snapshot_horizon.py --snapshot-proof <preuve-snapshot.json> --baseline-proof <preuve-observation-en-pause.json>` uses a snapshot still managed by the current plugin, without NPC creation or save writes. It runs the order x1,x5,x5,x1; every condition reloads the snapshot and requires pause, unique names, complete cohort, health, pose, clock, and camera matching the reference. The one-unit vertical guard remains unchanged; rejection stops the campaign and remains recorded. This visible-state check does not cover all AI states or equipment.

The default horizon is 0,5 game hour. The loop observes the scene every 0,2 real second until crossing that horizon; final pause and overshoot are retained. This threshold concerns world time, not a completed-task count. Medical states and external targets describe evolution without inventing hits or a responsible attacker. Camera and speed are checked at every observation. The test stops if PID changes, cohort becomes incomplete, or the horizon is not reached within 120 seconds.

The first pilot showed natively that `set_game_speed` removes pause. The clock boundary must therefore precede this command. CPU encloses activation, thread reads, and final pause; its interval differs from the clock interval. No additional simulated warmup is applied after loading; caches and streaming may vary with order. Final600-frame statistics and 3600 context remain separate windows, without claiming to summarize the whole horizon. The helper then reloads the initial copy paused and checks complete manifests and preferences. `analyze_snapshot_horizon.py` produces an offline summary with overshoots and excluded conditions.

Since the environment audit, the controller also requires a complete stable update list, equal to the first accepted run in labels/multiplicities and exact positions, before any speed command. Collector environment_diagnostics brackets list_characters with two scenes and refuses to call a comparison complete if count, pause, clock, or camera changes. The horizon controller now uses500 rows by default, adjustable with --environment-limit (1..500); the initial pilot remains at 250. An incomplete inventory causes a retained exclusion, not assumed equivalence; names are not identifiers. Precheck live_environment_preflight.py showed172 then 147 characters, including74 then 48 Fogmen, while both tracked actors were identical. See environment-preflight-measurements.md. The guard is tested and replayed against these raw data; no new identical native quartet was run. Do not keep reloading until a conveniently accepted state appears.

Pilot live_heavy_inventory.py validated the 500/250/500 sequence at Heng:412/250/412 rows for a constant total412, both complete inventories identical, the 250-row one excluded. See heavy-inventory-measurements.md. The500 limit is independent of the 65536-byte native-response limit; another population or long labels may still require different collection. Do not declare exhaustive a result reduced after a size error.

<a id="contraste-descriptif-pause--x1--pause"></a>

## Descriptive pause / x1 / pause contrast

`tools/research/live_pause_cpu.py` retains the same city and view across three successive phases without claiming to fix the work performed. Each activation is followed by three seconds of unmeasured stabilization, then a requested twenty seconds of process/thread CPU counters and scene reads every 0,5 second.500-row inventories bracket every phase; clock, pause/speed, camera, and PID are checked. Groups cover whole threads, and the same TIDs are matched across phases only with identical creation FILETIME. Thread absence at a boundary is not replaced with zero.

`analyze_pause_cpu.py` retains the signed x1-minus-mean-pause contrast, drift between pauses, quantized residuals, and separate intervals. Final600-frame statistics and 3600 context are not declared CPU-aligned; their frames and any overruns are explicit. No test suite may run during measurement. Population may evolve between phases and external load remains unquantified: results provide neither exclusive simulation/rendering cost nor optimization gain. See pause-cpu-measurements.md for the first native observation.

Shared-thread ranking uses maximum CPU rate descending, then numeric TID and creation time to break ties. The twelve retained rows' cutoff is thus stable across Python processes. Reports predating this fix remain retained; changed ordering at equal CPU is not a new measurement or gain.

Explicit mode `tools/research/live_pause_cpu.py --speed 5 --adaptive-tail --tail-max 3600` retains the same three phases, with label running_x5 and expected speed recorded. Analysis rejects speed1 in this phase, a boolean in place of speed, or a campaign whose phases declare different speeds. Omitted options retain the historical x1/600-frame scenario and analysis format.

Adaptive selection rereads the scene after the requested twenty seconds, then requests `min(cap, observed_frame − entry_frame − 1)` frames, cap 1..3600. A phase without a frame completed strictly after entry is rejected; no older frame is borrowed. Raw data retain selection scene, cap, and requested count; analysis recalculates that count and checks actual bounds/window continuity. Inventories must be complete at both boundaries under the independent 500-row and 64 KiB limits. Calls are counted at their **end**: a call ending in the window may have started before it. The expanded 3600-frame context stays separate and may overlap another phase. Native speed and measured simulated time are not completed-task counts or gain measurements.

<a id="combat-urbain-lourd-à-x5"></a>

## Heavy urban combat at x5

`tools/research/live_heavy_battle.py` prepares one40-NPC cohort within the native 20-pair limit, on the separate copy, at Mongrel with already mutually hostile factions. It retains four requested5/5/10/10-second windows, cohort observations every 0,25 second, complete health, process/thread CPU, bracketing SDK roles, bounded statistics, and 500-row inventories. Losing a cohort member never becomes an assumed death; partial preparation is never retried without reload. The finally restores copy, pause, and camera, then checks protected files/preferences.

Collector statistics_budget reduces get_frame_stats reads only after the native oversized-response error, halving count down to 1. Raw data retain every attempt and actual accepted count, including requested3600-frame contexts; other errors are not retried. Reduction does not claim complete CPU-window coverage. The battle controller uses this collector; older other scripts retain their own policies. Offline replay with analyze_heavy_battle.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER. See [the capture and its limitations](heavy-battle-x5-measurements.md).

<a id="observations-dadresses-utilisateur-pss"></a>

## PSS user-address observations

`tools/research/live_instruction_active.py PREUVE_CPU --count N` requires completed evidence from the same process, the copy restored paused, and an authorized session allowing thirty minutes for closure. It selects four TID/creation identities from the x1 recording, prepares Heng, then performs1..120 lightweight captures without cloning. The current version reads the scene, waits a variable0,8..1,2 s delay, then captures: no MCP call immediately before PSS. Native times, complete helper times, and actual scene-to-capture delay are retained. A call exceeding250 ms stops the series without automatic retry; the finally restores copy, pause, and camera.

`tools/research/analyze_instruction_active.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER` checks contexts/releases, modules, counts, and cadence offline, then recalculates progression and endpoint CPU counters. Address frequencies are neither CPU fractions, stacks, nor exclusive coverage. Helper duration does not measure exact target suspension; user contexts do not expose the kernel stack. All three tests and their limitations are in [instruction-active-measurements.md](instruction-active-measurements.md). Do not repeat failed clone capture1450 without a new condition, add a hook from an observed RVA, or transfer identities from an old session.
