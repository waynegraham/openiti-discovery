from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CATEGORY_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "known_entity": [
        {
            "text": "الشافعي",
            "variants": ["الشافعى", "محمد بن ادريس الشافعي"],
            "expansions": ["محمد بن إدريس الشافعي", "الإمام الشافعي"],
        },
        {
            "text": "الطبري",
            "variants": ["الطبرى"],
            "expansions": ["محمد بن جرير الطبري"],
        },
        {
            "text": "إحياء علوم الدين",
            "variants": ["احياء علوم الدين"],
            "expansions": ["الغزالي"],
        },
    ],
    "variant_orthography": [
        {
            "text": "مساله",
            "variants": ["مسألة", "مساله"],
            "expansions": ["مسائل الفقه"],
        },
        {
            "text": "مسووليه",
            "variants": ["مسؤولية", "مسوولية"],
            "expansions": ["التكليف"],
        },
        {
            "text": "قضاء",
            "variants": ["قضا", "قضاء"],
            "expansions": ["القضاء والقدر"],
        },
    ],
    "conceptual_thematic": [
        {
            "text": "اداب العالم والمتعلم",
            "variants": [],
            "expansions": ["تعليم", "آداب"],
        },
        {
            "text": "العدل في الحكم",
            "variants": [],
            "expansions": ["السياسة الشرعية", "الانصاف"],
        },
        {
            "text": "الزهد والتقشف",
            "variants": [],
            "expansions": ["الورع", "الاخلاق"],
        },
    ],
    "cross_textual_reuse": [
        {
            "text": "اطلبوا العلم ولو بالصين",
            "variants": [],
            "expansions": ["طلب العلم"],
        },
        {
            "text": "من جد وجد",
            "variants": [],
            "expansions": ["الحث على الاجتهاد"],
        },
        {
            "text": "الدين النصيحة",
            "variants": [],
            "expansions": ["النصيحة"],
        },
    ],
    "metadata_poor": [
        {
            "text": "البيعة والشرعية",
            "variants": [],
            "expansions": ["الخلافة", "السلطة"],
        },
        {
            "text": "أحكام السوق",
            "variants": [],
            "expansions": ["الحسبة", "المعاملات"],
        },
        {
            "text": "تدبير المدينة",
            "variants": [],
            "expansions": ["السلطة", "الإمامة"],
        },
    ],
}


def _build_queries(per_category: int) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    i = 1
    for category, templates in CATEGORY_TEMPLATES.items():
        for n in range(per_category):
            t = templates[n % len(templates)]
            queries.append(
                {
                    "id": f"Q{i:03d}",
                    "category": category,
                    "text": t["text"],
                    "variants": t.get("variants", []),
                    "expansions": t.get("expansions", []),
                    "placeholder": True,
                }
            )
            i += 1
    return queries


def _build_placeholder_qrels(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for q in queries:
        qid = str(q["id"])
        rows.append(
            {
                "query_id": qid,
                "passage_id": f"TODO_CHUNK_{qid}",
                "work_id": f"TODO_WORK_{qid}",
                "author_id": f"TODO_AUTHOR_{qid}",
                "relevance": 1,
                "placeholder": True,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate placeholder queries/qrels for paper evaluation workflow.")
    parser.add_argument("--out-queries", required=True, help="Destination queries JSON path")
    parser.add_argument("--out-qrels", required=True, help="Destination qrels JSON path")
    parser.add_argument("--per-category", type=int, default=4, help="Number of generated queries per category")
    args = parser.parse_args()

    if args.per_category <= 0:
        raise SystemExit("--per-category must be > 0")

    queries = _build_queries(args.per_category)
    qrels = _build_placeholder_qrels(queries)

    queries_path = Path(args.out_queries)
    qrels_path = Path(args.out_qrels)
    queries_path.parent.mkdir(parents=True, exist_ok=True)
    qrels_path.parent.mkdir(parents=True, exist_ok=True)

    queries_payload = {
        "meta": {
            "note": "Placeholder queries generated for pipeline testing before expert validation.",
            "categories": list(CATEGORY_TEMPLATES.keys()),
            "per_category": args.per_category,
            "total_queries": len(queries),
        },
        "queries": queries,
    }
    qrels_payload = {
        "meta": {
            "note": "Placeholder qrels. Replace TODO_* IDs with judged IDs from domain experts.",
            "total_rows": len(qrels),
        },
        "qrels": qrels,
    }

    queries_path.write_text(json.dumps(queries_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    qrels_path.write_text(json.dumps(qrels_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {queries_path}")
    print(f"wrote {qrels_path}")


if __name__ == "__main__":
    main()
