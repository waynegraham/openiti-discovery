from __future__ import annotations

import sys
import types

# Keep ingest unit tests lightweight by stubbing this optional heavy dependency.
if "sentence_transformers" not in sys.modules:
    stub = types.ModuleType("sentence_transformers")
    stub.SentenceTransformer = object
    sys.modules["sentence_transformers"] = stub

from app.ingest import run as ingest_run


def test_decide_ingest_behavior_matrix():
    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="complete", last_chunk_index=9),
        skip_existing=True,
        embeddings_enabled=False,
    )
    assert decision.action == "skip_complete"

    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="complete", last_chunk_index=9),
        skip_existing=False,
        embeddings_enabled=False,
    )
    assert decision.action == "process"
    assert decision.start_chunk_index == 0

    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="indexed_bm25", last_chunk_index=7),
        skip_existing=True,
        embeddings_enabled=False,
    )
    assert decision.action == "resume"
    assert decision.start_chunk_index == 8

    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="indexed_bm25", last_chunk_index=7),
        skip_existing=True,
        embeddings_enabled=True,
    )
    assert decision.action == "resume"
    assert decision.start_chunk_index == 7

    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="embedded", last_chunk_index=7),
        skip_existing=True,
        embeddings_enabled=True,
    )
    assert decision.action == "resume"
    assert decision.start_chunk_index == 8

    decision = ingest_run.decide_ingest_behavior(
        ingest_run.IngestStateRow(version_id="v1", status="failed", last_chunk_index=3),
        skip_existing=True,
        embeddings_enabled=False,
    )
    assert decision.action == "resume"
    assert decision.start_chunk_index == 4


def test_is_valid_ingest_transition_contract():
    assert ingest_run.is_valid_ingest_transition(None, "discovered")
    assert ingest_run.is_valid_ingest_transition("discovered", "parsed")
    assert ingest_run.is_valid_ingest_transition("indexed_bm25", "embedded")
    assert ingest_run.is_valid_ingest_transition("embedded", "complete")
    assert ingest_run.is_valid_ingest_transition("failed", "discovered")
    assert ingest_run.is_valid_ingest_transition("complete", "discovered")

    assert not ingest_run.is_valid_ingest_transition(None, "parsed")
    assert not ingest_run.is_valid_ingest_transition("parsed", "discovered")
    assert not ingest_run.is_valid_ingest_transition("complete", "indexed_bm25")
    assert not ingest_run.is_valid_ingest_transition("embedded", "parsed")


def test_restart_resume_matches_uninterrupted(monkeypatch):
    text = ingest_run.DiscoveredText(
        author_id="a1",
        work_id="a1.w1",
        version_id="a1.w1.v1-ara1",
        repo_path="data/a1/w1/v1-ara1.mARkdown",
        abs_path=ingest_run.Path("fake.mARkdown"),
        is_pri=True,
        lang="ara",
    )

    active = {
        "state": {},
        "phase": "resume_first",
        "bulk_calls_in_phase": 0,
    }
    sent_ids: dict[str, list[str]] = {"resume_first": [], "resume_second": [], "control": []}

    def fake_get_ingest_state(_engine, version_id: str):
        return active["state"].get(version_id)

    def fake_set_ingest_state(_engine, version_id: str, status: str, *, last_chunk_index=None, error_message=None):
        current = active["state"].get(version_id)
        current_status = current.status if current else None
        assert ingest_run.is_valid_ingest_transition(current_status, status)
        next_last_chunk = last_chunk_index if last_chunk_index is not None else (current.last_chunk_index if current else None)
        active["state"][version_id] = ingest_run.IngestStateRow(
            version_id=version_id,
            status=status,
            last_chunk_index=next_last_chunk,
        )

    def fake_os_bulk_index(docs: list[dict]):
        active["bulk_calls_in_phase"] += 1
        ids = [d["chunk_id"] for d in docs]
        sent_ids[active["phase"]].extend(ids)
        if active["phase"] == "resume_first" and active["bulk_calls_in_phase"] == 2:
            raise RuntimeError("simulated interruption")

    monkeypatch.setattr(ingest_run, "get_engine", lambda: object())
    monkeypatch.setattr(ingest_run, "ensure_write_index_target", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "_load_curated_tags", lambda: set())
    monkeypatch.setattr(ingest_run, "load_metadata", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(ingest_run, "discover_200_pri_arabic", lambda *_args, **_kwargs: [text])
    monkeypatch.setattr(ingest_run, "upsert_author", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "upsert_work", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "upsert_version", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "upsert_chunks_batch", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "set_chunk_links", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ingest_run, "get_ingest_state", fake_get_ingest_state)
    monkeypatch.setattr(ingest_run, "set_ingest_state", fake_set_ingest_state)
    monkeypatch.setattr(ingest_run, "os_bulk_index", fake_os_bulk_index)
    monkeypatch.setattr(ingest_run, "sha256_file", lambda *_args, **_kwargs: "checksum")
    monkeypatch.setattr(ingest_run, "read_text_file", lambda *_args, **_kwargs: "######OpenITI#\nalpha beta gamma delta epsilon zeta")
    monkeypatch.setattr(ingest_run, "normalize_arabic_script", lambda text: " ".join(text.splitlines()[1].split()))
    monkeypatch.setattr(ingest_run, "tqdm", lambda x, **_kwargs: x)

    monkeypatch.setattr(ingest_run, "EMBEDDINGS_ENABLED", False)
    monkeypatch.setattr(ingest_run, "SKIP_EXISTING", True)
    monkeypatch.setattr(ingest_run, "CHUNK_TARGET_WORDS", 2)
    monkeypatch.setattr(ingest_run, "CHUNK_MAX_OVERLAP_WORDS", 0)
    monkeypatch.setattr(ingest_run, "OS_BULK_BATCH", 1)

    monkeypatch.setenv("CORPUS_ROOT", ".")

    ingest_run.run()
    interrupted_state = active["state"][text.version_id]
    assert interrupted_state.status == "failed"
    assert interrupted_state.last_chunk_index == 0

    active["phase"] = "resume_second"
    active["bulk_calls_in_phase"] = 0
    ingest_run.run()

    assert f"{text.version_id}::0" not in sent_ids["resume_second"]
    assert active["state"][text.version_id].status == "complete"

    active["phase"] = "control"
    active["bulk_calls_in_phase"] = 0
    active["state"] = {}
    ingest_run.run()

    resumed_final = set(sent_ids["resume_first"] + sent_ids["resume_second"])
    control_final = set(sent_ids["control"])
    assert resumed_final == control_final
