from __future__ import annotations

from app.clients import opensearch_client as osc


class _FakeIndices:
    def __init__(self) -> None:
        self.indexes: set[str] = set()
        self.aliases: dict[str, dict[str, bool | None]] = {}
        self.created: list[str] = []
        self.updated_alias_bodies: list[dict] = []

    def exists(self, index: str) -> bool:
        return index in self.indexes

    def exists_alias(self, name: str) -> bool:
        return name in self.aliases

    def get_alias(self, name: str) -> dict:
        out: dict[str, dict] = {}
        for idx, cfg in self.aliases.get(name, {}).items():
            out[idx] = {"aliases": {name: {"is_write_index": cfg}}}
        return out

    def create(self, index: str, ignore: int = 400) -> dict:
        _ = ignore
        self.indexes.add(index)
        self.created.append(index)
        return {"acknowledged": True}

    def update_aliases(self, body: dict) -> dict:
        self.updated_alias_bodies.append(body)
        for action in body.get("actions", []):
            add = action.get("add")
            if not add:
                continue
            alias = add["alias"]
            index = add["index"]
            is_write_index = add.get("is_write_index")
            self.aliases.setdefault(alias, {})[index] = is_write_index
        return {"acknowledged": True}


class _FakeClient:
    def __init__(self) -> None:
        self.indices = _FakeIndices()


def test_ensure_write_index_target_bootstraps_alias(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(osc, "get_opensearch", lambda: client)

    target = osc.ensure_write_index_target("openiti_chunks")

    assert target == "openiti_chunks"
    assert client.indices.created == ["openiti_chunks_v1"]
    assert client.indices.aliases["openiti_chunks"]["openiti_chunks_v1"] is True


def test_ensure_write_index_target_bootstraps_versioned_index(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(osc, "get_opensearch", lambda: client)

    target = osc.ensure_write_index_target("openiti_chunks_v3")

    assert target == "openiti_chunks_v3"
    assert client.indices.created == ["openiti_chunks_v3"]
    assert client.indices.updated_alias_bodies == []
