# OpenITI Discovery

A local-first discovery stack for the OpenITI RELEASE corpus, combining full-text (BM25) search with vector search and a lightweight reading UI. The repo is structured for Docker-first development and can scale toward hosted deployment.

---

## Current State (Feb 2, 2026)

* FastAPI API with health and search endpoints
* BM25 search in OpenSearch, vector search in Qdrant, and a simple hybrid fusion mode
* One-shot ingest runner that discovers OpenITI texts, chunks them, and indexes BM25 + embeddings
* Next.js frontend with landing and search UI (currently using mock data; API wiring is pending)

---

## Architecture Overview

| Component | Purpose | Version | Notes |
| --- | --- | --- | --- |
| PostgreSQL | Canonical metadata, works, versions, chunks | 18 | In Docker Compose |
| OpenSearch | Lexical search, filters, highlights | 3.4.0 | ICU analysis plugin baked in |
| Qdrant | Vector search | 1.16 | HTTP + gRPC exposed |
| FastAPI | API + ingest runtime | Python 3.12 | Uvicorn dev server |
| Next.js | Frontend UI | 16.1.4 | React 19.2.3 |
| Redis | Optional cache | 8 | Profile `cache` |
| Docker Compose | Local orchestration | - | Profiles: `dashboards`, `cache`, `ingest` |

---

## Repository Structure

```text
.
|-- apps/
|   |-- api/                 # FastAPI backend + ingest runner
|   |-- frontend/            # Next.js frontend
|-- opensearch/
|   |-- templates/           # Index templates
|-- data/
|   |-- artifacts/           # Derived data, checkpoints
|-- docker-compose.yml
|-- README.md
|-- RELEASE/                 # OpenITI corpus (clone or submodule)
```

---

## Requirements

* Docker Engine >= 29.x
* Docker Compose plugin
* Recommended: 32 GB RAM for full corpus ingest
* Optional: NVIDIA GPU for faster embedding generation

If you run the frontend locally outside Docker, use Node 20 + pnpm.

---

## Getting Started

### 1. Clone Repository and Corpus

```bash
git clone https://github.com/waynegraham/openiti-discovery.git
cd openiti-discovery
git clone https://github.com/OpenITI/RELEASE.git
```

The OpenITI RELEASE repo must exist at `./RELEASE` so it can be mounted into containers.

### 2. Configure Environment

```bash
cp .env.example .env
```

Set `OPENSEARCH_INITIAL_ADMIN_PASSWORD` and any ingest controls you want to override.

### 3. Start Core Services

```bash
docker compose up -d
```

Optional profiles:

* Dashboards: `docker compose --profile dashboards up -d`
* Redis cache: `docker compose --profile cache up -d`

### 4. Run Database Migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Create OpenSearch Indices

Apply the template:

```bash
curl -X PUT http://localhost:9200/_index_template/openiti_chunks_template \
  -H "Content-Type: application/json" \
  -d @opensearch/templates/openiti_chunks_template.json
```

Create an initial index (the template adds the `openiti_chunks` alias automatically):

```bash
curl -X PUT http://localhost:9200/openiti_chunks_v1
```

---

## Ingesting the Corpus

The ingestion pipeline runs as a one-shot container that uses the API image.

```bash
docker compose --profile ingest run --rm ingest
```

Ingest behavior is controlled via environment variables (see `.env.example` and `docker-compose.yml`):

* `INGEST_MODE`: reserved for future runners (currently unused)
* `INGEST_ONLY_PRI`: `true` or `false`
* `INGEST_LANGS`: comma-separated tags (currently the ingest runner only processes `ara`)
* `INGEST_WORK_LIMIT`: limit number of works (default is 200 when unset)
* `CHUNK_TARGET_WORDS`: default 300
* `EMBEDDINGS_ENABLED`: `true` or `false`
* `EMBEDDING_DEVICE`: `cpu` or `cuda`
* `EMBEDDING_MODEL`: default multilingual MiniLM

---

## API Endpoints (Current)

* `GET /health` -> service health summary
* `GET /search` -> query OpenSearch/Qdrant
* `GET /chunks/{chunk_id}` -> chunk with neighbors

Search modes:

* `mode=bm25` (default)
* `mode=vector` (requires `vector` parameter)
* `mode=hybrid` (requires `vector` parameter)

The vector parameter is a temporary hook until a server-side embedding endpoint is added.

---

## Local URLs

* Frontend: http://localhost:3000
* API: http://localhost:8000
* API docs (Swagger): http://localhost:8000/docs
* API docs (ReDoc): http://localhost:8000/redoc
* OpenSearch API: http://localhost:9200
* OpenSearch Dashboards: http://localhost:5601 (profile `dashboards`)
* Qdrant API: http://localhost:6333
* Qdrant UI: http://localhost:6333/dashboard

---

## Index Versioning

Indices follow `openiti_chunks_v*`. The template assigns the `openiti_chunks` alias to each created index, enabling safe reindexing and schema changes.

---

## Licensing

The OpenITI RELEASE dataset is licensed under CC BY-NC-SA 4.0. This project does not include corpus data and does not alter the original licensing terms.

You are responsible for complying with the OpenITI license when deploying or redistributing derived indexes.

---

## Status

Active development. Expect iteration in schema, analyzers, ingest logic, and UI wiring.

---

## Acknowledgements

* OpenITI Project and contributors
* KITAB / AKU initiatives
* OpenSearch, Qdrant, and PostgreSQL communities
