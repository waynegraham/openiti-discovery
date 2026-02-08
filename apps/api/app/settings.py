from pydantic_settings import BaseSettings, SettingsConfigDict

from .runtime_config import search_runtime


_runtime = search_runtime()
_search_cfg = (_runtime.get("search") or {}) if isinstance(_runtime, dict) else {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres
    DATABASE_URL: str

    # OpenSearch
    OPENSEARCH_URL: str = "http://opensearch:9200"
    OPENSEARCH_INDEX_CHUNKS: str = "openiti_chunks"  # alias preferred

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "openiti_chunks"

    # Search behavior
    DEFAULT_SIZE: int = int(_search_cfg.get("default_page_size", 20))
    DEFAULT_PRI_ONLY: bool = True

    # Basic guardrails
    MAX_SIZE: int = int(_search_cfg.get("max_page_size", 100))


settings = Settings()
