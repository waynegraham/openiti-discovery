from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..clients.opensearch_client import get_opensearch
from ..settings import settings


AR_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670]")
TATWEEL_RE = re.compile(r"\u0640")
CHAR_MAP = str.maketrans(
    {
        "ٱ": "ا",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "ك": "ک",
        "ي": "ی",
    }
)


def normalize_arabic_script(s: str) -> str:
    s = TATWEEL_RE.sub("", s)
    s = AR_DIACRITICS_RE.sub("", s)
    s = s.translate(CHAR_MAP)
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class QueryItem:
    qid: str
    text: str
    category: str
    variants: tuple[str, ...]
    expansions: tuple[str, ...]


def _load_queries(path: Path) -> list[QueryItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("queries", [])
    out: list[QueryItem] = []
    for item in items:
        out.append(
            QueryItem(
                qid=str(item["id"]),
                text=str(item["text"]).strip(),
                category=str(item.get("category", "uncategorized")),
                variants=tuple(x.strip() for x in item.get("variants", []) if str(x).strip()),
                expansions=tuple(x.strip() for x in item.get("expansions", []) if str(x).strip()),
            )
        )
    return out


def _base_filters(pri_only: bool, langs: list[str] | None) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if pri_only:
        filters.append({"term": {"is_pri": True}})
    if langs:
        filters.append({"terms": {"lang": langs}})
    return filters


def _multi_match(query: str, fields: list[str]) -> dict[str, Any]:
    return {
        "multi_match": {
            "query": query,
            "type": "best_fields",
            "fields": fields,
            "operator": "or",
        }
    }


def _build_query(config: str, item: QueryItem, pri_only: bool, langs: list[str] | None, size: int) -> dict[str, Any]:
    raw = item.text
    norm = normalize_arabic_script(item.text)

    filters = _base_filters(pri_only=pri_only, langs=langs)

    if config == "baseline":
        must = [_multi_match(raw, ["title^2", "content.exact^4"])]
    elif config == "normalized":
        must = [_multi_match(norm or raw, ["title^2", "content.nostem^4", "content.exact^2"])]
    elif config == "variant_aware":
        variants = [normalize_arabic_script(v) for v in item.variants if v.strip()]
        should = [_multi_match(norm or raw, ["title^2", "content^4", "content.nostem^3", "content.persian^2", "content.exact^1"])]
        should.extend(_multi_match(v, ["content^3", "content.nostem^2", "content.persian^2"]) for v in variants if v)
        must = [{"bool": {"should": should, "minimum_should_match": 1}}]
    elif config == "full_pipeline":
        expansions = [normalize_arabic_script(x) for x in (*item.variants, *item.expansions) if x.strip()]
        should = [_multi_match(norm or raw, ["title^3", "content^5", "content.nostem^4", "content.persian^3", "content.exact^2"])]
        should.extend(_multi_match(ex, ["title^1", "content^3", "content.nostem^3", "content.persian^2"]) for ex in expansions if ex)
        must = [{"bool": {"should": should, "minimum_should_match": 1}}]
    else:
        raise ValueError(f"unsupported config: {config}")

    return {
        "size": size,
        "query": {
            "bool": {
                "filter": filters,
                "must": must,
            }
        },
        "_source": ["chunk_id", "work_id", "author_id", "version_id", "lang", "is_pri", "content", "title"],
    }


def run_config(
    *,
    config: str,
    queries: list[QueryItem],
    out_path: Path,
    size: int,
    pri_only: bool,
    langs: list[str] | None,
) -> None:
    client = get_opensearch()

    rows: list[dict[str, Any]] = []
    for item in queries:
        body = _build_query(config=config, item=item, pri_only=pri_only, langs=langs, size=size)

        t0 = time.perf_counter()
        res = client.search(index=settings.OPENSEARCH_INDEX_CHUNKS, body=body)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        hits = res.get("hits", {}).get("hits", [])
        for rank, hit in enumerate(hits, start=1):
            src = hit.get("_source") or {}
            rows.append(
                {
                    "query_id": item.qid,
                    "query_text": item.text,
                    "category": item.category,
                    "config": config,
                    "rank": rank,
                    "score": float(hit.get("_score") or 0.0),
                    "chunk_id": src.get("chunk_id") or hit.get("_id"),
                    "work_id": src.get("work_id"),
                    "author_id": src.get("author_id"),
                    "version_id": src.get("version_id"),
                    "elapsed_ms": elapsed_ms,
                }
            )

    payload = {
        "meta": {
            "config": config,
            "index": settings.OPENSEARCH_INDEX_CHUNKS,
            "size": size,
            "pri_only": pri_only,
            "langs": langs,
            "generated_at_epoch": time.time(),
        },
        "results": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval experiments for one or more configurations.")
    parser.add_argument("--queries", required=True, help="Path to queries JSON file")
    parser.add_argument("--output-dir", required=True, help="Directory for run outputs")
    parser.add_argument(
        "--configs",
        default="baseline,normalized,variant_aware,full_pipeline",
        help="Comma-separated configs",
    )
    parser.add_argument("--size", type=int, default=100, help="Top-k results per query")
    parser.add_argument("--pri-only", action="store_true", help="Apply is_pri filter")
    parser.add_argument("--langs", default="ara", help="Comma-separated language filters")

    args = parser.parse_args()

    queries = _load_queries(Path(args.queries))
    if not queries:
        raise SystemExit("No queries found.")

    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    configs = [x.strip() for x in args.configs.split(",") if x.strip()]

    out_dir = Path(args.output_dir)
    for config in configs:
        out_path = out_dir / f"run_{config}.json"
        run_config(
            config=config,
            queries=queries,
            out_path=out_path,
            size=args.size,
            pri_only=bool(args.pri_only),
            langs=langs or None,
        )
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
