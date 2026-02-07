from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ALLOWED_CATEGORIES = {
    "known_entity",
    "variant_orthography",
    "conceptual_thematic",
    "cross_textual_reuse",
    "metadata_poor",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def audit(queries_path: Path, qrels_path: Path) -> dict[str, Any]:
    queries_payload = _load_json(queries_path)
    qrels_payload = _load_json(qrels_path)

    query_rows = queries_payload.get("queries", [])
    qrel_rows = qrels_payload.get("qrels", [])

    queries_by_id: dict[str, dict[str, Any]] = {}
    dup_queries: list[str] = []
    invalid_categories: list[str] = []
    for q in query_rows:
        qid = str(q.get("id", "")).strip()
        if not qid:
            continue
        if qid in queries_by_id:
            dup_queries.append(qid)
        queries_by_id[qid] = q
        cat = str(q.get("category", "")).strip()
        if cat not in ALLOWED_CATEGORIES:
            invalid_categories.append(qid)

    qrels_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unknown_query_ids: set[str] = set()
    duplicate_judgments: set[str] = set()
    seen_judgments: set[tuple[str, str, str, str, int]] = set()
    missing_ids_rows: list[int] = []
    negative_relevance_rows: list[int] = []

    for i, row in enumerate(qrel_rows, start=1):
        qid = str(row.get("query_id", "")).strip()
        pid = str(row.get("passage_id", "")).strip()
        wid = str(row.get("work_id", "")).strip()
        aid = str(row.get("author_id", "")).strip()
        rel = int(row.get("relevance", 1))

        if qid not in queries_by_id:
            unknown_query_ids.add(qid)
        qrels_by_query[qid].append(row)

        if rel < 0:
            negative_relevance_rows.append(i)
        if not (pid or wid or aid):
            missing_ids_rows.append(i)

        key = (qid, pid, wid, aid, rel)
        if key in seen_judgments:
            duplicate_judgments.add(qid)
        seen_judgments.add(key)

    per_query_rows: list[dict[str, Any]] = []
    category_counts = Counter()
    for qid, q in sorted(queries_by_id.items()):
        cat = str(q.get("category", "uncategorized"))
        category_counts[cat] += 1

        judged = qrels_by_query.get(qid, [])
        relevant_count = sum(1 for r in judged if int(r.get("relevance", 1)) > 0)
        per_query_rows.append(
            {
                "query_id": qid,
                "category": cat,
                "query_text": str(q.get("text", "")),
                "qrels_rows": len(judged),
                "relevant_rows": relevant_count,
                "has_qrels": "yes" if judged else "no",
            }
        )

    missing_qrels = sorted(qid for qid in queries_by_id if qid not in qrels_by_query)
    categories_with_no_queries = sorted(cat for cat in ALLOWED_CATEGORIES if category_counts.get(cat, 0) == 0)

    return {
        "summary": {
            "queries_total": len(queries_by_id),
            "qrels_total": len(qrel_rows),
            "queries_missing_qrels": len(missing_qrels),
            "unknown_qrel_query_ids": len(unknown_query_ids),
            "duplicate_query_ids": len(set(dup_queries)),
            "duplicate_qrel_judgments": len(duplicate_judgments),
            "invalid_query_categories": len(invalid_categories),
            "qrel_rows_missing_all_ids": len(missing_ids_rows),
            "qrel_rows_negative_relevance": len(negative_relevance_rows),
        },
        "details": {
            "missing_qrels_query_ids": missing_qrels,
            "unknown_qrel_query_ids": sorted(unknown_query_ids),
            "duplicate_query_ids": sorted(set(dup_queries)),
            "duplicate_qrel_query_ids": sorted(duplicate_judgments),
            "invalid_category_query_ids": sorted(invalid_categories),
            "categories_with_no_queries": categories_with_no_queries,
            "qrel_rows_missing_all_ids": missing_ids_rows,
            "qrel_rows_negative_relevance": negative_relevance_rows,
        },
        "per_query": per_query_rows,
        "category_query_counts": dict(sorted(category_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit query and qrels completeness/consistency.")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = audit(Path(args.queries), Path(args.qrels))
    (out_dir / "qrels_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    per_query = report["per_query"]
    _write_csv(
        out_dir / "qrels_audit_per_query.csv",
        per_query,
        ["query_id", "category", "query_text", "qrels_rows", "relevant_rows", "has_qrels"],
    )

    summary_rows = [{"metric": k, "value": v} for k, v in report["summary"].items()]
    _write_csv(out_dir / "qrels_audit_summary.csv", summary_rows, ["metric", "value"])

    print(f"wrote {out_dir / 'qrels_audit.json'}")
    print(f"wrote {out_dir / 'qrels_audit_per_query.csv'}")
    print(f"wrote {out_dir / 'qrels_audit_summary.csv'}")


if __name__ == "__main__":
    main()
