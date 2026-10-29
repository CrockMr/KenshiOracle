<a id="horloge-de-jeu-et-retours-de-navigation--063"></a>

# Game clock and navigation returns — 0.6.3

The campaign near Heng observes game-clock progression at x5 equal to **4,999 times** that at x1. This result concerns the clock; it does not demonstrate that every AI task or path search completes without delay. No engine system was optimized or replaced.

<a id="horloges-vérifiées"></a>

## Verified clocks

Methods GameWorld::getTimeStamp_inGameHours(), TimeOfDay::getTotalHours(), GameWorld::getTimeStamp() and getLengthOfHourInRealSeconds() come from GameWorld.h and util/TimeOfDay.h; v100 linking and their native reads succeeded. Field game_total_hours remained at 404,334487915 for slightly over one second of pause. Raw timer getTimeStamp advanced from 104,432 to 105,448 during the same pause: it is not used as simulated time. Local evidence runtime/clock-pause-validation.json.

<a id="campagne-en-ville"></a>

## Town campaign

Data: runtime/measurements/city-paired-20261028T004449Z, order 1 then 5, three 600-frame windows per condition. Copy reloaded and prepared before each condition, camera checks at each window, same streaming/warm-up constants as benchmark-protocol.md. Clock intervals include requests and gaps between windows; they are not exactly frame-statistics intervals.

| Condition | Real seconds between readings | Game hours advanced | Game hours / real second |
| --- | --- | --- | --- |
| x1 | 14,911 | 0,136705 | 0,009167878 |
| x5 | 16,951 | 0,776884 | 0,045832215 |

Weighted rate ratio: 4,999217. getLengthOfHourInRealSeconds returned 109,090912 in both conditions. Mean frame times are 7,908..8,244 ms at x1 and 9,051..9,323 ms at x5. Here that frame difference does not translate into clock progression below the requested factor. This remains a town scene without battle, with imperfectly controlled caches/simulation evolution and external load.

<a id="retours-de-tous-les-appels-terminés"></a>

## Returns from all completed calls

New counters cover every findPath call completed within the windows, beyond only retained slow calls.

| Condition | True return | False return | Share of false returns | True wall sum ms | False wall sum ms |
| --- | --- | --- | --- | --- | --- |
| x1 | 121 | 41 | 25,31 % | 41,530 | 2,530 |
| x5 | 492 | 43 | 8,04 % | 140,001 | 3,827 |

These proportions describe each condition's observed calls. They do not prove a speed-dependent law: simulated time, requests, caches and real durations differ. False returns here are mostly very short, with no call ≥10 ms in stabilized windows. Optimizing every false return indiscriminately therefore does not follow from the measurements. Sums are inclusive wall time; they are neither exclusive CPU seconds nor total navigation time across every engine path.

The hook observes global NavMesh calls during this scene. Records are not yet associated with a character or specific town; inhabitants near Heng do not suffice to attribute every call to them.

A 180,318 ms call appears in the x5 context but ends at frame 14475, **before town preparation at frame 14517**. It is excluded from stabilized town windows. It consumes 171,875 user CPU ms, returns false and leaves the output array empty (0 before/after), with radius≈1,028 and water=6. This is not the same configuration as the four earlier slow calls with radius≈0,4/water=10. Its precise return reason is not exposed by the signature. Four transitional true returns produced 34..80 output elements, without interpreting physical length.

<a id="état-et-suite"></a>

## State and next steps

Same PID 37836 throughout measurement, no restart; the corrected watchdog remained healthy. Reference view, normal camera mode and pause were restored. Both quick.save files remain identical to their reference SHA-256. The audit outside the game retains provenance and avoids attributing preceding context calls to a new scene.

The next useful step concerns a reproducible battle and latency of actually completed tasks rather than repeating this town identically. Before changing an algorithm or adding a failure cache, establish mesh/door/streaming invariants and the link between expensive calls and character behavior. The three-hook ceiling remains respected; a new target must replace an existing one if it requires a hook.
