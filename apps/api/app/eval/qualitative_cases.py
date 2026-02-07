from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_run(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing run file: {path}")
    payload = _load_json(path)
    return payload.get("results", [])


def _load_qrels(path: Path) -> dict[str, dict[str, set[str]]]:
    payload = _load_json(path)
    out: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"passage": set(), "work": set(), "author": set()})
    for row in payload.get("qrels", []):
        qid = str(row.get("query_id", ""))
        if row.get("passage_id"):
            out[qid]["passage"].add(str(row["passage_id"]))
        if row.get("work_id"):
            out[qid]["work"].add(str(row["work_id"]))
        if row.get("author_id"):
            out[qid]["author"].add(str(row["author_id"]))
    return out


def _by_query(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[str(row.get("query_id", ""))].append(row)
    for qid in out:
        out[qid].sort(key=lambda r: int(r.get("rank", 10_000)))
    return out


def _ranked_ids(rows: list[dict[str, Any]], key: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        val = str(row.get(key, "")).strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _first_hit_rank(ranked: list[str], relevant: set[str]) -> int | None:
    for i, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            return i
    return None


def _hit_count_at_k(ranked: list[str], relevant: set[str], k: int) -> int:
    return sum(1 for doc_id in ranked[:k] if doc_id in relevant)


def _sample_ids(ranked: list[str], n: int) -> str:
    return "|".join(ranked[:n])


def _key_for_granularity(granularity: str) -> str:
    return {
        "passage": "chunk_id",
        "work": "work_id",
        "author": "author_id",
    }[granularity]


def build_cases(
    *,
    baseline_rows: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    qrels: dict[str, dict[str, set[str]]],
    granularity: str,
    top_k: int,
) -> list[dict[str, Any]]:
    key = _key_for_granularity(granularity)
    base_by_q = _by_query(baseline_rows)
    full_by_q = _by_query(full_rows)
    qids = sorted(set(base_by_q.keys()) | set(full_by_q.keys()))

    cases: list[dict[str, Any]] = []
    for qid in qids:
        base_rows_q = base_by_q.get(qid, [])
        full_rows_q = full_by_q.get(qid, [])
        if not base_rows_q and not full_rows_q:
            continue

        relevant = qrels.get(qid, {}).get(granularity, set())
        if not relevant:
            continue

        base_ranked = _ranked_ids(base_rows_q, key)
        full_ranked = _ranked_ids(full_rows_q, key)
        base_hits = _hit_count_at_k(base_ranked, relevant, top_k)
        full_hits = _hit_count_at_k(full_ranked, relevant, top_k)
        base_first = _first_hit_rank(base_ranked, relevant)
        full_first = _first_hit_rank(full_ranked, relevant)

        if full_hits > base_hits:
            case_type = "improved"
        elif full_hits < base_hits:
            case_type = "regressed"
        else:
            case_type = "parity"

        category = str((full_rows_q or base_rows_q)[0].get("category", "uncategorized"))
        query_text = str((full_rows_q or base_rows_q)[0].get("query_text", ""))

        cases.append(
            {
                "query_id": qid,
                "category": category,
                "query_text": query_text,
                "case_type": case_type,
                f"baseline_rel_hits_at_{top_k}": base_hits,
                f"full_pipeline_rel_hits_at_{top_k}": full_hits,
                "baseline_first_rel_rank": base_first if base_first is not None else "",
                "full_pipeline_first_rel_rank": full_first if full_first is not None else "",
                "baseline_top_ids": _sample_ids(base_ranked, 5),
                "full_pipeline_top_ids": _sample_ids(full_ranked, 5),
                "notes": "",
            }
        )
    return cases


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        headers = [
            "query_id",
            "category",
            "query_text",
            "case_type",
            "baseline_rel_hits_at_10",
            "full_pipeline_rel_hits_at_10",
            "baseline_first_rel_rank",
            "full_pipeline_first_rel_rank",
            "baseline_top_ids",
            "full_pipeline_top_ids",
            "notes",
        ]
    else:
        headers = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build qualitative comparison cases from baseline vs full pipeline runs.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--baseline-config", default="baseline")
    parser.add_argument("--full-config", default="full_pipeline")
    parser.add_argument("--granularity", choices=["passage", "work", "author"], default="passage")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    baseline = _load_run(run_dir / f"run_{args.baseline_config}.json")
    full = _load_run(run_dir / f"run_{args.full_config}.json")
    qrels = _load_qrels(Path(args.qrels))

    cases = build_cases(
        baseline_rows=baseline,
        full_rows=full,
        qrels=qrels,
        granularity=args.granularity,
        top_k=args.top_k,
    )
    _write_csv(Path(args.out_csv), cases)
    print(f"wrote {args.out_csv}")
    print(f"cases={len(cases)}")


if __name__ == "__main__":
    main()
