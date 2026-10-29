<a id="confirmation-randomisée-du-coût-de-collecte--protocole-préalable"></a>

# Randomized confirmation of collection cost — preregistered protocol

This protocol prepares a new paused acquisition with **the same 0.8.20 DLL**. It reports no results. It addresses two limitations of the [previous pilot](direct-aggregate-statistics-measurements.md): deterministic triad order and no MCP-server CPU measurement. Protection and restoration checks from the [initial protocol](observer-overhead-protocol.md) still apply.

<a id="plan-et-enregistrement-avant-capture"></a>

## Plan and registration before capture

The plan contains **36 blocks of 5 s**, grouped into **12 triads**. Each contains the following three conditions at one frequency:

| Condition | Work during the block |
|---|---|
| `baseline` | No getter; same scheduled timer wakeups |
| `full` | `get_frame_stats(n=60, detail='full')` at 1 or 10 Hz |
| `aggregates` | `get_frame_stats(n=60, detail='aggregates')` at 1 or 10 Hz |

For each frequency, 1 and 10 Hz, all six permutations of the three conditions occur exactly once. A triad's conditions remain contiguous; **the order of the 12 triads is randomized**, without changing their internal permutations. The executable reference is `analyze_observer_randomized.make_plan(seed)`. The actual resulting plan, triad indices, frequency, condition, and position are retained in full.

Before the first block, fix an unsigned **64-bit** integer seed without floating-point conversion, then record the seed, plan, this protocol, and SHA-256 values of sources, manifest, and DLL. The expected DLL is `0524ed8a218630b9b993e61966c807c36c2b9356d87a92ba2da0c7128d59b13e`. Retain the preregistration document's SHA and verify that the capture uses exactly its seed and plan. Storing a seed added after acquisition is insufficient. No reordering or seed selection based on initial results is permitted.

Each block is preceded by **1 s of neutral waiting without commands**, identical across all three conditions, followed by the same auxiliary checks. This is not warmup under the measured condition. Absolute deadlines use `perf_counter`/QPC, rechecked after waking. Only one request may be in flight, with no burst catch-up; delays, skipped slots, and overruns are recorded. A complete run schedules 660 requests and 330 control wakeups. An incomplete or off-schedule test is retained and flagged; it does not silently replace an unfavorable test.

<a id="état-maintenu-et-protection"></a>

## Maintained state and protection

The protocol changes neither native 0.8.20 code, its hooks, settings, nor game actors. It adds no combat, movement, actor input, or camera input. The `KenshiProbe_test` copy is used; `KenshiProbe_validation`, the copy, and protected snapshot are checked against their manifests.

Require a ready paused game, zero multiplier, constant simulated time, no tracked battle, the same game-process identity, and the same Root/CPU/service contract. Record population, active city, and positions: changes must remain visible, without claiming that pause determines all internal load. Take the camera reference after locking and stabilization, then check it at every block boundary and immediately before release. Do not add input to obtain artificially better timings.

At the end, verify pause, time, protected files, settings, DLL, sources, and restoration guards. Release camera control and restore the initial Edge setting. Coordinates after release are recorded separately; the protocol does not guarantee return to initial coordinates. On failure, retain the raw data and actual restoration state.

If the MCP server becomes unavailable, cleanup may use plugin TCP directly after freshly verifying game PID, creation time, executable, and arguments. This fallback is limited to the two idempotent calls `pause(paused=True)` and `set_camera_free(enabled=False, release_edge=True)`. Identity is checked before the MCP attempt and again before any TCP fallback. Every MCP failure and the fallback outcome are recorded. **A capture that used this fallback remains invalid for analysis, even if restoration succeeds.**

Scenes immediately before release and after cleanup are read directly through TCP after fresh game-identity verification, avoiding dependence on MCP-server survival. File and guard checks run in a block independent of camera or transport errors. Inability to restore is reported; it is not hidden by other successful checks.

<a id="cpu-du-serveur-mcp-et-bornes-distinctes"></a>

## MCP-server CPU and separate bounds

The MCP server persists throughout the series. Its identity is determined from its launch, then recorded with exactly **six fields**: `pid`, `created_at`, `executable`, `cmdline`, `parent_pid`, and `token`. The random launch token, separate from the plan seed, binds the exclusively created identity file to this stdio session. The owned script `observer_mcp_server.py` publishes identity, then imports and serves existing MCP in the same process; its code adds no implicit game getter.

Provenance retains the expected command, allowed Python executables, startup-script path, controller identity, and parent chain. The server must be the controller's direct child, or its descendant through **a single Python venv launcher**. Parent creation times precede their children's; chain, arguments, and identities are rechecked at every CPU read. Any launcher is not the measured server process. Server, controller, and game identities must be distinct. Ambiguous identity, restart, or absence at an endpoint invalidates the corresponding CPU measurement; no estimated consumption replaces it.

The retained counter belongs to **the server process alone**, excluding its launcher and any recursive child sum. Each `mcp_server_cpu_before` or `mcp_server_cpu_after` read contains the six-field identity, `user_seconds`, `system_seconds`, and QPC-derived `monotonic_seconds`. Identities must match the reference identity; time and counters are finite, CPU deltas nonnegative, and both endpoints must enclose the request window. The server's own interval normalizes its CPU delta; neither the requested 5 s nor the game interval substitutes for it.

The controller records this order: **server before, controller before, game before, request block, game after, server after, controller after**, then final getters. Game process/thread, server-process, and controller endpoints remain separate. Auxiliary getters, analysis, and response re-encoding run outside the game-CPU window; persistent effects remain possible. Controller CPU includes its collection work within its own bounds. No controller + server total is presented as an exact synchronous cost, and native service is not added to server CPU.

Callback statistics are fetched after the block in aggregate mode, with n calculated from scene boundaries, a single retained request, and a maximum budget of **3600 frames**. Retain first/last frame, requested/received n, and all attempts. Reduced n or budget overrun prevents calling the window complete. Sliding buckets are not treated as OS-counter windows.

<a id="comparaisons-annoncées-et-interprétation"></a>

## Declared comparisons and interpretation

The primary comparison is **`aggregates − full` within each frequency's six triads**, for three separately retained measurements:

- native service: difference between request medians in each block;
- MCP client latency: the same calculation on controller-observed round-trip duration;
- server-process CPU: difference in logical-processor equivalents, each calculated with its own endpoints.

These measurements are expected to decrease with the aggregate response. Publish all six differences, their median, range, and counts of positive, negative, and zero signs. Mixed signs or deltas near quantization prevent claiming a uniformly reproduced effect. No equivalence margin, significance threshold, or favorable selection rule is implicit. Repetitions within one session are not independent acquisitions.

`full − baseline` and `aggregates − baseline` comparisons, callbacks, game CPU, Root thread, controller, bytes, and queue waiting remain published as secondary diagnostics. The control retains plugin, hooks, watchdog, timer, and endpoints; it is not an uninstrumented game. Service results must remain wall durations covering only their documented scope, not exclusive CPU.

Retain quantized deltas, missing thread identities, and signed process-minus-computable-thread residuals without clamping or invented attribution. CPU, service, client, and callback scopes are not interchangeable. Randomization reduces an order limitation but removes neither machine noise, persistent effects, nor differences between successive scenes. **No FPS causality, rendering gain, or general engine-CPU reduction is inferred from this confirmation alone.**

<a id="preuves-attendues"></a>

## Expected evidence

The capture directory must make it possible to recover preregistration predating the first block, its 64-bit seed and plan, identified sources and binaries, raw data from every attempt, analysis, and restoration audit. Replay checks SHAs and the reconstructed plan, rejects inconsistent identities/bounds, and creates a new output without overwriting. Two Python hash seeds may check replay stability; they do not replace the randomization seed or constitute new acquisitions.

This document defines criteria before measurement. The actual seed, preregistration hashes, and results will belong to evidence from that future capture; they are not invented here.
