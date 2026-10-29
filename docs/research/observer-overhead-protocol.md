<a id="protocole-du-coût-de-collecte-après-0819"></a>

# Collection-overhead protocol after 0.8.19

**Proposed protocol; this document establishes no acquisition or validation.** It targets the effect of MCP reads on a paused game with the same DLL and settings. Service and transport durations evolved differently after [JSON transfers](json-ownership-measurements.md); [aggregate mode 0.8.19](aggregate-statistics-measurements.md) reduces transmitted volume but still constructs complete statistics. Those effects therefore need separate measurement.

<a id="question-et-plan-borné"></a>

## Question and bounded design

Compare three conditions in the same game session, with a persistent MCP server and controller:

| Condition | Reads during the block | Frequencies to test |
|---|---|---|
| M — minimal acquisition | No getter; same timer wakes as other conditions | 1 Hz and 10 Hz schedules, without a request |
| F — full response | `get_frame_stats(n=60, detail='full')` | 1 Hz and 10 Hz |
| A — aggregates | `get_frame_stats(n=60, detail='aggregates')` | 1 Hz and 10 Hz |

A pilot comprises **six triads per frequency**, each containing M, F and A for **5 s per condition**: 36 blocks, or 180 s of planned windows excluding preparation. Each of the six orders MFA, MAF, FMA, FAM, AMF and AFM is used once per frequency. The pilot uses preregistered deterministic order: for each permutation, the 1 Hz triad precedes the 10 Hz triad. Frequencies are interleaved and positions balanced, but the design is not randomized; a systematic order effect remains possible. Conclusions remain those of a short pilot.

Each F/A block schedules 5 or 50 reads respectively, spaced from a fixed monotonic origin. One request at a time; no catch-up burst. Record planned deadline, actual departure/return, missed deadlines and any overrun past the block's end. A block that fails to maintain frequency remains evidence of saturation, not a successful observation at nominal frequency. Control M retains timer and shared-observation costs: it is not an uninstrumented game.

The controller explicitly uses `time.perf_counter` for scheduling, latency, process/thread CPU boundaries and controller CPU boundaries. Its declared implementation and resolution are retained. Every wait rechecks the deadline, even after an early asyncio wake. Old `time.monotonic` timestamps are neither converted nor mixed with this clock.

<a id="état-initial-et-zones-hors-mesure"></a>

## Initial state and areas outside measurement

Retain the SHA-identified DLL, native version, Root selection, CPU and command-timing flags, settings, resolution, window/focus and watchdog cadence. Use KenshiProbe_test only, with a protected reference copy. Require effective pause, zero multiplier, identical simulated time, world ready, stable camera and no tracked battle. Verify PID/executable/creation identities; a restart invalidates pilot continuity. Inventory changes remain recorded and affected blocks are flagged, even while paused.

Warm up the session and history before measurement. The executed design retains a warm-up of **1 s of neutral waiting without commands** before every block, then shared scene and role reads. This pause is not condition-specific warm-up; carryover from the previous block remains possible. Identity, scene and role reads are identical in every block and outside its CPU window. No character list, capture, compilation or other scenario during blocks. Keep responses in memory; write files and calculate JSON sizes after the window to avoid adding that work to the observed regime.

The controller must finish OS CPU counters **before** final scene/statistics getters. The initial reading follows checks and warm-up. These areas exclude auxiliary commands from the selected CPU window; they do not automatically align scene, bucket and CPU boundaries.

<a id="mesures-et-bornes-à-conserver"></a>

## Measurements and boundaries to retain

- **Game:** user/kernel CPU of the process and threads computable at both OS endpoints; Root identity joined by TID and creation, monotonic durations, omissions and signed residual. Other machine processes are neither stopped nor reconfigured to improve results.
- **Collector:** controller and MCP-server CPU, with PID/executable/creation and their own endpoints. Avoid double-counting wrappers and flag a disappeared child. Reduced client work must not be claimed as reduced game CPU.
- **Every read:** MCP wall latency, native service, queue wait, n actually received, frame boundaries, mode, any error and compact re-encoded JSON bytes. These bytes are not exact TCP/MCP traffic. [Service scopes](command-service-measurements.md) notably exclude network serialization; their differences do not become exclusive CPU.
- **Callbacks:** retrieve aggregate statistics after the block within the **3600-frame** limit and explicitly record first/last frame. Calculate n from observed counters and verify continuity, new buckets and boundaries. A window over budget or requiring reduced n is not an entire comparable window: retain failure and uniformly shorten a new design, without overwriting the trial. The rolling getter may shift start/end relative to CPU; publish these scopes separately, without promising a capture frozen exactly over five seconds.

Aggregate mode makes that last reading feasible with a small payload but does not supply individual rows for the whole window. Boundaries cannot reconstruct each frame's duration or retrospectively remove every frame affected by an auxiliary check.

<a id="analyse-et-critères-de-conclusion"></a>

## Analysis and conclusion criteria

Fix comparisons before acquisition: A−F for volume, latency and CPU; F−M and A−M for total collection effect at each frequency. Keep all six triads separate, then publish their six paired differences, median, range and number of agreeing signs. Also present M controls in time order to expose drift. Frequent sign changes, substantial drift or missed deadlines prevent concluding a stable effect; retain results as indeterminate or a throughput limit.

Fewer bytes imply neither lower CPU nor latency. CPU hypotheses must be falsifiable by their corresponding measurements, without selecting favorable blocks only. The pilot cannot establish universal improvement; confirmation needs a declared design and a new independent series. Do not generalize from pause to combat or interpret callback interval as displayed FPS.

CPU counters are quantized; [helper calibration](root-cpu-measurements.md) does not guarantee their in-game precision. Retain zeros, deltas exceeding short wall times and signed residuals. Do not subtract Root duration, services and OS CPU to manufacture exclusive attribution. No result is pooled with old cohorts as if it came from the same deterministic world.

<a id="faisabilité-restitution-et-autorisation"></a>

## Feasibility, restoration and authorization

The **17 existing tools and three systems** suffice: full/aggregate getters, pause, scene, heartbeat and identities are available; OS CPU readers and service metadata exist. Controller `tools/research/live_observer_overhead.py` and analyzer `tools/research/analyze_observer_overhead.py` are prepared and tested for preregistered order, repetitions, deadlines, collector CPU and rejection of non-comparable windows. This protocol needs no new system hook or MCP tool.

Cleanup must restore the paused copy, time, camera and controls, then verify saves/settings/guards and watchdog state. Keep raw evidence even on failure. The user explicitly cancelled the former **October 28, 2026 at 22:15 UTC / 23:15 Paris** end and asked to continue. The controller now accepts `session_until: null`; if a new numeric deadline is configured, budget and closing reserve still apply. Every campaign remains bounded by its plan.

The camera reference is taken after locking and stabilization, then checked through the read before release. The pilot restores the initial Edge setting, not camera coordinates from before locking: drift after release remains possible. Before-lock, locked and post-release scenes are retained separately; save verification runs even if a camera check fails.
