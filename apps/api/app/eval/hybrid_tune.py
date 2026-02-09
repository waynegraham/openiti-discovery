from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .. import main as api_main
from .metrics import _load_qrels, evaluate_run
from .search_mode_runner import _load_queries, run_mode


def _float_fmt(value: float) -> str:
    return f"{value:.4f}"


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_run_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("results", [])


def _metrics_for_run(
    *,
    run_rows: list[dict[str, Any]],
    qrels: dict[str, dict[str, set[str]]],
    p_at: int,
    recall_at: int,
    success_at: int,
) -> dict[str, float]:
    overall, _ = evaluate_run(
        run_rows=run_rows,
        qrels=qrels,
        granularity="passage",
        p_at=p_at,
        recall_at=recall_at,
        success_at=success_at,
    )
    return {
        f"precision_at_{p_at}": overall["p_at_k"],
        f"recall_at_{recall_at}": overall["recall_at_k"],
        "map": overall["map"],
        "task_success_rate_pct": overall["task_success"] * 100.0,
    }


def _read_baseline_row(path: Path, config: str) -> dict[str, float]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("retrieval_configuration")) != config:
                continue
            return {
                "precision_at_10": float(row.get("precision_at_10", 0.0) or 0.0),
                "recall_at_100": float(row.get("recall_at_100", 0.0) or 0.0),
                "map": float(row.get("map", 0.0) or 0.0),
                "task_success_rate_pct": float(row.get("task_success_rate_pct", 0.0) or 0.0),
            }
    raise SystemExit(f"Missing baseline config '{config}' in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 8 hybrid tuning sweep with no-regression selection.")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--run-dir", required=True, help="Directory for intermediate run_*.json artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for tuning outputs")
    parser.add_argument("--baseline-table-x", required=True, help="CSV with baseline metrics")
    parser.add_argument("--baseline-config", default="full_pipeline")
    parser.add_argument("--candidate-k-grid", default="100,200,400", help="Comma-separated candidate_k values")
    parser.add_argument("--rrf-k-grid", default="30,60,90", help="Comma-separated rrf_k values")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--pri-only", action="store_true")
    parser.add_argument("--langs", default="ar")
    parser.add_argument("--subset-manifest", default="", help="Recorded in decision artifact for traceability")
    parser.add_argument("--p-at", type=int, default=10)
    parser.add_argument("--recall-at", type=int, default=100)
    parser.add_argument("--success-at", type=int, default=10)
    args = parser.parse_args()

    queries = _load_queries(Path(args.queries))
    if not queries:
        raise SystemExit("No valid queries available for hybrid tuning")
    qrels = _load_qrels(Path(args.qrels))
    baseline = _read_baseline_row(Path(args.baseline_table_x), args.baseline_config)

    candidate_grid = [int(x.strip()) for x in args.candidate_k_grid.split(",") if x.strip()]
    rrf_grid = [int(x.strip()) for x in args.rrf_k_grid.split(",") if x.strip()]
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]

    client = TestClient(api_main.app)
    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for candidate_k in candidate_grid:
        for rrf_k in rrf_grid:
            config_name = f"hybrid_ck{candidate_k}_rrf{rrf_k}"
            out_path = run_dir / f"run_{config_name}.json"
            run_mode(
                client=client,
                queries=queries,
                mode="hybrid",
                config_name=config_name,
                out_path=out_path,
                size=args.page_size,
                page_size=args.page_size,
                pri_only=bool(args.pri_only),
                langs=langs or None,
                candidate_k_override=candidate_k,
                rrf_k_override=rrf_k,
            )
            metrics = _metrics_for_run(
                run_rows=_read_run_rows(out_path),
                qrels=qrels,
                p_at=args.p_at,
                recall_at=args.recall_at,
                success_at=args.success_at,
            )
            regressions = [
                metric_name
                for metric_name in ("precision_at_10", "recall_at_100", "map", "task_success_rate_pct")
                if metrics[metric_name] < baseline[metric_name]
            ]
            results.append(
                {
                    "config": config_name,
                    "candidate_k": candidate_k,
                    "rrf_k": rrf_k,
                    "precision_at_10": _float_fmt(metrics["precision_at_10"]),
                    "recall_at_100": _float_fmt(metrics["recall_at_100"]),
                    "map": _float_fmt(metrics["map"]),
                    "task_success_rate_pct": _float_fmt(metrics["task_success_rate_pct"]),
                    "passes_no_regression": "true" if not regressions else "false",
                    "regressed_metrics": ",".join(regressions),
                }
            )

    passing = [r for r in results if r["passes_no_regression"] == "true"]
    if not passing:
        raise SystemExit("No hybrid tuning candidate passed no-regression gate against baseline")

    best = sorted(
        passing,
        key=lambda r: (
            float(r["map"]),
            float(r["task_success_rate_pct"]),
            float(r["recall_at_100"]),
            float(r["precision_at_10"]),
        ),
        reverse=True,
    )[0]

    matrix_csv = out_dir / "milestone8_hybrid_matrix.csv"
    _write_csv(
        matrix_csv,
        results,
        [
            "config",
            "candidate_k",
            "rrf_k",
            "precision_at_10",
            "recall_at_100",
            "map",
            "task_success_rate_pct",
            "passes_no_regression",
            "regressed_metrics",
        ],
    )

    decision_path = out_dir / "milestone8_hybrid_decision.md"
    decision_path.write_text(
        "\n".join(
            [
                "# Milestone 8 Hybrid Tuning Decision",
                "",
                f"- Baseline config: `{args.baseline_config}`",
                f"- Baseline table: `{args.baseline_table_x}`",
                f"- Baseline metrics: `{json.dumps(baseline, ensure_ascii=False)}`",
                f"- Candidate grid: `candidate_k={candidate_grid}`, `rrf_k={rrf_grid}`",
                f"- Representative subset manifest: `{args.subset_manifest or 'not_provided'}`",
                "",
                "## Selected Configuration",
                f"- Config: `{best['config']}`",
                f"- candidate_k: `{best['candidate_k']}`",
                f"- rrf_k: `{best['rrf_k']}`",
                f"- precision@10: `{best['precision_at_10']}`",
                f"- recall@100: `{best['recall_at_100']}`",
                f"- MAP: `{best['map']}`",
                f"- task_success_rate_pct: `{best['task_success_rate_pct']}`",
                "",
                "Rationale: highest MAP among no-regression candidates, with task success and recall as tie-breakers.",
                "",
                f"Full matrix: `{matrix_csv}`",
            ]
        ),
        encoding="utf-8",
    )

    selected_json = out_dir / "milestone8_selected_hybrid.json"
    selected_json.write_text(
        json.dumps(
            {
                "config": best["config"],
                "candidate_k": int(best["candidate_k"]),
                "rrf_k": int(best["rrf_k"]),
                "precision_at_10": float(best["precision_at_10"]),
                "recall_at_100": float(best["recall_at_100"]),
                "map": float(best["map"]),
                "task_success_rate_pct": float(best["task_success_rate_pct"]),
                "baseline_config": args.baseline_config,
                "baseline_metrics": baseline,
                "subset_manifest": args.subset_manifest or "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"wrote {matrix_csv}")
    print(f"wrote {decision_path}")
    print(f"wrote {selected_json}")


if __name__ == "__main__":
    main()
