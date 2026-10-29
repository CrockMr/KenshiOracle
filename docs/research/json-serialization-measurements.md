<a id="sérialisation-json-synthétique-et-version-0812"></a>

# Synthetic JSON serialization and version 0.8.12

**The new serializer writes the same bytes with less intermediate work.** On two owned synthetic trees of 20,8 and 25,9 KiB, the paired old/new median ratio is **3,350763 and 3,542731**. This is a local serialization improvement measured outside the game; no FPS or exclusive engine-CPU gain is demonstrated.

<a id="mesure-reproductible"></a>

## Reproducible measurement

`tools/research/benchmark_json.cpp` includes only Windows and our JSON library, without SDK or game data. Three deterministic fixtures: a small80-byte object,40 **synthetic** actors with seven parts, and 100 **synthetic** rows with three parts. They do not reproduce the full game scene or statistics schema; the number40 does not make this a measurement of a real NPC's cost.

Compilation **MSVC2010/v100 x64**, flags **/O2 /EHsc /MD /W3**. Each acquisition launches three processes; each measures seven repetitions in rotating order of five operations,60 iterations per cell: construction with internal copies and destruction, copy/destruction of a prebuilt tree, envelope with copy/destruction, reference serialization, and current serialization. Each cell is timed by QPC and divided by 60. First repetitions are retained. A consumed checksum prevents measuring only an empty loop; no allocation counter is collected.

Times are inclusive wall durations, with ambient system load, allocations, caches, and scheduling effects not isolated. The game stays paused during acquisitions but is not suspended; these values are not exclusive CPU. The benchmark does not use the DLL's linker optimizations and is not a direct measurement of its network throughput.

`tests/json_legacy_serializer.h` retains **our**0.8.11 serializer as a compatibility oracle. Only recursive namespace qualification and a type alias differ to avoid ADL; this is neither game code nor a decompilation. In the first binary, this code and the current 0.8.11 serializer produce the same bytes and paired median ratios0,997585/0,998404/1,011076, close to 1. In the second binary, only **plugin/json.h** differs in the benchmark source inventory; compilers, flags, fixtures, and measurement code remain the same.

<a id="résultats-du-binaire-candidat"></a>

## Candidate binary results

Mean operation times in milliseconds over 21 cells, each of 60 iterations. “Copy” includes destruction; “construction” includes the fixture's internal copies. Ratios are paired by process/repetition, not calculated across two games or different worlds.

| Fixture | Bytes | Construction | Copy | Envelope + copy | Old serialization | New | Median old/new ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Small object |80|0,002014|0,000512|0,001127|0,007267|0,001726|4,409412|
|40 synthetic actors |20806|1,891860|0,174992|0,173433|2,973062|0,883630|3,350763|
|100 synthetic rows |25928|2,345826|0,225878|0,225815|3,715743|1,037406|3,542731|

Paired ratio min..max:2,917605..6,238757 for the small object,**3,201990..3,575176** for20,8 KiB,**3,306065..4,009083** for25,9 KiB. The small object's tiny values are more noise-sensitive; all 21 raw durations are retained for every operation and fixture. Copy/construction costs do not change in this version; mean differences between separate captures remain descriptive.

<a id="changement-et-compatibilité"></a>

## Change and compatibility

Under0.8.12, `json::dump` uses `appendQuoted` and `appendSerialized` to write recursively into a single buffer. It avoids an ostringstream per key, string, boolean, or container, and temporary subtree strings. **Numbers retain exactly0.8.11's v100 formatting, classic locale, and precision16**; no new numeric algorithm. Map-key order, control/quote/backslash escaping, UTF8 bytes, non-finite values rendered null, and absence of spaces are preserved.

`tests/test_json.cpp` compares output byte for byte against the oracle: bytes0..255 in strings/keys,12 special numeric values (including−0,extremes,subnormal,Inf/NaN),10000 deterministic numbers under a comma-decimal C++ locale,1000 deterministic nested trees, and four sizes around 64 KiB. Existing parser/Unicode/surrogate/error/depth tests still pass. The comparison covers these cases; it is not formal proof for every arbitrary tree.

Production changes only **plugin/json.h** and the version number in Probe.cpp. Value copies, queue, hooks, Game access, SDK types/layout, and engine algorithms do not change. Still17 tools and three probes charsUpdate/findPath/Havok. The64 KiB line/response limit and error contract remain identical; native large-string tests verify produced bytes, not the entire TCP boundary behavior on their own.

<a id="provenance-et-rejeu"></a>

## Provenance and replay

- Baseline: **runtime/json-benchmark/legacy-0811/controller.json**, SHA **acf74c6642e9a72e7c80ca161e86f68d6c9efd6b808d1e2683304ea0411b93b1**.
- Candidate: **runtime/json-benchmark/append-candidate-0812/controller.json**, SHA **b1b7d86fe7dede32ee6471900463a6ff23d7c221b50d618517c1a81f714fdc24**.
- Report: **runtime/json-benchmark-analysis-0812.json**. Each directory contains raw stdout outputs and their fingerprints, the exact separate binary, and fingerprints of the five relevant sources.

```powershell
& .\.venv\Scripts\python.exe tools\research\analyze_json_benchmark.py runtime\json-benchmark\legacy-0811\controller.json runtime\json-benchmark\append-candidate-0812\controller.json --baseline-sha256 acf74c6642e9a72e7c80ca161e86f68d6c9efd6b808d1e2683304ea0411b93b1 --candidate-sha256 b1b7d86fe7dede32ee6471900463a6ff23d7c221b50d618517c1a81f714fdc24 --output runtime\new-report-json.json
```

Analysis checks the compiler/architecture/order/count plan, finite/positive durations and consistent units, stable fixture fingerprints, consumed checksum, measurement sources unchanged except json.h, and stdout/separate-binary fingerprints. Fixture FNV fingerprints provide a quick check alongside exact native comparison, not cryptographic content proof. Captures are retained, not overwritten by a new run.

<a id="déploiement-local-et-validation"></a>

## Local deployment and validation

**624 Python tests pass in 23,48 s**, including15 new analysis/replay checks; native JSON v100 tests pass. DLL 0.8.12 **280064 bytes/SHA8077d19487888e152cca41e14058400f1e9414cbac6b16b1cde35ce669ae78ed**, separate PDB **10341376 bytes/SHA c363dbd5abf66e46a37eed1fc909ab1307e50fe6b6ca194f3503375f539314cd** under runtime/symbols/0.8.12. Archived deployment **crashes/20261028T153641982090Z-deployment-0812**, evidence runtime/deploy-0812.json. Old processes verified by exe/command/creation time before stopping, and old 0.8.11 DLL preserved.

Smoke test **runtime/json-serializer-0812-smoke.json** validates actual MCP,17 tools,three probes,active Havok,SDK identities,pause,and service metadata. A subsequent wire check verifies truncated JSON,duplicate key,invalid UTF8,and unknown command with a Unicode/quote/backslash/newline identifier, then ping and the copy still paused. The first wire controller incorrectly expected a string error instead of the documented code/message object; its failure **runtime/json-serializer-0812-wire.json** is retained, without game mutation. Expectation corrected after rereading error() and the protocol, new separate capture **runtime/json-serializer-0812-wire-1793201950211417600.json**,completed=true/four cases. This was not a native regression.

Independent audit **runtime/json-serializer-0812-final.json** recalculates saves/snapshot/settings: **702/702/738 identical files**, settings byte-identical to the predeployment state, and guards false. Game **24320/Unix creation 1793201827.3623693**, pause/multiplier0 at **404,3333339691162 h**, normal camera/temporary control released/Edge=true,battle inactive,fresh watchdog/zero errors,WPR inactive,and no remaining controller. Helpers **13424/creation 1793201826.9521272** and **33328/creation 1793201826.9085033**, requiring fresh verification before stopping. Final n3600 statistics accepted in 48986 re-encoded compact bytes. Accepted wire capture SHA **6e8bb38717746197b9ccf97ba5cc86923334d71549f429e41f229ad62183ddbf**, rejected test SHA **bca9f202ff0f49ed179538fcfc14af9942a03ed2e51625e0ef3596ca2e15415a**. This step does not rerun combat40: the change concerns our network serializer and already has targeted validation.

Next useful measurement: verify a short active window with existing telemetry if the question concerns observation cost in combat. Optimizing Value copies requires a separate measurement and network ownership/event verification; it is not included here. Do not convert the serialization factor into a global gain. No user/administrator intervention expected; autonomous deadline22 h15 UTC/23 h15 Paris unchanged.
