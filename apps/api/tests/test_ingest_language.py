from __future__ import annotations

import os
from pathlib import Path
import sys
import types

# Keep ingest unit tests lightweight by stubbing this optional heavy dependency.
if "sentence_transformers" not in sys.modules:
    stub = types.ModuleType("sentence_transformers")
    stub.SentenceTransformer = object
    sys.modules["sentence_transformers"] = stub

from app.ingest import run as ingest_run


def _fixture_corpus_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "milestone7_corpus" / "RELEASE"


def test_load_metadata_normalizes_language_aliases():
    corpus_root = _fixture_corpus_root()
    by_path, _ = ingest_run.load_metadata(corpus_root, curated_tags=set())

    assert by_path["data/a1/w1/v1.ara1.mARkdown"]["lang"] == "ar"
    assert by_path["data/a2/w2/v2.eng1.mARkdown"]["lang"] == "en"


def test_discovery_includes_two_languages_when_available(monkeypatch):
    corpus_root = _fixture_corpus_root()
    by_path, _ = ingest_run.load_metadata(corpus_root, curated_tags=set())

    monkeypatch.setattr(ingest_run, "DEFAULT_ONLY_PRI", False)
    monkeypatch.setattr(ingest_run, "DEFAULT_LANGS", ["ar", "en", "fa"])

    discovered = ingest_run.discover_200_pri_arabic(corpus_root, target_works=2, metadata_by_path=by_path)
    langs = {d.lang for d in discovered}

    assert len(discovered) == 2
    assert {"ar", "en"}.issubset(langs)


def test_discovery_logs_and_keeps_unknown_languages(monkeypatch, caplog):
    corpus_root = _fixture_corpus_root()
    by_path, _ = ingest_run.load_metadata(corpus_root, curated_tags=set())

    monkeypatch.setattr(ingest_run, "DEFAULT_ONLY_PRI", False)
    monkeypatch.setattr(ingest_run, "DEFAULT_LANGS", ["ar", "en"])

    discovered = ingest_run.discover_200_pri_arabic(corpus_root, target_works=3, metadata_by_path=by_path)

    assert any(d.lang == "unknown" for d in discovered)
    assert "missing/unmapped" in caplog.text


def test_discovery_can_use_prebuilt_index(monkeypatch):
    corpus_root = _fixture_corpus_root()
    out_json = Path(os.getenv("TEMP", ".")) / "openiti_discovery_index.pytest.v1.json"
    if out_json.exists():
        try:
            out_json.unlink()
        except PermissionError:
            pass
    ingest_run.build_discovery_index(corpus_root, out_json, curated_tags=set())

    try:
        monkeypatch.setattr(ingest_run, "DISCOVERY_INDEX_PATH", str(out_json))
        index_entries = ingest_run.load_discovery_index(corpus_root)
        discovered = ingest_run.discover_200_pri_arabic(
            corpus_root,
            target_works=10,
            discovery_index_entries=index_entries,
            metadata_by_path=None,
        )

        repo_paths = {d.repo_path for d in discovered}
        assert "data/a1/w1/v1.ara1.mARkdown" in repo_paths
        assert "data/a3/w3/v3.zzz1.mARkdown" in repo_paths
    finally:
        if out_json.exists():
            try:
                out_json.unlink()
            except PermissionError:
                pass
