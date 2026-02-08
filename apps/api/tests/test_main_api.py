from __future__ import annotations

from app import main


def test_health_reports_dependency_states(client, monkeypatch):
    monkeypatch.setattr(main, "ping_db", lambda: True)
    monkeypatch.setattr(main, "ping_opensearch", lambda: False)
    monkeypatch.setattr(main, "ping_qdrant", lambda: True)

    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {
        "ok": False,
        "postgres": True,
        "opensearch": False,
        "qdrant": True,
    }


def test_embed_rejects_empty_payload(client):
    res = client.post("/embed", json={"texts": [], "input_type": "query"})
    assert res.status_code == 400
    assert res.json()["detail"] == "texts must not be empty"


def test_embed_rejects_text_over_max_length(client, monkeypatch):
    monkeypatch.setattr(main, "_max_query_len", lambda: 5)

    res = client.post("/embed", json={"texts": ["abcdef"], "input_type": "query"})

    assert res.status_code == 400
    assert res.json()["detail"] == "text exceeds max length 5"


def test_embed_returns_vectors_and_trace(client, monkeypatch):
    monkeypatch.setattr(main, "encode_texts", lambda texts, input_type: [[0.1, 0.2]])
    monkeypatch.setattr(
        main,
        "embedding_trace",
        lambda: {
            "embedding_model": "unit-test-model",
            "embedding_model_version": "v1",
            "normalization_version": "norm-v1",
        },
    )

    res = client.post("/embed", json={"texts": ["abc"], "input_type": "query"})

    assert res.status_code == 200
    assert res.json() == {
        "vectors": [[0.1, 0.2]],
        "embedding_model": "unit-test-model",
        "embedding_model_version": "v1",
        "normalization_version": "norm-v1",
    }


def test_search_bm25_returns_facets_and_sanitized_highlights(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "embedding_trace",
        lambda: {
            "embedding_model": "m",
            "embedding_model_version": "v",
            "normalization_version": "n",
        },
    )
    monkeypatch.setattr(main, "facet_labels", lambda: {"period": {"P1": "Period 1"}})
    monkeypatch.setattr(
        main,
        "bm25_search",
        lambda **kwargs: {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "chunk-1",
                        "_score": 12.3,
                        "_source": {"chunk_id": "chunk-1", "content": "text"},
                        "highlight": {"content": ['ok <em>hit</em> <script>x</script>']},
                    }
                ],
            },
            "aggregations": {
                "period": {"buckets": [{"key": "P1", "doc_count": 4}]},
                "region": {"buckets": []},
                "tags": {"buckets": []},
                "lang": {"buckets": []},
                "version": {"buckets": []},
            },
        },
    )

    res = client.get("/search", params={"q": "abc", "mode": "bm25"})
    body = res.json()

    assert res.status_code == 200
    assert body["requested_mode"] == "bm25"
    assert body["effective_mode"] == "bm25"
    assert body["total"] == 1
    assert body["results"][0]["chunk_id"] == "chunk-1"
    assert body["results"][0]["highlight"]["content"][0] == "ok <em>hit</em> x"
    assert body["facets"]["period"] == [{"key": "P1", "label": "Period 1", "count": 4}]


def test_search_vector_hydrates_from_opensearch_sources(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "embedding_trace",
        lambda: {
            "embedding_model": "m",
            "embedding_model_version": "v",
            "normalization_version": "n",
        },
    )
    monkeypatch.setattr(main, "encode_texts", lambda texts, input_type: [[0.2, 0.3]])
    monkeypatch.setattr(
        main,
        "vector_search",
        lambda **kwargs: [
            {"chunk_id": "c1", "score": 0.91, "payload": {"chunk_id": "c1", "content": "payload"}},
            {"chunk_id": "c2", "score": 0.87, "payload": {"chunk_id": "c2", "content": "payload"}},
        ],
    )
    monkeypatch.setattr(main, "vector_count", lambda **kwargs: 2)
    monkeypatch.setattr(main, "filter_chunk_ids", lambda chunk_ids, **kwargs: {"c1"})
    monkeypatch.setattr(
        main,
        "fetch_sources_by_chunk_ids",
        lambda chunk_ids: {"c1": {"chunk_id": "c1", "content": "hydrated"}},
    )

    res = client.get("/search", params={"q": "abc", "mode": "vector", "size": 2})
    body = res.json()

    assert res.status_code == 200
    assert body["effective_mode"] == "vector"
    assert body["total"] == 2
    assert body["facets"] == {}
    assert [hit["chunk_id"] for hit in body["results"]] == ["c1"]
    assert body["results"][0]["source"]["content"] == "hydrated"


def test_search_hybrid_falls_back_to_bm25_when_vector_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "embedding_trace",
        lambda: {
            "embedding_model": "m",
            "embedding_model_version": "v",
            "normalization_version": "n",
        },
    )
    monkeypatch.setattr(main, "encode_texts", lambda texts, input_type: [[0.2, 0.3]])

    calls = {"count": 0}

    def fake_bm25_search(**kwargs):
        calls["count"] += 1
        return {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "chunk-9",
                        "_score": 3.14,
                        "_source": {"chunk_id": "chunk-9", "content": "bm25"},
                        "highlight": {"content": ["<em>bm25</em>"]},
                    }
                ],
            },
            "aggregations": {
                "period": {"buckets": []},
                "region": {"buckets": []},
                "tags": {"buckets": []},
                "lang": {"buckets": []},
                "version": {"buckets": []},
            },
        }

    monkeypatch.setattr(main, "bm25_search", fake_bm25_search)
    monkeypatch.setattr(main, "vector_search", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(main, "facet_labels", lambda: {})

    res = client.get("/search", params={"q": "abc", "mode": "hybrid"})
    body = res.json()

    assert res.status_code == 200
    assert calls["count"] == 2
    assert body["requested_mode"] == "hybrid"
    assert body["effective_mode"] == "bm25"
    assert body["warnings"] == ["qdrant_unavailable_fallback_bm25"]
    assert body["results"][0]["chunk_id"] == "chunk-9"
