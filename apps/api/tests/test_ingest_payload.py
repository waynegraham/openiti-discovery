from __future__ import annotations

from pathlib import Path
import sys
import types

# Keep ingest unit tests lightweight by stubbing this optional heavy dependency.
if "sentence_transformers" not in sys.modules:
    stub = types.ModuleType("sentence_transformers")
    stub.SentenceTransformer = object
    sys.modules["sentence_transformers"] = stub

from app.ingest.run import DiscoveredText, build_vector_payload


def test_build_vector_payload_includes_filter_contract_fields():
    text = DiscoveredText(
        author_id="a1",
        work_id="a1.w1",
        version_id="a1.w1.v1",
        repo_path="data/a1/w1/v1.mARkdown",
        abs_path=Path(__file__),  # unused by helper
        is_pri=True,
        lang="ara",
    )
    meta = {
        "period": "Abbasid",
        "region": ["Baghdad"],
        "tags": ["GAL@adab"],
        "version_label": "PRI",
    }

    payload = build_vector_payload(
        chunk_id="a1.w1.v1::0",
        chunk_index=0,
        t=text,
        meta=meta,
    )

    assert payload["period"] == "Abbasid"
    assert payload["region"] == ["Baghdad"]
    assert payload["tags"] == ["GAL@adab"]
    assert payload["version_label"] == "PRI"
    assert payload["is_pri"] is True
