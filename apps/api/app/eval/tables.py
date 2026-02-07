from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from ..clients.opensearch_client import get_opensearch


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_markdown_table(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_scalability(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("runs", [])


def _load_run_avg_latency(path: Path) -> float:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("results", [])
    if not rows:
        return 0.0
    return sum(float(r.get("elapsed_ms") or 0.0) for r in rows) / len(rows)


def _index_store_gb(index_name: str) -> float:
    client = get_opensearch()
    stats = client.indices.stats(index=index_name, metric="store")
    idx = stats.get("indices", {}).get(index_name, {})
    size_bytes = idx.get("total", {}).get("store", {}).get("size_in_bytes") or 0
    return float(size_bytes) / (1024.0 ** 3)


def build_scalability_table(*, manifest_path: Path, out_csv: Path, out_md: Path) -> None:
    rows_in = _load_scalability(manifest_path)
    rows_out: list[dict[str, Any]] = []

    for row in rows_in:
        label = str(row["label"])
        corpus_size_lines = int(row["corpus_size_lines"])
        index_name = str(row["index_name"])
        indexing_hours = float(row.get("indexing_hours", 0.0))

        run_path_raw = row.get("run_path")
        avg_latency = 0.0
        if run_path_raw:
            run_path = Path(run_path_raw)
            if not run_path.is_absolute():
                run_path = manifest_path.parent / run_path
            avg_latency = _load_run_avg_latency(run_path)

        index_gb = _index_store_gb(index_name)
        rows_out.append(
            {
                "corpus_size_lines": corpus_size_lines,
                "index_size_gb": f"{index_gb:.3f}",
                "indexing_time_hrs": f"{indexing_hours:.3f}",
                "avg_query_latency_ms": f"{avg_latency:.2f}",
                "subset_label": label,
            }
        )

    headers = [
        "subset_label",
        "corpus_size_lines",
        "index_size_gb",
        "indexing_time_hrs",
        "avg_query_latency_ms",
    ]

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in rows_out:
            w.writerow(row)

    _write_markdown_table(out_md, headers, rows_out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render markdown tables and compute scalability table.")
    parser.add_argument("--metrics-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--scalability-manifest", required=True)
    args = parser.parse_args()

    metrics_dir = Path(args.metrics_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    x_rows = _read_csv(metrics_dir / "table_x_retrieval_performance.csv")
    y_rows = _read_csv(metrics_dir / "table_y_granularity.csv")

    _write_markdown_table(
        out_dir / "table_x_retrieval_performance.md",
        [
            "retrieval_configuration",
            "precision_at_10",
            "recall_at_100",
            "map",
            "task_success_rate_pct",
        ],
        x_rows,
    )
    _write_markdown_table(
        out_dir / "table_y_granularity.md",
        [
            "granularity_level",
            "precision_at_10",
            "recall_at_100",
            "map",
        ],
        y_rows,
    )

    build_scalability_table(
        manifest_path=Path(args.scalability_manifest),
        out_csv=metrics_dir / "table_z_scalability.csv",
        out_md=out_dir / "table_z_scalability.md",
    )

    print(f"wrote {out_dir / 'table_x_retrieval_performance.md'}")
    print(f"wrote {out_dir / 'table_y_granularity.md'}")
    print(f"wrote {out_dir / 'table_z_scalability.md'}")


if __name__ == "__main__":
    main()
