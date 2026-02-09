from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .. import main as api_main


def _assert_search_ok(
    client: TestClient,
    *,
    mode: str,
    query: str,
    size: int,
    page: int,
    langs: str,
    expect_effective_mode: str | None = None,
    expect_warning: str | None = None,
) -> dict[str, Any]:
    res = client.get(
        "/search",
        params={
            "q": query,
            "mode": mode,
            "size": size,
            "page": page,
            "langs": langs,
            "pri_only": "true",
        },
    )
    if res.status_code != 200:
        raise SystemExit(f"/search mode={mode} returned HTTP {res.status_code}")
    body = res.json()
    if expect_effective_mode and body.get("effective_mode") != expect_effective_mode:
        raise SystemExit(
            f"/search mode={mode} expected effective_mode={expect_effective_mode}, got {body.get('effective_mode')}"
        )
    if expect_warning:
        warnings = [str(x) for x in (body.get("warnings") or [])]
        if expect_warning not in warnings:
            raise SystemExit(f"/search mode={mode} missing warning {expect_warning}")
    if mode == "bm25":
        facets = body.get("facets")
        if not isinstance(facets, dict):
            raise SystemExit("bm25 response missing facets object")
    return body


def _check_reading_routes(client: TestClient, search_body: dict[str, Any]) -> None:
    results = search_body.get("results") or []
    if not results:
        return

    first = results[0]
    chunk_id = str(first.get("chunk_id") or "")
    source = first.get("source") or {}
    work_id = str(source.get("work_id") or "")
    if chunk_id:
        c_res = client.get(f"/chunks/{chunk_id}")
        if c_res.status_code not in (200, 404):
            raise SystemExit(f"/chunks/{chunk_id} returned HTTP {c_res.status_code}")
    if work_id:
        w_res = client.get(f"/works/{work_id}")
        if w_res.status_code not in (200, 404):
            raise SystemExit(f"/works/{work_id} returned HTTP {w_res.status_code}")
        v_res = client.get(f"/works/{work_id}/versions")
        if v_res.status_code not in (200, 404):
            raise SystemExit(f"/works/{work_id}/versions returned HTTP {v_res.status_code}")
        if v_res.status_code == 200:
            versions = v_res.json() or []
            if versions:
                version_id = versions[0].get("version_id")
                chunk_index = first.get("source", {}).get("chunk_index", 0)
                r_res = client.get(
                    f"/works/{work_id}/versions/{version_id}/chunks/resolve",
                    params={"target_chunk_index": chunk_index if isinstance(chunk_index, int) else 0},
                )
                if r_res.status_code not in (200, 404):
                    raise SystemExit(
                        f"/works/{work_id}/versions/{version_id}/chunks/resolve returned HTTP {r_res.status_code}"
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 8 API smoke checks for search modes and reading routes.")
    parser.add_argument("--query", default="الشافعي")
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--langs", default="ar")
    parser.add_argument(
        "--expect-degraded",
        action="store_true",
        help="Expect hybrid mode to degrade to bm25 with fallback warning",
    )
    parser.add_argument("--out-json", default="")
    args = parser.parse_args()

    client = TestClient(api_main.app)
    bm25_body = _assert_search_ok(
        client,
        mode="bm25",
        query=args.query,
        size=args.size,
        page=args.page,
        langs=args.langs,
        expect_effective_mode="bm25",
    )
    vector_total: int | None = None
    if not args.expect_degraded:
        vector_body = _assert_search_ok(
            client,
            mode="vector",
            query=args.query,
            size=args.size,
            page=args.page,
            langs=args.langs,
            expect_effective_mode="vector",
        )
        vector_total = vector_body.get("total")
    hybrid_body = _assert_search_ok(
        client,
        mode="hybrid",
        query=args.query,
        size=args.size,
        page=args.page,
        langs=args.langs,
        expect_effective_mode="bm25" if args.expect_degraded else "hybrid",
        expect_warning="qdrant_unavailable_fallback_bm25" if args.expect_degraded else None,
    )

    _check_reading_routes(client, bm25_body)

    payload = {
        "ok": True,
        "query": args.query,
        "size": args.size,
        "langs": args.langs,
        "expect_degraded": bool(args.expect_degraded),
        "bm25_total": bm25_body.get("total"),
        "vector_total": vector_total,
        "hybrid_total": hybrid_body.get("total"),
        "hybrid_effective_mode": hybrid_body.get("effective_mode"),
        "hybrid_warnings": hybrid_body.get("warnings") or [],
    }

    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
