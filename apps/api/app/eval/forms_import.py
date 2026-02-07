from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ALLOWED_CATEGORIES = {
    "known_entity",
    "variant_orthography",
    "conceptual_thematic",
    "cross_textual_reuse",
    "metadata_poor",
}


def _split_pipe(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_queries(path: Path, strict: bool) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for i, row in enumerate(rows, start=2):
        query_id = str(row.get("query_id", "")).strip()
        category = str(row.get("category", "")).strip()
        query_text = str(row.get("query_text", "")).strip()
        variants = _split_pipe(str(row.get("variants_pipe", "")))
        expansions = _split_pipe(str(row.get("expansions_pipe", "")))

        if not query_id:
            if strict:
                raise SystemExit(f"{path}:{i}: missing query_id")
            continue
        if query_id in seen_ids:
            raise SystemExit(f"{path}:{i}: duplicate query_id '{query_id}'")
        seen_ids.add(query_id)

        if not query_text:
            if strict:
                raise SystemExit(f"{path}:{i}: missing query_text for '{query_id}'")
            continue

        if category not in ALLOWED_CATEGORIES:
            raise SystemExit(
                f"{path}:{i}: invalid category '{category}' for '{query_id}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_CATEGORIES))}"
            )

        out.append(
            {
                "id": query_id,
                "category": category,
                "text": query_text,
                "variants": variants,
                "expansions": expansions,
            }
        )
    return out


def _load_qrels(path: Path, valid_query_ids: set[str], strict: bool) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []

    for i, row in enumerate(rows, start=2):
        query_id = str(row.get("query_id", "")).strip()
        passage_id = str(row.get("passage_id", "")).strip()
        work_id = str(row.get("work_id", "")).strip()
        author_id = str(row.get("author_id", "")).strip()
        relevance_raw = str(row.get("relevance", "")).strip()

        if not query_id:
            if strict:
                raise SystemExit(f"{path}:{i}: missing query_id")
            continue
        if query_id not in valid_query_ids:
            raise SystemExit(f"{path}:{i}: query_id '{query_id}' not found in query form")

        if strict and not (passage_id or work_id or author_id):
            raise SystemExit(f"{path}:{i}: missing all of passage_id/work_id/author_id for '{query_id}'")
        if not (passage_id or work_id or author_id):
            continue

        if relevance_raw == "":
            relevance = 1
        else:
            try:
                relevance = int(relevance_raw)
            except ValueError as exc:
                raise SystemExit(f"{path}:{i}: invalid relevance '{relevance_raw}'") from exc

        qrel: dict[str, Any] = {
            "query_id": query_id,
            "relevance": relevance,
        }
        if passage_id:
            qrel["passage_id"] = passage_id
        if work_id:
            qrel["work_id"] = work_id
        if author_id:
            qrel["author_id"] = author_id

        out.append(qrel)

    return out


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert expert CSV forms into eval JSON files.")
    parser.add_argument("--queries-csv", required=True)
    parser.add_argument("--qrels-csv", required=True)
    parser.add_argument("--out-queries", required=True)
    parser.add_argument("--out-qrels", required=True)
    parser.add_argument("--strict", action="store_true", help="Fail on missing required values")
    args = parser.parse_args()

    queries = _load_queries(Path(args.queries_csv), strict=bool(args.strict))
    if not queries:
        raise SystemExit("No valid queries found in query CSV")
    query_ids = {q["id"] for q in queries}

    qrels = _load_qrels(Path(args.qrels_csv), valid_query_ids=query_ids, strict=bool(args.strict))
    if not qrels:
        raise SystemExit("No valid qrels found in qrels CSV")

    queries_payload = {"queries": queries}
    qrels_payload = {"qrels": qrels}
    _write_json(Path(args.out_queries), queries_payload)
    _write_json(Path(args.out_qrels), qrels_payload)

    print(f"wrote {args.out_queries}")
    print(f"wrote {args.out_qrels}")
    print(f"imported queries={len(queries)} qrels={len(qrels)}")


if __name__ == "__main__":
    main()
