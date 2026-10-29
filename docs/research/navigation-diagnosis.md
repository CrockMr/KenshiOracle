<a id="navigation-par-thread--première-observation-061"></a>

# Navigation by thread — first observation 0.6.1

The diagnosis places observed slow findPath calls on a thread separate from GameWorld. Their wall time therefore does not measure a direct, equal-duration block executed on the main thread. An indirect effect on simulation remains possible and unquantified. No engine optimization was performed.

<a id="nouvelle-observation-en-bataille--073"></a>

## New battle observation — 0.7.3

`runtime/scenarios/battle-20261028T015352Z.json` measures ten NPCs created near Mongrel, with reinforcements and commands through MCP stdio. The final 600-frame window contains 300 calls, all on another thread: 299 true and one false. Of eleven ≥10 ms calls retained without truncation, ten true calls take 10,210..11,632 ms and produce 92..98 elements; the false call takes **130,579 ms**, consumes **125 ms CPU**, and leaves **six output elements**, versus zero on entry. CPU counters for these short calls are quantized to zero or 15,625 ms; an observed zero is not treated as absence of computation.

This false return with partial output prevents interpreting the boolean as “no path returned.” The public signature still gives no detailed reason. Calls remain global, without attribution to fighting characters. Population, cohort, and initial-state differences prevent causal comparison with older Heng measurements. The navigation auditor must explicitly support this capture format before integrating its events into previous campaigns; do not force their provenance into the paired-city schema. See battle-observations.md for the recipe, checks, and limitations.

<a id="preuve-native"></a>

## Native evidence

Local campaign runtime/measurements/city-paired-20261028T000701Z, order 5 then 1, five 600-frame windows per condition, same process 13036. Scene near Heng, rebuilt before each condition according to benchmark-protocol.md. Source and copy quick.save match the reference SHA-256 after testing; initial view, normal mode, and pause restored.

| Condition | Measured frames | findPath calls | On GameWorld | On other threads | Retained ≥10 ms calls | Slow-call range ms |
| --- | --- | --- | --- | --- | --- | --- |
| x5 | 3000 | 977 | 0 | 977 | 13 | 154,488–165,824 |
| x1 | 3000 | 1006 | 0 | 1006 | 1 | 160,981 |

Counter/duration/maximum partitions passed collector checks. No call in these windows remained unclassified, and no slow record was lost to saturation of the 32-entry buffer. All retained slow calls have thread_id=28440 versus game_thread_id_at_start=17356, hierarchical=true, radius≈0,4, water=10, and result=false. This return specifies neither the cause nor permanence of failure; do not automatically treat it as a permanently unreachable destination.

At x5, these thirteen calls represent 1,33 % of observed calls and 84,44 % of their inclusive wall-duration sum (2080,095 ms of 2463,352 ms). This makes them a diagnostic target, not yet an estimate of recoverable CPU.

Example: a 161,349 ms call starts at frame 2473 and is counted at frame 2492, in a window whose maximum GameWorld interval is 14,058 ms. It spans several frames on another thread. Some goal_key values recur, but keys alone do not describe identical requests: positions, mesh state, and streaming conditions require examination before any cache proposal.

<a id="cpu-du-processus"></a>

## Process CPU

| Condition | Enclosing interval s | User CPU s | System CPU s | Equivalent logical processors | Capacity share on 16 logical processors |
| --- | --- | --- | --- | --- | --- |
| x5 | 23,516 | 32,094 | 19,250 | 2,183 | 13,646 % |
| x1 | 22,469 | 27,984 | 21,984 | 2,224 | 13,899 % |

These OS counters cover the whole process, all threads and modules, over the interval enclosing collection; they are not attributable to navigation or a specific window. A low share of total capacity cannot rule out a single-thread bottleneck. CPU durations for individual findPath calls were not measured: 160 ms wall time may include computation, waiting, or descheduling. Outside application load remains unquantified.

<a id="qualité-de-mesure-et-suite-justifiée"></a>

## Measurement quality and justified next steps

Version 0.6.1 transfers counters from the previous bucket and publishes the new frame under the same lock. This removes labeling ambiguity when a concurrent call ends at that boundary. The hook retains the same arguments, original call, and result; nevertheless, diagnostics add a read lock at start and a bounded write for slow calls. Do not interpret a cross-version difference as an engine improvement.

The next useful observation is CPU consumed by the calling thread during slow calls, for example through public Win32 counters, with their resolution and probe cost documented. Retaining public start/goal positions would also distinguish truly repeated requests from shared keys alone. Then examine the causes of result=false and simulation impact before changing algorithms, delays, or caches. The limit remains three system hooks; there is no reason to add a fourth.

<a id="extension-062--cpu-des-appels"></a>

## Extension 0.6.2: call CPU

The optional GetThreadTimes probe was compiled with v100 and enabled for this campaign. All four Havok-vector components are copied before the call from public member hkVector4f::m_quad; no engine argument changes. Observed vectors are near local coordinates200,150,-30, while the city has very different world coordinates: **do not label them world positions**. NavMesh.h also exposes worldShift/shiftWorld; the effective transformation was not observed. The start vector's fourth component varies from 914 to 1737 in these examples and is not treated as a spatial coordinate.

The first 0.6.2 pair, city-paired-20261028T001447Z, revealed 1512,481 units of camera drift at x1. This condition is excluded from a fixed-view comparison; quality.json retains that classification without changing raw responses. The three successful 10..16 ms calls in its transition context validated CPU/vector fields but do not describe the targeted long failures. The drift's cause is not established. Closing an RE_Kenshi panel and reloading restored the initial view. The collector now checks camera mode and positions after each window, with a five-unit tolerance; successive restorations can be compared against a reference.

The retry with this guard, city-paired-20261028T002159Z, completed both measurement files, x1 then x5: 5×600 frames per condition, 247 x1 calls and 803 x5 calls. Cameras passed per-window checks. Four slow x5 calls, on a thread separate from GameWorld, returned false:

| Wall time ms | User CPU ms | Kernel CPU ms | Total CPU ms |
| --- | --- | --- | --- |
| 167,619 | 171,875 | 0 | 171,875 |
| 163,888 | 125 | 15,625 | 140,625 |
| 164,592 | 125 | 31,250 | 156,250 |
| 161,599 | 156,250 | 15,625 | 171,875 |

In these four observations, CPU is of the same order as wall time: a simple-wait hypothesis does not describe their principal cost. Counters are quantized; a CPU sample may slightly exceed wall time and is not artificially capped. The CPU bracket includes some probe work around the call. The mean of 200 startup reads was 0,230 µs per read in this process, which is no cost guarantee on the other thread. API and units are documented in [GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes).

Goals and starts are not all identical. Two calls share exactly the same captured start but target different goals. This observation does not justify reusing a failure across requests or mesh states. The next measurement-based lead is to study costly false-returning searches and their coverage, then their effect on simulation throughput. No engine cache, delay, or algorithm changed.

Automatic restoration of this second pair failed **after both measurements were written**: the watchdog exited on a Windows state-file lock, and its finally closed its game. The original manifest retains restored=null. Incident archived and watchdog fixed; a new instance then recovered the reference view and pause. Evidence is separate in quality.json and runtime/scenarios/restored-camera-062-recovered.json; do not present this recovery as incident-free completion of the original process.
