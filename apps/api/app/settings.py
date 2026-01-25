from pydantic_settings import BaseSettings, SettingsConfigDict


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
    DEFAULT_SIZE: int = 20
    DEFAULT_PRI_ONLY: bool = True

    # Basic guardrails
    MAX_SIZE: int = 100


settings = Settings()
