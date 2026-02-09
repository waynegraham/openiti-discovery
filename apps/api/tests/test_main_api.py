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


def test_search_vector_forwards_filters_and_normalizes_version(client, monkeypatch):
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

    captured: dict[str, dict] = {}

    def fake_vector_search(**kwargs):
        captured["vector_search"] = kwargs
        return [{"chunk_id": "c1", "score": 0.9, "payload": {"chunk_id": "c1"}}]

    def fake_vector_count(**kwargs):
        captured["vector_count"] = kwargs
        return 1

    def fake_filter_chunk_ids(chunk_ids, **kwargs):
        captured["filter_chunk_ids"] = {"chunk_ids": list(chunk_ids), **kwargs}
        return set(chunk_ids)

    monkeypatch.setattr(main, "vector_search", fake_vector_search)
    monkeypatch.setattr(main, "vector_count", fake_vector_count)
    monkeypatch.setattr(main, "filter_chunk_ids", fake_filter_chunk_ids)
    monkeypatch.setattr(
        main,
        "fetch_sources_by_chunk_ids",
        lambda chunk_ids: {"c1": {"chunk_id": "c1", "content": "hydrated"}},
    )

    res = client.get(
        "/search",
        params={
            "q": "abc",
            "mode": "vector",
            "period": "Abb",
            "region": "Basra",
            "tags": "GAL@adab",
            "version": "pri",
        },
    )
    body = res.json()

    assert res.status_code == 200
    assert body["results"][0]["chunk_id"] == "c1"
    assert captured["vector_search"]["period"] == ["Abb"]
    assert captured["vector_search"]["region"] == ["Basra"]
    assert captured["vector_search"]["tags"] == ["GAL@adab"]
    assert captured["vector_search"]["langs"] is None
    assert captured["vector_search"]["version"] == ["PRI"]
    assert captured["vector_count"]["version"] == ["PRI"]
    assert captured["filter_chunk_ids"]["version"] == ["PRI"]


def test_search_normalizes_language_alias_filters(client, monkeypatch):
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

    captured: dict[str, dict] = {}

    def fake_vector_search(**kwargs):
        captured["vector_search"] = kwargs
        return [{"chunk_id": "c1", "score": 0.9, "payload": {"chunk_id": "c1"}}]

    monkeypatch.setattr(main, "vector_search", fake_vector_search)
    monkeypatch.setattr(main, "vector_count", lambda **kwargs: 1)
    monkeypatch.setattr(main, "filter_chunk_ids", lambda chunk_ids, **kwargs: set(chunk_ids))
    monkeypatch.setattr(main, "fetch_sources_by_chunk_ids", lambda chunk_ids: {})

    res = client.get(
        "/search",
        params={
            "q": "abc",
            "mode": "vector",
            "langs": "ara,eng,zzz",
        },
    )

    assert res.status_code == 200
    assert captured["vector_search"]["langs"] == ["ar", "en", "unknown"]


def test_search_hybrid_forwards_filters_to_bm25_and_vector(client, monkeypatch):
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
    monkeypatch.setattr(main, "_candidate_k", lambda page, size: 5)
    monkeypatch.setattr(main, "_rrf_k", lambda: 60)

    captured: dict[str, dict] = {}

    def fake_bm25_search(**kwargs):
        captured["bm25_search"] = kwargs
        return {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "c1",
                        "_score": 1.0,
                        "_source": {"chunk_id": "c1", "content": "bm25"},
                        "highlight": {"content": ["<em>x</em>"]},
                    }
                ],
            }
        }

    def fake_vector_search(**kwargs):
        captured["vector_search"] = kwargs
        return [{"chunk_id": "c1", "score": 0.9, "payload": {"chunk_id": "c1"}}]

    def fake_vector_count(**kwargs):
        captured["vector_count"] = kwargs
        return 1

    monkeypatch.setattr(main, "bm25_search", fake_bm25_search)
    monkeypatch.setattr(main, "vector_search", fake_vector_search)
    monkeypatch.setattr(main, "vector_count", fake_vector_count)
    monkeypatch.setattr(
        main,
        "fetch_sources_by_chunk_ids",
        lambda chunk_ids: {"c1": {"chunk_id": "c1", "content": "hydrated"}},
    )

    res = client.get(
        "/search",
        params={
            "q": "abc",
            "mode": "hybrid",
            "period": "Abb",
            "region": "Basra",
            "tags": "GAL@adab",
            "version": "sec",
        },
    )
    body = res.json()

    assert res.status_code == 200
    assert body["effective_mode"] == "hybrid"
    assert body["results"][0]["chunk_id"] == "c1"
    assert captured["bm25_search"]["period"] == ["Abb"]
    assert captured["bm25_search"]["region"] == ["Basra"]
    assert captured["bm25_search"]["tags"] == ["GAL@adab"]
    assert captured["bm25_search"]["version"] == ["ALT"]
    assert captured["vector_search"]["version"] == ["ALT"]
    assert captured["vector_count"]["version"] == ["ALT"]


def test_get_work_detail_returns_work(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(
        main,
        "get_work",
        lambda engine, work_id: {
            "work_id": "w1",
            "author_id": "a1",
            "title_ar": "t_ar",
            "title_latn": "t_latn",
            "author_name_ar": "n_ar",
            "author_name_latn": "n_latn",
            "death_year_ah": 600,
            "death_year_ce": 1203,
            "work_year_start_ce": 1190,
            "work_year_end_ce": 1200,
        },
    )

    res = client.get("/works/w1")
    assert res.status_code == 200
    assert res.json()["work_id"] == "w1"
    assert res.json()["author_id"] == "a1"


def test_get_work_detail_404(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: None)

    res = client.get("/works/missing")
    assert res.status_code == 404
    assert res.json()["detail"] == "work not found"


def test_get_versions_for_work_uses_configured_language_order(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: {"work_id": work_id, "author_id": "a1"})
    monkeypatch.setattr(main.settings, "SUPPORTED_LANGUAGES", "ar,en,fa")

    captured: dict[str, list[str]] = {}

    def fake_list_work_versions(engine, work_id, preferred_langs):
        captured["preferred_langs"] = list(preferred_langs)
        return [
            {
                "version_id": "v1",
                "work_id": work_id,
                "lang": "ar",
                "is_pri": True,
                "source_uri": None,
                "repo_path": "repo/v1",
            }
        ]

    monkeypatch.setattr(main, "list_work_versions", fake_list_work_versions)

    res = client.get(
        "/works/w1/versions",
        params={"locale": "ar", "preferred_langs": "fas,ara"},
    )

    assert res.status_code == 200
    assert captured["preferred_langs"] == ["ar", "en", "fa"]
    assert res.json()[0]["version_id"] == "v1"


def test_get_versions_for_work_404_when_work_missing(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: None)

    res = client.get("/works/w1/versions")
    assert res.status_code == 404
    assert res.json()["detail"] == "work not found"


def test_resolve_version_chunk_returns_exact_or_lower_match(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: {"work_id": work_id, "author_id": "a1"})
    monkeypatch.setattr(
        main,
        "list_work_versions",
        lambda engine, work_id, preferred_langs: [{"version_id": "v1"}],
    )
    monkeypatch.setattr(
        main,
        "resolve_chunk_for_version",
        lambda engine, work_id, version_id, target_chunk_index: {
            "chunk_id": "v1::7",
            "chunk_index": 7,
        },
    )

    res = client.get(
        "/works/w1/versions/v1/chunks/resolve",
        params={"target_chunk_index": 8},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["resolved_chunk_id"] == "v1::7"
    assert body["resolved_chunk_index"] == 7
    assert body["requested_chunk_index"] == 8


def test_resolve_version_chunk_404_when_no_lower_chunk(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: {"work_id": work_id, "author_id": "a1"})
    monkeypatch.setattr(
        main,
        "list_work_versions",
        lambda engine, work_id, preferred_langs: [{"version_id": "v1"}],
    )
    monkeypatch.setattr(main, "resolve_chunk_for_version", lambda *args, **kwargs: None)

    res = client.get(
        "/works/w1/versions/v1/chunks/resolve",
        params={"target_chunk_index": 0},
    )

    assert res.status_code == 404
    assert res.json()["detail"] == "no chunk at or below target_chunk_index"


def test_resolve_version_chunk_404_when_version_not_in_work(client, monkeypatch):
    monkeypatch.setattr(main, "get_engine", lambda: object())
    monkeypatch.setattr(main, "get_work", lambda engine, work_id: {"work_id": work_id, "author_id": "a1"})
    monkeypatch.setattr(
        main,
        "list_work_versions",
        lambda engine, work_id, preferred_langs: [{"version_id": "v1"}],
    )

    res = client.get(
        "/works/w1/versions/v2/chunks/resolve",
        params={"target_chunk_index": 0},
    )

    assert res.status_code == 404
    assert res.json()["detail"] == "version not found for work"
