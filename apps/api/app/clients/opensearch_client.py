from __future__ import annotations

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


def bm25_search(
    *,
    q: str,
    size: int,
    langs: list[str] | None,
    pri_only: bool,
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

    body = {
        "size": size,
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

    client = get_opensearch()
    return client.search(index=settings.OPENSEARCH_INDEX_CHUNKS, body=body)
