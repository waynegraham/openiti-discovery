from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .settings import settings
from .db import get_engine, ping_db
from .clients.opensearch_client import bm25_search, ping_opensearch
from .clients.qdrant_client import ping_qdrant, vector_search
from .repos.chunks import get_chunk_with_neighbors
from .schemas import HealthResponse, SearchResponse, SearchHit, ChunkResponse


app = FastAPI(title="OpenITI Discovery API", version="0.1.0")


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


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    mode: str = Query("bm25", pattern="^(bm25|vector|hybrid)$"),
    size: int = Query(settings.DEFAULT_SIZE, ge=1, le=settings.MAX_SIZE),
    langs: str | None = Query(None, description="Comma-separated: ara,fas,ota"),
    pri_only: bool = Query(settings.DEFAULT_PRI_ONLY),
    # For vector/hybrid mode: provide a query vector (temporary hook).
    vector: list[float] | None = Query(
        None,
        description="Embedding vector for vector/hybrid mode (temporary hook until model endpoint exists).",
    ),
) -> SearchResponse:
    langs_list = [x.strip() for x in langs.split(",")] if langs else None

    results: list[SearchHit] = []

    if mode in ("bm25", "hybrid"):
        os_res = bm25_search(q=q, size=size, langs=langs_list, pri_only=pri_only)
        hits = os_res.get("hits", {}).get("hits", [])
        for h in hits:
            src = h.get("_source") or {}
            results.append(
                SearchHit(
                    chunk_id=src.get("chunk_id") or h.get("_id"),
                    score=float(h.get("_score") or 0.0),
                    source=src,
                    highlight=h.get("highlight"),
                )
            )

        if mode == "bm25":
            return SearchResponse(query=q, mode=mode, size=size, results=results)

    # vector or hybrid requires query vector provided
    if mode in ("vector", "hybrid"):
        if not vector:
            raise HTTPException(
                status_code=400,
                detail="vector parameter is required for vector/hybrid mode (temporary hook).",
            )
        vhits = vector_search(
            query_vector=vector, limit=size, langs=langs_list, pri_only=pri_only
        )
        if mode == "vector":
            out = [
                SearchHit(chunk_id=h["chunk_id"], score=h["score"], source=h["payload"])
                for h in vhits
                if h.get("chunk_id")
            ]
            return SearchResponse(query=q, mode=mode, size=size, results=out)

        # hybrid: naive fusion (RRF-lite): combine normalized ranks
        # This is intentionally simple; replace with true RRF later.
        bm25_rank = {hit.chunk_id: i for i, hit in enumerate(results, start=1)}
        vec_rank = {h["chunk_id"]: i for i, h in enumerate(vhits, start=1) if h.get("chunk_id")}

        all_ids = set(bm25_rank) | set(vec_rank)
        fused = []
        for cid in all_ids:
            r1 = bm25_rank.get(cid, 10_000)
            r2 = vec_rank.get(cid, 10_000)
            # smaller is better; convert to score where higher is better
            score = (1.0 / r1) + (1.0 / r2)
            fused.append((cid, score))

        fused.sort(key=lambda x: x[1], reverse=True)
        fused = fused[:size]

        # hydrate fused results from whatever source we have handy
        by_id = {hit.chunk_id: hit for hit in results}
        out: list[SearchHit] = []
        for cid, score in fused:
            base = by_id.get(cid)
            if base:
                out.append(SearchHit(chunk_id=cid, score=score, source=base.source, highlight=base.highlight))
            else:
                # fallback payload-only
                payload = next((h["payload"] for h in vhits if h.get("chunk_id") == cid), {})
                out.append(SearchHit(chunk_id=cid, score=score, source=payload))
        return SearchResponse(query=q, mode=mode, size=size, results=out)

    # Should never hit this due to mode pattern
    raise HTTPException(status_code=400, detail="invalid mode")
