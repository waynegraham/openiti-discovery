from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_run(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("meta", {}).get("config", "unknown")), payload.get("results", [])


def _load_qrels(path: Path) -> dict[str, dict[str, set[str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rel_by_q: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"passage": set(), "work": set(), "author": set()})

    for row in payload.get("qrels", []):
        qid = str(row["query_id"])
        if row.get("passage_id"):
            rel_by_q[qid]["passage"].add(str(row["passage_id"]))
        if row.get("work_id"):
            rel_by_q[qid]["work"].add(str(row["work_id"]))
        if row.get("author_id"):
            rel_by_q[qid]["author"].add(str(row["author_id"]))

    return rel_by_q


def _rankings(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_q[str(row["query_id"])].append(row)
    for qid in by_q:
        by_q[qid].sort(key=lambda r: int(r["rank"]))
    return by_q


def _dedup_ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        val = row.get(key)
        if not val:
            continue
        sval = str(val)
        if sval in seen:
            continue
        seen.add(sval)
        out.append(sval)
    return out


def _average_precision(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for i, doc_id in enumerate(ranked_ids[:k], start=1):
        if doc_id in relevant:
            hits += 1
            sum_prec += hits / i
    return sum_prec / len(relevant)


def _score_query(ranked_ids: list[str], relevant: set[str], p_at: int, recall_at: int, success_at: int) -> dict[str, float]:
    if not relevant:
        return {
            "p_at_k": 0.0,
            "recall_at_k": 0.0,
            "ap": 0.0,
            "task_success": 0.0,
        }

    top_p = ranked_ids[:p_at]
    top_r = ranked_ids[:recall_at]
    top_s = ranked_ids[:success_at]

    p_hits = sum(1 for x in top_p if x in relevant)
    r_hits = sum(1 for x in top_r if x in relevant)
    success = any(x in relevant for x in top_s)

    return {
        "p_at_k": p_hits / float(p_at),
        "recall_at_k": r_hits / float(len(relevant)),
        "ap": _average_precision(ranked_ids, relevant, k=max(recall_at, p_at, success_at)),
        "task_success": 1.0 if success else 0.0,
    }


def _aggregate(query_scores: list[dict[str, float]]) -> dict[str, float]:
    if not query_scores:
        return {"p_at_k": 0.0, "recall_at_k": 0.0, "map": 0.0, "task_success": 0.0}

    n = len(query_scores)
    return {
        "p_at_k": sum(x["p_at_k"] for x in query_scores) / n,
        "recall_at_k": sum(x["recall_at_k"] for x in query_scores) / n,
        "map": sum(x["ap"] for x in query_scores) / n,
        "task_success": sum(x["task_success"] for x in query_scores) / n,
    }


def evaluate_run(
    *,
    run_rows: list[dict[str, Any]],
    qrels: dict[str, dict[str, set[str]]],
    granularity: str,
    p_at: int,
    recall_at: int,
    success_at: int,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    by_q = _rankings(run_rows)
    by_cat: dict[str, list[dict[str, float]]] = defaultdict(list)
    all_scores: list[dict[str, float]] = []

    key_map = {"passage": "chunk_id", "work": "work_id", "author": "author_id"}
    rank_key = key_map[granularity]

    for qid, rows in by_q.items():
        relevant = qrels.get(qid, {}).get(granularity, set())
        if not relevant:
            # Skip unjudged queries so partial qrels do not artificially deflate scores.
            continue
        ranked_ids = _dedup_ids(rows, rank_key)
        s = _score_query(ranked_ids, relevant, p_at=p_at, recall_at=recall_at, success_at=success_at)
        all_scores.append(s)
        category = str(rows[0].get("category", "uncategorized")) if rows else "uncategorized"
        by_cat[category].append(s)

    per_cat = {cat: _aggregate(scores) for cat, scores in by_cat.items()}
    return _aggregate(all_scores), per_cat


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _load_runs(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for p in sorted(run_dir.glob("run_*.json")):
        config, rows = _load_run(p)
        out[config] = rows
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute retrieval metrics from run outputs + qrels.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--p-at", type=int, default=10)
    parser.add_argument("--recall-at", type=int, default=100)
    parser.add_argument("--success-at", type=int, default=10)
    args = parser.parse_args()

    qrels = _load_qrels(Path(args.qrels))
    runs = _load_runs(Path(args.run_dir))
    if not runs:
        raise SystemExit("No run_*.json files found")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    granularity_rows: list[dict[str, Any]] = []

    for config, rows in runs.items():
        overall, per_cat = evaluate_run(
            run_rows=rows,
            qrels=qrels,
            granularity="passage",
            p_at=args.p_at,
            recall_at=args.recall_at,
            success_at=args.success_at,
        )
        summary_rows.append(
            {
                "retrieval_configuration": config,
                f"precision_at_{args.p_at}": _fmt(overall["p_at_k"]),
                f"recall_at_{args.recall_at}": _fmt(overall["recall_at_k"]),
                "map": _fmt(overall["map"]),
                "task_success_rate_pct": _fmt(overall["task_success"] * 100.0),
            }
        )

        for category, scores in sorted(per_cat.items()):
            category_rows.append(
                {
                    "retrieval_configuration": config,
                    "category": category,
                    f"precision_at_{args.p_at}": _fmt(scores["p_at_k"]),
                    f"recall_at_{args.recall_at}": _fmt(scores["recall_at_k"]),
                    "map": _fmt(scores["map"]),
                    "task_success_rate_pct": _fmt(scores["task_success"] * 100.0),
                }
            )

    full_rows = runs.get("full_pipeline", next(iter(runs.values())))
    for granularity in ("passage", "work", "author"):
        overall, _ = evaluate_run(
            run_rows=full_rows,
            qrels=qrels,
            granularity=granularity,
            p_at=args.p_at,
            recall_at=args.recall_at,
            success_at=args.success_at,
        )
        granularity_rows.append(
            {
                "granularity_level": f"{granularity}-level",
                f"precision_at_{args.p_at}": _fmt(overall["p_at_k"]),
                f"recall_at_{args.recall_at}": _fmt(overall["recall_at_k"]),
                "map": _fmt(overall["map"]),
            }
        )

    _write_csv(
        out_dir / "table_x_retrieval_performance.csv",
        summary_rows,
        [
            "retrieval_configuration",
            f"precision_at_{args.p_at}",
            f"recall_at_{args.recall_at}",
            "map",
            "task_success_rate_pct",
        ],
    )
    _write_csv(
        out_dir / "category_breakdown.csv",
        category_rows,
        [
            "retrieval_configuration",
            "category",
            f"precision_at_{args.p_at}",
            f"recall_at_{args.recall_at}",
            "map",
            "task_success_rate_pct",
        ],
    )
    _write_csv(
        out_dir / "table_y_granularity.csv",
        granularity_rows,
        [
            "granularity_level",
            f"precision_at_{args.p_at}",
            f"recall_at_{args.recall_at}",
            "map",
        ],
    )

    print(f"wrote {out_dir / 'table_x_retrieval_performance.csv'}")
    print(f"wrote {out_dir / 'category_breakdown.csv'}")
    print(f"wrote {out_dir / 'table_y_granularity.csv'}")


if __name__ == "__main__":
    main()
