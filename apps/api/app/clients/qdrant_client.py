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


def _normalize_version_values(version: list[str] | None) -> list[str] | None:
    if not version:
        return None
    out: list[str] = []
    for value in version:
        v = (value or "").strip()
        if not v:
            continue
        low = v.lower()
        if low == "pri":
            out.append("PRI")
        elif low in ("alt", "sec"):
            out.append("ALT")
        else:
            out.append(v.upper())
    return out or None


def _build_query_filter(
    *,
    langs: list[str] | None,
    pri_only: bool,
    period: list[str] | None = None,
    region: list[str] | None = None,
    tags: list[str] | None = None,
    version: list[str] | None = None,
) -> dict | None:
    must: list[dict] = []
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
    normalized_version = _normalize_version_values(version)
    if normalized_version:
        must.append({"key": "version_label", "match": {"any": normalized_version}})
    return {"must": must} if must else None


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

    flt = _build_query_filter(
        langs=langs,
        pri_only=pri_only,
        period=period,
        region=region,
        tags=tags,
        version=version,
    )

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

    flt = _build_query_filter(
        langs=langs,
        pri_only=pri_only,
        period=period,
        region=region,
        tags=tags,
        version=version,
    )

    res = q.count(collection_name=settings.QDRANT_COLLECTION, count_filter=flt, exact=False)
    return int(getattr(res, "count", 0) or 0)
