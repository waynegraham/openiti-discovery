from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any


def _band(ms: float) -> str:
    if ms < 50.0:
        return "Excellent"
    if ms < 100.0:
        return "Good"
    if ms <= 300.0:
        return "Acceptable"
    return "Poor"


def _read_latencies(path: Path) -> tuple[str, list[float], dict[str, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    config = str(meta.get("config", path.stem))
    latencies = [float(x) for x in (meta.get("query_latencies_ms") or [])]
    effective_mode_counts = {
        str(k): int(v)
        for k, v in (meta.get("effective_mode_counts") or {}).items()
    }
    return config, latencies, effective_mode_counts


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * pct
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    frac = index - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Milestone 8 latency classification report from run_*.json artifacts.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--page-size", type=int, default=20)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_files = sorted(run_dir.glob("run_*.json"))
    if not run_files:
        raise SystemExit(f"No run_*.json files found in {run_dir}")

    rows: list[dict[str, Any]] = []
    for run_file in run_files:
        config, latencies, effective_counts = _read_latencies(run_file)
        if not latencies:
            continue
        p95 = _percentile(latencies, 0.95)
        rows.append(
            {
                "config": config,
                "sample_count": len(latencies),
                "avg_ms": f"{statistics.fmean(latencies):.2f}",
                "p50_ms": f"{_percentile(latencies, 0.50):.2f}",
                "p95_ms": f"{p95:.2f}",
                "classification": _band(p95),
                "page_size": args.page_size,
                "effective_mode_counts": json.dumps(effective_counts, ensure_ascii=False),
            }
        )

    if not rows:
        raise SystemExit("No latency samples available in run metadata")

    rows.sort(key=lambda r: r["config"])
    _write_csv(
        Path(args.out_csv),
        rows,
        [
            "config",
            "sample_count",
            "avg_ms",
            "p50_ms",
            "p95_ms",
            "classification",
            "page_size",
            "effective_mode_counts",
        ],
    )

    md_lines = [
        "# Milestone 8 Latency Report",
        "",
        f"- Page size: `{args.page_size}`",
        "- Classification bands: `<50ms Excellent`, `<100ms Good`, `100-300ms Acceptable`, `>300ms Poor`",
        "- Note: latency bands are report-only for Milestone 8.",
        "",
        "| Config | Samples | Avg (ms) | P50 (ms) | P95 (ms) | Class |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        md_lines.append(
            f"| {row['config']} | {row['sample_count']} | {row['avg_ms']} | {row['p50_ms']} | {row['p95_ms']} | {row['classification']} |"
        )

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_md}")


if __name__ == "__main__":
    main()
