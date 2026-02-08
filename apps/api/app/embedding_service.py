from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from .runtime_config import normalization_version, search_runtime
from .text_normalization import normalize_arabic_script

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


def _embedding_cfg() -> dict:
    return (search_runtime().get("embedding") or {}) if search_runtime() else {}


def embedding_model_name() -> str:
    return str(
        _embedding_cfg().get(
            "model_name",
            os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
        )
    )


def embedding_model_version() -> str:
    return str(_embedding_cfg().get("model_version", "unknown"))


def _device() -> str:
    return os.getenv("EMBEDDING_DEVICE", "cpu").lower()


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(embedding_model_name(), device=_device())


def _prefixed_text(text: str, input_type: str) -> str:
    norm = normalize_arabic_script(text)
    if input_type == "query":
        return f"query: {norm}"
    return f"passage: {norm}"


def encode_texts(texts: list[str], input_type: str) -> list[list[float]]:
    model = get_embedding_model()
    prepared = [_prefixed_text(t, input_type) for t in texts]
    vectors = model.encode(
        prepared,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embedding_trace() -> dict[str, str]:
    return {
        "embedding_model": embedding_model_name(),
        "embedding_model_version": embedding_model_version(),
        "normalization_version": normalization_version(),
    }
