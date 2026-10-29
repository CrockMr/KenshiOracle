"""Run the prebuilt v100 OWN-snapshot oracle/benchmark; never attach to a game."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "plugin/Probe.cpp", "plugin/FrameStatistics.h", "plugin/StatisticsDetail.h",
    "plugin/json.h", "plugin/NavTelemetry.h", "plugin/CallTelemetry.h",
    "plugin/CharsTelemetry.h", "plugin/FunctionProbeTarget.h",
    "tests/StatisticsLegacyOracle.h", "tests/StatisticsSnapshotFixture.h",
    "tests/test_statistics_detail.cpp", "tests/test-statistics-detail-v100.cmd",
    "tests/benchmark_statistics_detail.cpp", "tests/benchmark-statistics-detail-v100.cmd",
    "tests/run_statistics_detail_benchmark.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path, runs: int) -> dict:
    if not 1 <= runs <= 10:
        raise ValueError("runs must be 1..10")
    sources = {name: sha(ROOT / name) for name in SOURCES}
    binaries = {name: ROOT / "plugin/build/native-tests" / name for name in (
        "test_statistics_detail.exe", "benchmark_statistics_detail.exe")}
    hashes = {name: sha(path) for name, path in binaries.items()}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "OWN immutable native snapshots; no game access or FPS inference",
                "source_sha256_before": sources, "binary_sha256": hashes,
                "runs": [], "completed": False}
    try:
        oracle = subprocess.run([str(binaries["test_statistics_detail.exe"])], cwd=ROOT,
                                capture_output=True, check=True, timeout=180)
        oracle_data = json.loads(oracle.stdout)
        if not oracle_data.get("passed") or oracle_data.get("aggregate_detail_rows_built") != 0:
            raise ValueError("native oracle did not pass")
        (output / "oracle.json").write_bytes(oracle.stdout)
        manifest["oracle"] = {"path": "oracle.json", "sha256": sha(output / "oracle.json"),
                              "result": oracle_data}
        all_rows = []
        fixture_inventory = None
        for index in range(runs):
            result = subprocess.run([str(binaries["benchmark_statistics_detail.exe"])], cwd=ROOT,
                                    capture_output=True, check=True, timeout=180)
            report = json.loads(result.stdout)
            if (report.get("compiler") != 1600 or report.get("pointer_bytes") != 8 or
                    report.get("synthetic_only") is not True or len(report["rows"]) != 448 or
                    not all(item["oracle_equal"] for item in report["fixtures"])):
                raise ValueError("unexpected native benchmark schema")
            if fixture_inventory is not None and fixture_inventory != report["fixtures"]:
                raise ValueError("fixture bytes or inventory changed between processes")
            fixture_inventory = report["fixtures"]
            name = f"run-{index + 1}.json"
            (output / name).write_bytes(result.stdout)
            manifest["runs"].append({"path": name, "sha256": sha(output / name)})
            for row in report["rows"]:
                all_rows.append({"process": index, **row})
        summary = []
        for fixture in fixture_inventory:
            for serialize in (False, True):
                rows = [r for r in all_rows if r["fixture"] == fixture["name"] and
                        r["serialize"] is serialize]
                groups = {op: [r["per_operation_ms"] for r in rows if r["operation"] == op]
                          for op in ("legacy_full", "direct_full", "legacy_projected", "direct_aggregates")}
                pairs = {}
                for row in rows:
                    pairs.setdefault((row["process"], row["repetition"]), {})[row["operation"]] = row["per_operation_ms"]
                reductions = [100 * (p["legacy_projected"] - p["direct_aggregates"]) / p["legacy_projected"]
                              for p in pairs.values()]
                summary.append({"fixture": fixture["name"], "serialize": serialize,
                                "timing_samples_per_operation": len(pairs),
                                "median_ms": {op: statistics.median(values) for op, values in groups.items()},
                                "paired_compact_reduction_pct_median": statistics.median(reductions),
                                "paired_compact_reduction_pct_range": [min(reductions), max(reductions)]})
        (output / "summary.json").write_text(json.dumps({"schema": 1, "fixtures": fixture_inventory,
                                                       "rows": summary}, indent=2) + "\n", encoding="utf-8")
        manifest["summary"] = {"path": "summary.json", "sha256": sha(output / "summary.json")}
        manifest["source_sha256_after"] = {name: sha(ROOT / name) for name in SOURCES}
        manifest["source_unchanged"] = manifest["source_sha256_after"] == sources
        manifest["binary_unchanged"] = {name: sha(path) for name, path in binaries.items()} == hashes
        if not manifest["source_unchanged"] or not manifest["binary_unchanged"]:
            raise ValueError("sources or binaries changed during benchmark")
        manifest["completed"] = True
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), "completed": True, "runs": runs,
            "oracle_checks": manifest["oracle"]["result"]["checks"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.runs)))
