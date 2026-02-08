from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .clients.opensearch_client import (
    bm25_search,
    fetch_sources_by_chunk_ids,
    filter_chunk_ids,
    ping_opensearch,
)
from .clients.qdrant_client import ping_qdrant, vector_count, vector_search
from .db import get_engine, ping_db
from .embedding_service import embedding_trace, encode_texts
from .repos.chunks import get_chunk_with_neighbors
from .runtime_config import facet_labels, search_runtime
from .sanitize import sanitize_highlight_html
from .schemas import (
    ChunkResponse,
    EmbedRequest,
    EmbedResponse,
    FacetBucket,
    HealthResponse,
    SearchHit,
    SearchResponse,
)
from .settings import settings


app = FastAPI(title="OpenITI Discovery API", version="0.1.0")


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    vals = [x.strip() for x in value.split(",") if x.strip()]
    return vals or None


def _search_cfg() -> dict:
    cfg = search_runtime().get("search") or {}
    return cfg if isinstance(cfg, dict) else {}


def _embedding_cfg() -> dict:
    cfg = search_runtime().get("embedding") or {}
    return cfg if isinstance(cfg, dict) else {}


def _hybrid_cfg() -> dict:
    cfg = search_runtime().get("hybrid") or {}
    return cfg if isinstance(cfg, dict) else {}


def _max_query_len() -> int:
    return int(_search_cfg().get("max_query_length_chars", 256))


def _max_batch_size() -> int:
    return int(_embedding_cfg().get("max_batch_size", 32))


def _candidate_k(page: int, size: int) -> int:
    cfg = _hybrid_cfg().get("candidate_pool") or {}
    mult = int(cfg.get("multiplier_per_page_size", 5))
    floor = int(cfg.get("min", 100))
    ceiling = int(cfg.get("max", 1000))
    return max(floor, min(ceiling, page * size * mult))


def _rrf_k() -> int:
    cfg = (_hybrid_cfg().get("rrf") or {}) if _hybrid_cfg() else {}
    return int(cfg.get("rrf_k", 60))


def _label_for(facet: str, key: str) -> str:
    labels = facet_labels()
    return labels.get(facet, {}).get(key, key)


def _build_facets(aggs: dict) -> dict[str, list[FacetBucket]]:
    out: dict[str, list[FacetBucket]] = {}
    for key in ("period", "region", "tags", "lang", "version"):
        buckets = aggs.get(key, {}).get("buckets", []) if aggs else []
        out[key] = [
            FacetBucket(
                key=str(b.get("key")),
                label=_label_for(key, str(b.get("key"))),
                count=int(b.get("doc_count") or 0),
            )
            for b in buckets
            if b.get("key") is not None
        ]
    return out


def _sanitize_highlight(highlight: dict | None) -> dict | None:
    if not highlight:
        return highlight
    out: dict[str, list[str]] = {}
    for k, vals in (highlight or {}).items():
        if isinstance(vals, list):
            out[k] = [sanitize_highlight_html(str(v)) for v in vals]
    return out


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    pg = ping_db()
    os_ok = ping_opensearch()
    qd = ping_qdrant()
    ok = pg and os_ok and qd
    return HealthResponse(ok=ok, postgres=pg, opensearch=os_ok, qdrant=qd)


@app.get("/chunks/{chunk_id}", response_model=ChunkResponse)
def get_chunk(chunk_id: str) -> ChunkResponse:
    eng = get_engine()
    row = get_chunk_with_neighbors(eng, chunk_id)
    if not row:
        raise HTTPException(status_code=404, detail="chunk not found")
    return ChunkResponse(
        chunk_id=row["chunk_id"],
        version_id=row["version_id"],
        work_id=row["work_id"],
        author_id=row["author_id"],
        chunk_index=row["chunk_index"],
        heading_text=row.get("heading_text"),
        heading_path=row.get("heading_path"),
        text_raw=row["text_raw"],
        prev_chunk_id=row.get("prev_chunk_id"),
        next_chunk_id=row.get("next_chunk_id"),
    )


@app.post("/embed", response_model=EmbedResponse)
def embed(payload: EmbedRequest) -> EmbedResponse:
    texts = payload.texts or []
    if not texts:
        raise HTTPException(status_code=400, detail="texts must not be empty")
    if len(texts) > _max_batch_size():
        raise HTTPException(
            status_code=400,
            detail=f"texts exceeds max batch size {_max_batch_size()}",
        )
    max_len = _max_query_len()
    for txt in texts:
        if len(txt) > max_len:
            raise HTTPException(
                status_code=400,
                detail=f"text exceeds max length {max_len}",
            )

    vectors = encode_texts(texts, payload.input_type)
    trace = embedding_trace()
    return EmbedResponse(vectors=vectors, **trace)


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    mode: str = Query("bm25", pattern="^(bm25|vector|hybrid)$"),
    size: int = Query(settings.DEFAULT_SIZE, ge=1, le=settings.MAX_SIZE),
    page: int = Query(1, ge=1),
    langs: str | None = Query(None, description="Comma-separated: ara,fas,ota"),
    pri_only: bool = Query(settings.DEFAULT_PRI_ONLY),
    period: str | None = Query(None),
    region: str | None = Query(None),
    tags: str | None = Query(None),
    version: str | None = Query(None),
) -> SearchResponse:
    max_len = _max_query_len()
    if len(q) > max_len:
        raise HTTPException(status_code=400, detail=f"q exceeds max length {max_len}")

    requested_mode = mode
    effective_mode = mode
    warnings: list[str] = []

    trace = embedding_trace()

    langs_list = _split_csv(langs)
    period_list = _split_csv(period)
    region_list = _split_csv(region)
    tags_list = _split_csv(tags)
    version_list = _split_csv(version)
    from_ = (page - 1) * size

    if mode == "bm25":
        os_res = bm25_search(
            q=q,
            size=size,
            from_=from_,
            langs=langs_list,
            pri_only=pri_only,
            period=period_list,
            region=region_list,
            tags=tags_list,
            version=version_list,
            include_aggs=True,
        )
        hits = os_res.get("hits", {}).get("hits", [])
        total_obj = os_res.get("hits", {}).get("total", 0)
        total = int(total_obj.get("value") if isinstance(total_obj, dict) else total_obj or 0)

        results = [
            SearchHit(
                chunk_id=(h.get("_source") or {}).get("chunk_id") or h.get("_id"),
                score=float(h.get("_score") or 0.0),
                source=h.get("_source") or {},
                highlight=_sanitize_highlight(h.get("highlight")),
            )
            for h in hits
        ]

        facets = _build_facets(os_res.get("aggregations", {}) or {})
        return SearchResponse(
            query=q,
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            warnings=warnings,
            total=total,
            page=page,
            size=size,
            results=results,
            facets=facets,
            **trace,
        )

    # vector and hybrid both require query embedding
    query_vector = encode_texts([q], "query")[0]

    if mode == "vector":
        try:
            vhits = vector_search(
                query_vector=query_vector,
                limit=size,
                offset=from_,
                langs=langs_list,
                pri_only=pri_only,
                period=period_list,
                region=region_list,
                tags=tags_list,
                version=version_list,
            )
            total = vector_count(
                langs=langs_list,
                pri_only=pri_only,
                period=period_list,
                region=region_list,
                tags=tags_list,
                version=version_list,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"vector search unavailable: {exc}")

        ids = [str(h.get("chunk_id")) for h in vhits if h.get("chunk_id")]
        if ids:
            allowed = filter_chunk_ids(
                ids,
                langs=langs_list,
                pri_only=pri_only,
                period=period_list,
                region=region_list,
                tags=tags_list,
                version=version_list,
            )
            vhits = [h for h in vhits if h.get("chunk_id") in allowed]

        sources = fetch_sources_by_chunk_ids([str(h.get("chunk_id")) for h in vhits if h.get("chunk_id")])

        results = [
            SearchHit(
                chunk_id=str(h["chunk_id"]),
                score=float(h["score"]),
                source=sources.get(str(h["chunk_id"]), h.get("payload") or {}),
            )
            for h in vhits
            if h.get("chunk_id")
        ]

        return SearchResponse(
            query=q,
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            warnings=warnings,
            total=total,
            page=page,
            size=size,
            results=results,
            facets={},
            **trace,
        )

    # hybrid mode
    candidate_k = _candidate_k(page, size)

    bm25_res = bm25_search(
        q=q,
        size=candidate_k,
        from_=0,
        langs=langs_list,
        pri_only=pri_only,
        period=period_list,
        region=region_list,
        tags=tags_list,
        version=version_list,
        include_aggs=False,
    )
    bm25_hits = bm25_res.get("hits", {}).get("hits", [])
    bm25_total_obj = bm25_res.get("hits", {}).get("total", 0)
    bm25_total = int(
        bm25_total_obj.get("value") if isinstance(bm25_total_obj, dict) else bm25_total_obj or 0
    )

    try:
        vec_hits = vector_search(
            query_vector=query_vector,
            limit=candidate_k,
            offset=0,
            langs=langs_list,
            pri_only=pri_only,
            period=period_list,
            region=region_list,
            tags=tags_list,
            version=version_list,
        )
        vec_total = vector_count(
            langs=langs_list,
            pri_only=pri_only,
            period=period_list,
            region=region_list,
            tags=tags_list,
            version=version_list,
        )
    except Exception:
        effective_mode = "bm25"
        warnings.append("qdrant_unavailable_fallback_bm25")

        page_res = bm25_search(
            q=q,
            size=size,
            from_=from_,
            langs=langs_list,
            pri_only=pri_only,
            period=period_list,
            region=region_list,
            tags=tags_list,
            version=version_list,
            include_aggs=True,
        )
        page_hits = page_res.get("hits", {}).get("hits", [])
        total_obj = page_res.get("hits", {}).get("total", 0)
        total = int(total_obj.get("value") if isinstance(total_obj, dict) else total_obj or 0)

        results = [
            SearchHit(
                chunk_id=(h.get("_source") or {}).get("chunk_id") or h.get("_id"),
                score=float(h.get("_score") or 0.0),
                source=h.get("_source") or {},
                highlight=_sanitize_highlight(h.get("highlight")),
            )
            for h in page_hits
        ]
        facets = _build_facets(page_res.get("aggregations", {}) or {})

        return SearchResponse(
            query=q,
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            warnings=warnings,
            total=total,
            page=page,
            size=size,
            results=results,
            facets=facets,
            **trace,
        )

    # True RRF fusion
    rrf_k = _rrf_k()
    bm25_rank = {
        ((h.get("_source") or {}).get("chunk_id") or h.get("_id")): i
        for i, h in enumerate(bm25_hits, start=1)
    }
    vec_rank = {str(h.get("chunk_id")): i for i, h in enumerate(vec_hits, start=1) if h.get("chunk_id")}

    all_ids = (set(k for k in bm25_rank if k) | set(k for k in vec_rank if k))
    fused: list[tuple[str, float]] = []
    for cid in all_ids:
        s = 0.0
        rb = bm25_rank.get(cid)
        rv = vec_rank.get(cid)
        if rb is not None:
            s += 1.0 / (rrf_k + rb)
        if rv is not None:
            s += 1.0 / (rrf_k + rv)
        fused.append((cid, s))

    fused.sort(key=lambda x: x[1], reverse=True)
    total = max(bm25_total, vec_total)
    page_fused = fused[from_: from_ + size]

    bm25_by_id = {
        ((h.get("_source") or {}).get("chunk_id") or h.get("_id")): h
        for h in bm25_hits
    }
    source_map = fetch_sources_by_chunk_ids([cid for cid, _ in page_fused])

    results: list[SearchHit] = []
    for cid, score in page_fused:
        base = bm25_by_id.get(cid)
        highlight = _sanitize_highlight(base.get("highlight")) if base else None
        src = source_map.get(cid)
        if not src:
            src = next((h.get("payload") or {} for h in vec_hits if str(h.get("chunk_id")) == cid), {})
        results.append(SearchHit(chunk_id=cid, score=score, source=src or {}, highlight=highlight))

    return SearchResponse(
        query=q,
        requested_mode=requested_mode,
        effective_mode=effective_mode,
        warnings=warnings,
        total=total,
        page=page,
        size=size,
        results=results,
        facets={},
        **trace,
    )
