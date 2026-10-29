<a id="chronologie-des-recherches-de-chemin-lentes-à-heng"></a>

# Timeline of slow path searches at Heng

Both x5 captures show an initial burst of `findPath` calls lasting at least 10 ms, then no further completion above that threshold in the retained window. This conclusion concerns slow calls: the temporal distribution of fast searches remains unknown. It does not establish a steady-state engine regime.

<a id="résultats-hors-jeu"></a>

## Offline results

| Capture | Window frames | All calls | Retained slow details | Distribution across four frame quarters | QPC envelope of retained calls |
|---|---:|---:|---:|---|---:|
| Heng x5, 0.8.9 | 501422–504179 (2758) | 778 | 7 of 7 | 7 / 0 / 0 / 0 | 1997,5414 ms |
| Heng x5, 0.8.10 | 11260–14091 (2832) | 1227 | 8 of 8 | 8 / 0 / 0 / 0 | 1393,3195 ms |

The quarters divide **frame** indices, not four equal durations. The envelopes run from the first QPC start to the last end reconstructed as `started_qpc_ms + elapsed_ms`. They represent neither a CPU sum nor all navigation activity. Native QPC clocks and the CPU reader's monotonic clocks remain separate.

Slow completions occupy frames **501516–501771** and **11511–11681**, respectively. All these calls are hierarchical and return `false`. Their inclusive wall-time sums are **1179,9232 / 1391,0739 ms**; their quantized CPU-counter sums are **1078,125 / 1359,375 ms**. No exclusive-coverage ratio against the whole thread is inferred.

The captured XYZ pairs and parameters are all distinct: **7 and 8 groups**, whereas `start_key/goal_key` pairs form only **6 in each capture**. Equal keys therefore do not describe geometrically identical requests. The descriptive projection retains radius, water, hierarchical, and initial output size; the raw data also retain the keys and all four vector components. The fourth component is not treated as a spatial coordinate. Cache validity and the causes of `false` returns remain unknown.

The second recording's 3600-frame context contains ten slow calls: the same eight, plus two out-of-window completions at frames **10925 and 10963**. The analysis deduplicates observations by PID, process creation time, TID, and QPC start. It does not sum the context and main window. Across all three phases, the two captures contain **8 and 10 unique calls**, respectively, with provenance retained.

Call rows do not carry thread creation time. A TID matching a stable lifetime at both CPU boundaries is reported as a **candidate**, without claiming an exact call/FILETIME association. Process and thread data are recalculated from raw counters before results are read.

<a id="reproduction-et-preuves"></a>

## Reproduction and evidence

Analyzer: `tools/research/analyze_navigation_timeline.py`. It requires a complete restored capture, detailed mode, and an expected SHA; it rejects an existing output file. `aggregates` responses, including those from combat 0.8.19, are explicitly unavailable for this timeline and are never converted into zero calls.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_navigation_timeline.py runtime\scenarios\pause-cpu-x5-adaptive-20261028T133051Z.json --expected-sha256 f1d846061c4f8f905481b82d54303e9e9c7a1d87605d315879ab666a5a0667c3 --output runtime\new-navigation-089.json
& .\.venv\Scripts\python.exe tools\research\analyze_navigation_timeline.py runtime\scenarios\pause-cpu-x5-adaptive-20261028T140511Z.json --expected-sha256 60d74111457fa6d932efd5bf41d19fbf8fee96c3c497f0e57ba535ec8355f34a --output runtime\new-navigation-0810.json
```

Both Python seeds, **0 and 8675309**, produce byte-identical reports. Evidence: `runtime/navigation-timeline-replay-proof.json`.

- 0.8.9 report: `runtime/navigation-timeline-089-seed0.json`, SHA **5e7c695f95e3e8a7fd3b3f94d4889748c2852465d06102b963f8fb71ece9b16f**.
- 0.8.10 report: `runtime/navigation-timeline-0810-seed0.json`, SHA **2c7d48aca1d1010e26f96f0a5472aec62abc39effbc4ce1021bc0e7e5e3dc360**.
- **22 targeted tests pass**, covering identity, QPC, contradictory duplicates, retention, compact mode, SHA, and overwrite rejection.

Selection is complete at the declared threshold in both windows, without slowcall truncation. However, the final 100 `per_frame` rows alone cannot reconstruct all fast calls by subperiod. A future acquisition is justified only by a specific hypothesis requiring this information. No new capture, DLL, probe, or game API was needed for this result.
