from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    postgres: bool
    opensearch: bool
    qdrant: bool


class FacetBucket(BaseModel):
    key: str
    label: str
    count: int


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    source: dict = Field(default_factory=dict)
    highlight: dict | None = None


class SearchResponse(BaseModel):
    query: str
    requested_mode: str
    effective_mode: str
    warnings: list[str] = Field(default_factory=list)
    total: int
    page: int
    size: int
    results: list[SearchHit]
    embedding_model: str
    embedding_model_version: str
    normalization_version: str
    facets: dict[str, list[FacetBucket]] = Field(default_factory=dict)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)
    input_type: str = Field(pattern="^(query|passage)$")


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    embedding_model: str
    embedding_model_version: str
    normalization_version: str


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
