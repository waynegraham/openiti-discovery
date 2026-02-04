from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    postgres: bool
    opensearch: bool
    qdrant: bool


class FacetBucket(BaseModel):
    key: str
    count: int


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    source: dict = Field(default_factory=dict)
    highlight: dict | None = None


class SearchResponse(BaseModel):
    query: str
    mode: str  # bm25 | vector | hybrid
    total: int
    page: int
    size: int
    results: list[SearchHit]
    facets: dict[str, list[FacetBucket]] = Field(default_factory=dict)


class ChunkResponse(BaseModel):
    chunk_id: str
    version_id: str
    work_id: str
    author_id: str
    chunk_index: int
    heading_text: str | None = None
    heading_path: list[str] | None = None
    text_raw: str
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None
