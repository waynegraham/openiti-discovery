from __future__ import annotations

import re

from opensearchpy import OpenSearch
from opensearchpy.exceptions import OpenSearchException

from ..settings import settings


_client: OpenSearch | None = None


def get_opensearch() -> OpenSearch:
    global _client
    if _client is None:
        # Security disabled in local dev stack; adjust for hosted deployments.
        _client = OpenSearch(
            hosts=[settings.OPENSEARCH_URL],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
        )
    return _client


def ping_opensearch() -> bool:
    try:
        return bool(get_opensearch().ping())
    except OpenSearchException:
        return False
    except Exception:
        return False


def ensure_write_index_target(index_or_alias: str) -> str:
    """
    Ensure writes to `index_or_alias` will succeed.
    - If it is a concrete index, return it unchanged.
    - If it is an alias with missing/invalid write index state, pick one target index
      and update alias metadata so exactly one index has `is_write_index=true`.
    """
    client = get_opensearch()

    if client.indices.exists(index=index_or_alias):
        return index_or_alias

    if not client.indices.exists_alias(name=index_or_alias):
        raise RuntimeError(
            f"OpenSearch target '{index_or_alias}' is neither an existing index nor alias."
        )

    alias_view = client.indices.get_alias(name=index_or_alias)
    if not alias_view:
        raise RuntimeError(f"OpenSearch alias '{index_or_alias}' has no backing indices.")

    all_indices = sorted(alias_view.keys())
    write_indices: list[str] = []
    for idx, data in alias_view.items():
        alias_cfg = (data.get("aliases") or {}).get(index_or_alias) or {}
        if alias_cfg.get("is_write_index") is True:
            write_indices.append(idx)

    if len(write_indices) == 1:
        return index_or_alias

    def _index_sort_key(name: str) -> tuple[int, str]:
        match = re.search(r"_v(\d+)$", name)
        return (int(match.group(1)) if match else -1, name)

    target = max(all_indices, key=_index_sort_key)
    actions = [{"add": {"index": target, "alias": index_or_alias, "is_write_index": True}}]
    for idx in all_indices:
        if idx == target:
            continue
        actions.append(
            {"add": {"index": idx, "alias": index_or_alias, "is_write_index": False}}
        )

    client.indices.update_aliases(body={"actions": actions})
    return index_or_alias


def bm25_search(
    *,
    q: str,
    size: int,
    from_: int,
    langs: list[str] | None,
    pri_only: bool,
    period: list[str] | None = None,
    region: list[str] | None = None,
    tags: list[str] | None = None,
    version: list[str] | None = None,
    include_aggs: bool = True,
) -> dict:
    """
    Minimal BM25 search using multi_match across analyzed content fields.
    Assumes the OpenSearch template provided earlier.
    """
    filters = []
    if pri_only:
        filters.append({"term": {"is_pri": True}})
    if langs:
        filters.append({"terms": {"lang": langs}})
    if period:
        filters.append({"terms": {"period": period}})
    if region:
        filters.append({"terms": {"region": region}})
    if tags:
        filters.append({"terms": {"tags": tags}})
    if version:
        filters.append({"terms": {"version_label": version}})

    body = {
        "size": size,
        "from": from_,
        "query": {
            "bool": {
                "filter": filters,
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "type": "best_fields",
                            "fields": [
                                "title^2",
                                "content^4",
                                "content.nostem^3",
                                "content.exact^2",
                                # content.folded only exists if ICU plugin is installed and template includes it
                                "content.folded^1",
                            ],
                        }
                    }
                ],
            }
        },
        "highlight": {
            "fields": {
                "content": {},
                "content.nostem": {},
            }
        },
    }
    if include_aggs:
        body["aggs"] = {
            "period": {"terms": {"field": "period", "size": 24}},
            "region": {"terms": {"field": "region", "size": 24}},
            "tags": {"terms": {"field": "tags", "size": 50}},
            "lang": {"terms": {"field": "lang", "size": 10}},
            "version": {"terms": {"field": "version_label", "size": 10}},
        }

    client = get_opensearch()
    return client.search(index=settings.OPENSEARCH_INDEX_CHUNKS, body=body)


def fetch_sources_by_chunk_ids(chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    client = get_opensearch()
    body = {
        "size": len(chunk_ids),
        "query": {"terms": {"chunk_id": chunk_ids}},
    }
    res = client.search(index=settings.OPENSEARCH_INDEX_CHUNKS, body=body)
    out: dict[str, dict] = {}
    for hit in res.get("hits", {}).get("hits", []):
        src = hit.get("_source") or {}
        cid = src.get("chunk_id") or hit.get("_id")
        if cid:
            out[str(cid)] = src
    return out


def filter_chunk_ids(
    chunk_ids: list[str],
    *,
    langs: list[str] | None,
    pri_only: bool,
    period: list[str] | None = None,
    region: list[str] | None = None,
    tags: list[str] | None = None,
    version: list[str] | None = None,
) -> set[str]:
    if not chunk_ids:
        return set()

    filters = [{"terms": {"chunk_id": chunk_ids}}]
    if pri_only:
        filters.append({"term": {"is_pri": True}})
    if langs:
        filters.append({"terms": {"lang": langs}})
    if period:
        filters.append({"terms": {"period": period}})
    if region:
        filters.append({"terms": {"region": region}})
    if tags:
        filters.append({"terms": {"tags": tags}})
    if version:
        filters.append({"terms": {"version_label": version}})

    client = get_opensearch()
    res = client.search(
        index=settings.OPENSEARCH_INDEX_CHUNKS,
        body={
            "size": len(chunk_ids),
            "_source": ["chunk_id"],
            "query": {"bool": {"filter": filters}},
        },
    )
    allowed: set[str] = set()
    for hit in res.get("hits", {}).get("hits", []):
        src = hit.get("_source") or {}
        cid = src.get("chunk_id") or hit.get("_id")
        if cid:
            allowed.add(str(cid))
    return allowed
