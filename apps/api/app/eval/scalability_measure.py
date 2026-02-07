from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from ..clients.opensearch_client import get_opensearch


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * p
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _index_size_gb(index_name: str) -> float:
    client = get_opensearch()
    try:
        stats = client.indices.stats(index=index_name, metric="store")
        idx = stats.get("indices", {}).get(index_name, {})
        size_bytes = idx.get("total", {}).get("store", {}).get("size_in_bytes") or 0
        return float(size_bytes) / (1024.0 ** 3)
    except Exception:
        return 0.0


def _latency_stats_from_run(path: Path) -> dict[str, float]:
    payload = _load_json(path)
    values = [float(r.get("elapsed_ms") or 0.0) for r in payload.get("results", [])]
    if not values:
        return {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    return {
        "avg_ms": sum(values) / len(values),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
    }


def _resolve_run_path(manifest_path: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (manifest_path.parent / p).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute measured scalability rows from manifest + run files.")
    parser.add_argument("--manifest", required=True, help="Path to scalability manifest JSON")
    parser.add_argument("--out-csv", required=True, help="Output CSV path")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = _load_json(manifest_path)
    rows_in = manifest.get("runs", [])

    rows_out: list[dict[str, Any]] = []
    for row in rows_in:
        label = str(row.get("label", ""))
        corpus_size_lines = int(row.get("corpus_size_lines", 0))
        index_name = str(row.get("index_name", ""))
        indexing_hours = float(row.get("indexing_hours", 0.0))
        run_path_raw = str(row.get("run_path", "")).strip()

        lat = {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
        if run_path_raw:
            run_path = _resolve_run_path(manifest_path, run_path_raw)
            if run_path.exists():
                lat = _latency_stats_from_run(run_path)

        rows_out.append(
            {
                "subset_label": label,
                "corpus_size_lines": corpus_size_lines,
                "index_name": index_name,
                "index_size_gb": f"{_index_size_gb(index_name):.3f}",
                "indexing_time_hrs": f"{indexing_hours:.3f}",
                "avg_query_latency_ms": f"{lat['avg_ms']:.2f}",
                "p50_query_latency_ms": f"{lat['p50_ms']:.2f}",
                "p95_query_latency_ms": f"{lat['p95_ms']:.2f}",
                "run_path": run_path_raw,
            }
        )

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "subset_label",
        "corpus_size_lines",
        "index_name",
        "index_size_gb",
        "indexing_time_hrs",
        "avg_query_latency_ms",
        "p50_query_latency_ms",
        "p95_query_latency_ms",
        "run_path",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows_out:
            writer.writerow(row)

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
