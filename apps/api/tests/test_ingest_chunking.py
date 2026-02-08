from __future__ import annotations

import copy
import sys
import types

# Keep ingest unit tests lightweight by stubbing this optional heavy dependency.
if "sentence_transformers" not in sys.modules:
    stub = types.ModuleType("sentence_transformers")
    stub.SentenceTransformer = object
    sys.modules["sentence_transformers"] = stub

from app.ingest import run as ingest_run


def test_build_chunk_plan_prefers_structural_boundaries_and_offsets():
    raw = "\n".join(
        [
            "######OpenITI#",
            "### Section One",
            "أَبجد alpha beta gamma",
            "### Section Two",
            "delta epsilon zeta eta",
        ]
    )
    chunks = ingest_run.build_chunk_plan(raw, target_words=2, overlap_words=0)

    assert chunks
    assert any(c.heading_text == "Section One" for c in chunks)
    assert any(c.heading_text == "Section Two" for c in chunks)

    for chunk in chunks:
        assert chunk.start_char_offset >= 0
        assert chunk.end_char_offset > chunk.start_char_offset
        assert raw[chunk.start_char_offset:chunk.end_char_offset] == chunk.text_raw
        assert chunk.text_norm

    assert chunks[0].text_raw != chunks[0].text_norm


def test_build_chunk_plan_fixed_size_fallback_without_headings():
    raw = "alpha beta gamma delta epsilon zeta"
    chunks = ingest_run.build_chunk_plan(raw, target_words=2, overlap_words=0)

    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert all(c.heading_text is None for c in chunks)
    assert all(c.heading_path is None for c in chunks)


def test_ingest_regression_stable_chunk_ids_and_continuity(monkeypatch):
    text = ingest_run.DiscoveredText(
        author_id="a1",
        work_id="a1.w1",
        version_id="a1.w1.v1-ara1",
        repo_path="data/a1/w1/v1-ara1.mARkdown",
        abs_path=ingest_run.Path("fake.mARkdown"),
        is_pri=True,
        lang="ara",
    )
    raw = "\n".join(
        [
            "######OpenITI#",
            "### First",
            "alpha beta gamma delta",
            "### Second",
            "epsilon zeta eta theta",
        ]
    )

    state: dict[str, ingest_run.IngestStateRow] = {}
    run_rows: dict[int, list[dict]] = {}
    run_ids: dict[int, list[str]] = {}
    active_run = {"idx": 1}

    def fake_get_ingest_state(_engine, version_id: str):
        return state.get(version_id)

    def fake_set_ingest_state(_engine, version_id: str, status: str, *, last_chunk_index=None, error_message=None):
        current = state.get(version_id)
        current_status = current.status if current else None
        assert ingest_run.is_valid_ingest_transition(current_status, status)
        next_last = last_chunk_index if last_chunk_index is not None else (current.last_chunk_index if current else None)
        state[version_id] = ingest_run.IngestStateRow(
            version_id=version_id,
            status=status,
            last_chunk_index=next_last,
        )

    def fake_upsert_chunks_batch(_engine, rows: list[dict]):
        run_rows.setdefault(active_run["idx"], []).extend(copy.deepcopy(rows))

    def fake_set_chunk_links(_engine, _version_id: str):
        rows = run_rows.get(active_run["idx"], [])
        by_index = {r["chunk_index"]: r for r in rows}
        for index, row in by_index.items():
            prev_row = by_index.get(index - 1)
            next_row = by_index.get(index + 1)
            row["prev_chunk_id"] = prev_row["chunk_id"] if prev_row else None
            row["next_chunk_id"] = next_row["chunk_id"] if next_row else None

    def fake_os_bulk_index(docs: list[dict]):
        run_ids.setdefault(active_run["idx"], []).extend(d["chunk_id"] for d in docs)

    monkeypatch.setattr(ingest_run, "get_engine", lambda: object())
    monkeypatch.setattr(ingest_run, "ensure_write_index_target", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "_load_curated_tags", lambda: set())
    monkeypatch.setattr(ingest_run, "load_metadata", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(ingest_run, "discover_200_pri_arabic", lambda *_args, **_kwargs: [text])
    monkeypatch.setattr(ingest_run, "upsert_author", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "upsert_work", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "upsert_version", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "get_ingest_state", fake_get_ingest_state)
    monkeypatch.setattr(ingest_run, "set_ingest_state", fake_set_ingest_state)
    monkeypatch.setattr(ingest_run, "upsert_chunks_batch", fake_upsert_chunks_batch)
    monkeypatch.setattr(ingest_run, "set_chunk_links", fake_set_chunk_links)
    monkeypatch.setattr(ingest_run, "os_bulk_index", fake_os_bulk_index)
    monkeypatch.setattr(ingest_run, "sha256_file", lambda *_args, **_kwargs: "checksum")
    monkeypatch.setattr(ingest_run, "read_text_file", lambda *_args, **_kwargs: raw)
    monkeypatch.setattr(ingest_run, "tqdm", lambda x, **_kwargs: x)

    monkeypatch.setattr(ingest_run, "EMBEDDINGS_ENABLED", False)
    monkeypatch.setattr(ingest_run, "SKIP_EXISTING", False)
    monkeypatch.setattr(ingest_run, "CHUNK_TARGET_WORDS", 2)
    monkeypatch.setattr(ingest_run, "CHUNK_MAX_OVERLAP_WORDS", 0)
    monkeypatch.setattr(ingest_run, "OS_BULK_BATCH", 2)

    monkeypatch.setenv("CORPUS_ROOT", ".")

    ingest_run.run()
    active_run["idx"] = 2
    ingest_run.run()

    assert run_ids[1] == run_ids[2]

    rows = sorted(run_rows[1], key=lambda r: r["chunk_index"])
    assert rows

    for row in rows:
        start = row["start_char_offset"]
        end = row["end_char_offset"]
        assert isinstance(start, int) and isinstance(end, int)
        assert end > start
        assert raw[start:end] == row["text_raw"]

    for i, row in enumerate(rows):
        expected_prev = rows[i - 1]["chunk_id"] if i > 0 else None
        expected_next = rows[i + 1]["chunk_id"] if i + 1 < len(rows) else None
        assert row["prev_chunk_id"] == expected_prev
        assert row["next_chunk_id"] == expected_next
