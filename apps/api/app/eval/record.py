from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_table_x(metrics_dir: Path) -> dict[str, dict[str, str]]:
    path = metrics_dir / "table_x_retrieval_performance.csv"
    if not path.exists():
        return {}

    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            config = str(row.get("retrieval_configuration", "")).strip()
            if config:
                rows[config] = row
    return rows


def _avg_latency_ms(run_rows: list[dict[str, Any]]) -> float:
    if not run_rows:
        return 0.0
    return sum(float(r.get("elapsed_ms") or 0.0) for r in run_rows) / len(run_rows)


def _rows_for_runs(
    *,
    queries_path: Path,
    qrels_path: Path,
    run_dir: Path,
    metrics_dir: Path,
    tables_dir: Path,
) -> list[dict[str, str]]:
    query_payload = _load_json(queries_path)
    query_count = len(query_payload.get("queries", []))

    qrels_payload = _load_json(qrels_path)
    qrels_count = len(qrels_payload.get("qrels", []))

    table_x = _read_table_x(metrics_dir)
    run_files = sorted(run_dir.glob("run_*.json"))
    now = datetime.now(timezone.utc).isoformat()

    out: list[dict[str, str]] = []
    for path in run_files:
        payload = _load_json(path)
        meta = payload.get("meta", {})
        rows = payload.get("results", [])
        config = str(meta.get("config", "unknown"))
        metrics_row = table_x.get(config, {})

        out.append(
            {
                "run_recorded_at_utc": now,
                "config": config,
                "query_count": str(query_count),
                "qrels_count": str(qrels_count),
                "run_file": str(path),
                "avg_latency_ms": f"{_avg_latency_ms(rows):.2f}",
                "precision_at_10": str(metrics_row.get("precision_at_10", "")),
                "recall_at_100": str(metrics_row.get("recall_at_100", "")),
                "map": str(metrics_row.get("map", "")),
                "task_success_rate_pct": str(metrics_row.get("task_success_rate_pct", "")),
                "pri_only": str(meta.get("pri_only", "")),
                "langs": ",".join(meta.get("langs") or []),
                "size": str(meta.get("size", "")),
                "queries_path": str(queries_path),
                "qrels_path": str(qrels_path),
                "metrics_dir": str(metrics_dir),
                "tables_dir": str(tables_dir),
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, str]], append: bool) -> None:
    headers = [
        "run_recorded_at_utc",
        "config",
        "query_count",
        "qrels_count",
        "run_file",
        "avg_latency_ms",
        "precision_at_10",
        "recall_at_100",
        "map",
        "task_success_rate_pct",
        "pri_only",
        "langs",
        "size",
        "queries_path",
        "qrels_path",
        "metrics_dir",
        "tables_dir",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not append or not file_exists:
            w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append experiment metadata and key metrics to a run log CSV.")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--metrics-dir", required=True)
    parser.add_argument("--tables-dir", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    rows = _rows_for_runs(
        queries_path=Path(args.queries),
        qrels_path=Path(args.qrels),
        run_dir=Path(args.run_dir),
        metrics_dir=Path(args.metrics_dir),
        tables_dir=Path(args.tables_dir),
    )
    if not rows:
        raise SystemExit(f"No run_*.json files found in {args.run_dir}")

    out_csv = Path(args.out_csv)
    _write_csv(out_csv, rows, append=bool(args.append))
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
