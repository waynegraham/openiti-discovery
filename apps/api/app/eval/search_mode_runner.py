from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .. import main as api_main


@dataclass(frozen=True)
class QueryItem:
    qid: str
    text: str
    category: str


def _load_queries(path: Path) -> list[QueryItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[QueryItem] = []
    for row in payload.get("queries", []):
        qid = str(row.get("id", "")).strip()
        text = str(row.get("text", "")).strip()
        if not qid or not text:
            continue
        out.append(
            QueryItem(
                qid=qid,
                text=text,
                category=str(row.get("category", "uncategorized")),
            )
        )
    return out


def _write_run(
    *,
    out_path: Path,
    config: str,
    size: int,
    pri_only: bool,
    langs: list[str] | None,
    rows: list[dict[str, Any]],
    query_latencies_ms: list[float],
    effective_mode_counts: dict[str, int],
    warnings: list[str],
    page_size: int,
) -> None:
    payload = {
        "meta": {
            "config": config,
            "size": size,
            "page_size": page_size,
            "pri_only": pri_only,
            "langs": langs,
            "generated_at_epoch": time.time(),
            "query_latencies_ms": query_latencies_ms,
            "effective_mode_counts": effective_mode_counts,
            "warnings_seen": sorted(set(warnings)),
        },
        "results": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_mode(
    *,
    client: TestClient,
    queries: list[QueryItem],
    mode: str,
    config_name: str,
    out_path: Path,
    size: int,
    page_size: int,
    pri_only: bool,
    langs: list[str] | None,
    candidate_k_override: int | None,
    rrf_k_override: int | None,
) -> None:
    original_candidate_k = api_main._candidate_k
    original_rrf_k = api_main._rrf_k

    if candidate_k_override is not None:
        api_main._candidate_k = lambda page, req_size: int(candidate_k_override)
    if rrf_k_override is not None:
        api_main._rrf_k = lambda: int(rrf_k_override)

    rows: list[dict[str, Any]] = []
    query_latencies_ms: list[float] = []
    effective_mode_counts: dict[str, int] = {}
    seen_warnings: list[str] = []

    try:
        for item in queries:
            params: dict[str, Any] = {
                "q": item.text,
                "mode": mode,
                "size": page_size,
                "page": 1,
                "pri_only": str(pri_only).lower(),
            }
            if langs:
                params["langs"] = ",".join(langs)

            res = None
            elapsed_ms = 0.0
            last_exc: Exception | None = None
            for attempt in range(1, 5):
                try:
                    t0 = time.perf_counter()
                    res = client.get("/search", params=params)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    if res.status_code == 200:
                        break
                    if res.status_code in (429, 502, 503, 504) and attempt < 4:
                        time.sleep(float(attempt))
                        continue
                    body_preview = (res.text or "").strip().replace("\n", " ")
                    if len(body_preview) > 300:
                        body_preview = body_preview[:300] + "..."
                    raise SystemExit(
                        f"{config_name}: /search returned HTTP {res.status_code} for query {item.qid}; body={body_preview}"
                    )
                except Exception as exc:
                    last_exc = exc
                    if attempt >= 4:
                        raise SystemExit(
                            f"{config_name}: /search request failed for query {item.qid}: {type(exc).__name__}: {exc}"
                        )
                    time.sleep(float(attempt))

            if res is None:
                if last_exc is not None:
                    raise SystemExit(
                        f"{config_name}: /search request failed for query {item.qid}: {type(last_exc).__name__}: {last_exc}"
                    )
                raise SystemExit(f"{config_name}: /search did not return a response for query {item.qid}")

            query_latencies_ms.append(elapsed_ms)

            body = res.json()
            effective_mode = str(body.get("effective_mode") or "unknown")
            effective_mode_counts[effective_mode] = effective_mode_counts.get(effective_mode, 0) + 1
            for warning in body.get("warnings") or []:
                seen_warnings.append(str(warning))

            for rank, hit in enumerate(body.get("results", []), start=1):
                source = hit.get("source") or {}
                rows.append(
                    {
                        "query_id": item.qid,
                        "query_text": item.text,
                        "category": item.category,
                        "config": config_name,
                        "rank": rank,
                        "score": float(hit.get("score") or 0.0),
                        "chunk_id": hit.get("chunk_id") or source.get("chunk_id"),
                        "work_id": source.get("work_id"),
                        "author_id": source.get("author_id"),
                        "version_id": source.get("version_id"),
                        "elapsed_ms": elapsed_ms,
                    }
                )
    finally:
        api_main._candidate_k = original_candidate_k
        api_main._rrf_k = original_rrf_k

    _write_run(
        out_path=out_path,
        config=config_name,
        size=size,
        pri_only=pri_only,
        langs=langs,
        rows=rows,
        query_latencies_ms=query_latencies_ms,
        effective_mode_counts=effective_mode_counts,
        warnings=seen_warnings,
        page_size=page_size,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run API search mode experiments via in-process FastAPI client.")
    parser.add_argument("--queries", required=True, help="Path to queries JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for run_*.json outputs")
    parser.add_argument("--modes", default="bm25,vector,hybrid", help="Comma-separated modes")
    parser.add_argument("--size", type=int, default=100, help="Top-k cutoff used by evaluator")
    parser.add_argument("--page-size", type=int, default=20, help="Search page size sent to API")
    parser.add_argument("--pri-only", action="store_true", help="Apply pri_only filter")
    parser.add_argument("--langs", default="ar", help="Comma-separated language filters")
    parser.add_argument("--config-prefix", default="mode", help="Prefix for config labels")
    parser.add_argument("--candidate-k", type=int, default=None, help="Optional fixed candidate_k override")
    parser.add_argument("--rrf-k", type=int, default=None, help="Optional rrf_k override")
    args = parser.parse_args()

    queries = _load_queries(Path(args.queries))
    if not queries:
        raise SystemExit("No valid queries found in queries file")

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]

    out_dir = Path(args.output_dir)
    client = TestClient(api_main.app)
    for mode in modes:
        config_name = f"{args.config_prefix}_{mode}"
        out_path = out_dir / f"run_{config_name}.json"
        run_mode(
            client=client,
            queries=queries,
            mode=mode,
            config_name=config_name,
            out_path=out_path,
            size=args.size,
            page_size=args.page_size,
            pri_only=bool(args.pri_only),
            langs=langs or None,
            candidate_k_override=args.candidate_k,
            rrf_k_override=args.rrf_k,
        )
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
