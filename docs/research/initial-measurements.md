<a id="premières-mesures-de-validation"></a>

# Initial validation measurements

Local measurement27 October 2026: plugin0.3.0, game 1.0.65 Steam through RE_Kenshi, test save KenshiProbe_test copied from KenshiProbe_validation. Outdoor Gut scene, two player characters, unchanged load camera, effective speed1, unpaused. User-selected 1280x720 resolution. VSync enabled in configuration.

Three separate300-frame windows after five seconds warmup. Raw responses in runtime/measurements/gut-x1-validation.json (local Git-ignored file), with timestamps, versions, mods.cfg hash and states bracketing windows.

| Window | Mean ms | Median ms | p95 ms | p99 ms | Maximum ms | Mean charsUpdate ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 10,390 | 10,136 | 12,144 | 15,697 | 17,834 | 0,213 |
| 2 | 10,986 | 10,512 | 13,762 | 16,864 | 19,798 | 0,233 |
| 3 | 10,699 | 10,333 | 12,608 | 16,382 | 18,369 | 0,228 |

Mean charsUpdateUT:0,00385 to 0,00409 ms per window. These hooks do not cover all AI and may overlap. Scene is not a large battle; no populated town prepared.

Codex, Firefox, Steam and Discord open; CPU load unquantified. Simulation advances during windows. Results validate collection and describe variation in this scene; they demonstrate no optimization gain, cannot be compared to earlier measurements at another resolution and do not identify pathfinding as bottleneck.

Speed5 scenario, repetitions after identical reload and town/battle scenarios remain to measure under benchmark-protocol.md.

<a id="série-appariée-032"></a>

## Paired series0.3.2

Second series reloaded KenshiProbe_test before each condition, retained load camera and applied five real seconds warmup. Same1280x720 resolution, three separate300-frame windows per speed. Local data: runtime/measurements/paired-20261027T225206Z/x1.json and x5.json. Same process throughout pair; speed reread/restored to 1 after trial.

| Speed | Window | Mean ms | p95 ms | p99 ms | Maximum ms | Mean charsUpdate ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 12,538 | 18,234 | 37,964 | 54,617 | 0,354 |
| 1 | 2 | 11,218 | 13,109 | 16,563 | 18,693 | 0,242 |
| 1 | 3 | 11,500 | 14,680 | 18,588 | 20,158 | 0,256 |
| 5 | 1 | 12,254 | 14,743 | 17,544 | 19,452 | 0,291 |
| 5 | 2 | 12,013 | 14,411 | 17,638 | 20,221 | 0,268 |
| 5 | 3 | 12,045 | 15,304 | 19,679 | 21,485 | 0,276 |

First speed1 window contains54,617 ms peak, retained. Mean durations overlap, order fixed (1 then 5). Single pair, unquantified concurrent load and partial system coverage cannot establish bottleneck or robust statistical difference. No system replacement or performance gain achieved.

Useful continuation: alternating-order repetition, then targeted navigation instrumentation and retained town/battle scenes. Requested three-profiling-hook cap leaves one slot for a targeted candidate.

<a id="navigation-observée-en-040-ordre-5-puis-1"></a>

## Navigation observed in 0.4.0, order5 then 1

Third hook NavMesh::findPath. Version 0.4.0 compiled in v100, loaded through automatic recovery and confirmed by ping.navmesh_profiling=true. Identified windows checked nonoverlapping. Local data: runtime/measurements/paired-20261027T230735Z/ (28 October, around 00 h07 Europe/Paris).

| Speed | Frames | Mean frame ms | findPath calls | Mean findPath time/frame ms | Longest call ms |
| --- | --- | --- | --- | --- | --- |
| 5 | 6068–6367 | 12,419 | 39 | 0,00658 | 0,11970 |
| 5 | 6373–6672 | 11,509 | 41 | 0,00750 | 0,18940 |
| 5 | 6677–6976 | 11,994 | 30 | 0,00579 | 0,11180 |
| 1 | 7497–7796 | 12,155 | 75 | 0,25440 | 2,01300 |
| 1 | 7807–8106 | 12,014 | 67 | 0,25103 | 1,89980 |
| 1 | 8114–8413 | 11,726 | 68 | 0,25423 | 1,99180 |

Hook observes real calls; costs differ substantially between conditions in this pair. Query count/nature differ, simulation evolves differently by speed, caches are not reset by protocol. Figures therefore establish neither a cost law by speed nor improvement over earlier versions. Time is wall/inclusive, calls assigned to completion frame; no exclusive CPU measurement or coverage of other navigation paths such as directPath.

Cap now reached: three system hooks. Next step concerns heavy scenarios/representative queries, retaining explicit coverage limitations/cache conditions.
