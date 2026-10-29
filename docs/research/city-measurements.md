<a id="première-campagne-près-de-heng--28-octobre-2026"></a>

# First campaign near Heng — October 28, 2026

Plugin 0.6.0, Kenshi 1.0.65 Steam, v100 x64. Two pairs ran in the same test process: order 1 then 5, followed by 5 then 1. Mean frame times overlap; neither an optimization gain nor an exclusive CPU bottleneck is demonstrated.

<a id="scène-et-protocole"></a>

## Scene and protocol

Each condition reloads KenshiProbe_test, then moves the two grouped player characters to Heng's x/z position from TownList through the public movement controller. Ten seconds of streaming at x1, a wait for a ready world, then five seconds at the target speed. Three distinct windows of 300 frames, with identities checked. Resolution 1280×720, VSync enabled in the initial settings. These loop intervals do not measure the GPU presentation rate.

The camera stays near the town, approximately 2240 units from its center; actual positions are retained in each JSON. The number of characters within 2000 units of the center varies from 157 to 163 before/after measurement, compared with two moved players. The complete update list ranges from 406 to 458 at condition observations. This is neither a battle nor an identical population at every instant.

Local raw evidence: runtime/measurements/city-paired-20261027T235740Z and city-paired-20261027T235907Z. Saves, raw measurements and game files remain outside Git. Manifests confirm restoration of the initial view, free mode false and pause true; source quick.save is unchanged at its reference SHA-256. PID 9772 remains stable across both pairs.

<a id="ordre-1-puis-5"></a>

## Order 1 then 5

| Speed | Frames | Mean frame ms | p99 frame ms | findPath calls | Mean findPath per frame ms | Longest call ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 17551–17850 | 8,007 | 12,042 | 134 | 0,3063 | 4,632 |
| 1 | 17859–18158 | 8,377 | 19,611 | 128 | 0,2206 | 5,516 |
| 1 | 18172–18471 | 7,385 | 10,603 | 121 | 0,1616 | 1,574 |
| 5 | 19770–20069 | 7,628 | 9,841 | 61 | 1,1259 | 162,153 |
| 5 | 20083–20382 | 7,719 | 19,386 | 91 | 1,1641 | 166,927 |
| 5 | 20387–20686 | 7,586 | 9,480 | 67 | 0,0352 | 1,102 |

<a id="ordre-5-puis-1"></a>

## Order 5 then 1

| Speed | Frames | Mean frame ms | p99 frame ms | findPath calls | Mean findPath per frame ms | Longest call ms |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 25529–25828 | 7,591 | 10,327 | 109 | 0,1147 | 2,391 |
| 5 | 25839–26138 | 7,428 | 9,713 | 97 | 0,0901 | 2,287 |
| 5 | 26146–26445 | 8,215 | 14,340 | 134 | 0,0710 | 1,319 |
| 1 | 27732–28031 | 7,460 | 14,834 | 142 | 0,3290 | 2,673 |
| 1 | 28040–28339 | 7,838 | 21,517 | 33 | 0,0413 | 4,072 |
| 1 | 28350–28649 | 8,094 | 17,384 | 49 | 0,0714 | 3,160 |

<a id="ce-que-ces-résultats-justifient"></a>

## What these results justify

The 162..167 ms spikes do not recur in the reverse order. Calls and costs differ even at the same speed. Caches are not purged, streaming and simulation continue, identical real-time warm-up represents different simulated durations at the target speed, and load from other applications is not quantified. Do not conclude that x5 speeds up or slows down pathfinding, or compare FPS with the Gut scene, whose camera differs.

Hooks measure inclusive wall-clock durations, attributed to the frame in which a call ends. In the first two x5 windows, the longest call greatly exceeds the window's maximum frame interval (14,810 and 26,178 ms). This justifies classification by thread and examining calls that cross window boundaries; it does not yet prove a 167 ms CPU cost blocking the main thread.

The next useful instrumentation is to distinguish the GameWorld thread from other threads in the existing findPath hook, retain a few slow calls with public parameters/results, and record process CPU consumption over the same intervals. Keep the three-hook limit. Then prepare a preservable, repeatable battle on the copy before replacing any system.

This instrumentation was subsequently implemented in 0.6.1 and extended in 0.6.2: see [thread-specific diagnosis](navigation-diagnosis.md). Captured slow calls run on a thread distinct from GameWorld; four new samples also have CPU cost of the same order as their wall time. A camera guard now excludes conditions where the view drifts.
