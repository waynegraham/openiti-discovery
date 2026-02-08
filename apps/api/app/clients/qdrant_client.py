from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from ..settings import settings


_client: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL, timeout=30.0)
    return _client


def ping_qdrant() -> bool:
    try:
        # lightweight call
        get_qdrant().get_collections()
        return True
    except UnexpectedResponse:
        return False
    except Exception:
        return False


def vector_search(
    *,
    query_vector: list[float],
    limit: int,
    offset: int,
    langs: list[str] | None,
    pri_only: bool,
    period: list[str] | None = None,
    region: list[str] | None = None,
    tags: list[str] | None = None,
    version: list[str] | None = None,
) -> list[dict]:
    """
    Minimal vector search against Qdrant.
    Expects payloads include: chunk_id, lang, is_pri
    """
    q = get_qdrant()

    must = []
    if pri_only:
        must.append({"key": "is_pri", "match": {"value": True}})
    if langs:
        must.append({"key": "lang", "match": {"any": langs}})
    if period:
        must.append({"key": "period", "match": {"any": period}})
    if region:
        must.append({"key": "region", "match": {"any": region}})
    if tags:
        must.append({"key": "tags", "match": {"any": tags}})
    if version:
        must.append({"key": "version_label", "match": {"any": version}})

    flt = {"must": must} if must else None

    res = q.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
        query_filter=flt,
    )

    out = []
    for pt in res:
        payload = pt.payload or {}
        out.append(
            {
                "chunk_id": payload.get("chunk_id"),
                "score": float(pt.score),
                "payload": payload,
            }
        )
    return out


def vector_count(
    *,
    langs: list[str] | None,
    pri_only: bool,
    period: list[str] | None = None,
    region: list[str] | None = None,
    tags: list[str] | None = None,
    version: list[str] | None = None,
) -> int:
    q = get_qdrant()

    must = []
    if pri_only:
        must.append({"key": "is_pri", "match": {"value": True}})
    if langs:
        must.append({"key": "lang", "match": {"any": langs}})
    if period:
        must.append({"key": "period", "match": {"any": period}})
    if region:
        must.append({"key": "region", "match": {"any": region}})
    if tags:
        must.append({"key": "tags", "match": {"any": tags}})
    if version:
        must.append({"key": "version_label", "match": {"any": version}})

    flt = {"must": must} if must else None
    res = q.count(collection_name=settings.QDRANT_COLLECTION, count_filter=flt, exact=False)
    return int(getattr(res, "count", 0) or 0)
