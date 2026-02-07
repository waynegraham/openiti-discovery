# OpenITI Discovery

A local-first discovery stack for the OpenITI RELEASE corpus, combining full-text (BM25) search with vector search and a lightweight reading UI. The repo is structured for Docker-first development and can scale toward hosted deployment.

---

## Current State (Feb 7, 2026)

* FastAPI API with health and search endpoints
* BM25 search in OpenSearch, vector search in Qdrant, and a simple hybrid fusion mode
* One-shot ingest runner that discovers OpenITI texts, chunks them, and indexes BM25 + embeddings
* Next.js frontend with landing and search UI (currently using mock data; API wiring is pending)
* Paper-focused evaluation toolkit: query/qrels forms import, corpus-size planning, subset experiment runner, audit, qualitative case extraction, and table generation

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
* Optional: NVIDIA GPU for faster embedding generation (Windows/Linux only)

### Optional CUDA Support (Windows/Linux)

To use GPU embeddings:

* Windows: Docker Desktop with WSL2 GPU support and NVIDIA drivers installed.
* Linux: NVIDIA drivers + NVIDIA Container Toolkit.
* macOS: CUDA is not supported; use CPU mode.

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

### Build Images (CPU vs GPU)

Build CPU images (default API + ingest):

```bash
docker compose build api frontend
```

Build GPU images (CUDA API + ingest):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu build api_cuda
```

Run CPU API stack:

```bash
docker compose up -d api frontend
```

Run GPU API stack (Windows/Linux + NVIDIA):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d api_cuda frontend
```

When using `api_cuda`, point the frontend/API client to `http://localhost:8000` as usual.

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

Create an initial versioned index:

```bash
curl -X PUT http://localhost:9200/openiti_chunks_v2
```

Attach the stable alias and mark the write index:

```bash
curl -X POST http://localhost:9200/_aliases \
  -H "Content-Type: application/json" \
  -d '{"actions":[{"add":{"index":"openiti_chunks_v2","alias":"openiti_chunks","is_write_index":true}}]}'
```

---

## Ingesting the Corpus

The ingestion pipeline runs as a one-shot container that reuses the API image.

Build the image first (if needed):

```bash
docker compose build api
```

```bash
docker compose --profile ingest run --rm ingest
docker compose --profile ingest run --rm -e EMBEDDINGS_ENABLED=true -e EMBEDDING_DEVICE=cpu ingest
```

### GPU Ingest (Windows/Linux + NVIDIA)

Use the CUDA-enabled image and profile (requires Docker Compose with `--gpus` support):

Build the CUDA image first (if needed):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu build api_cuda
```

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm ingest_cuda
```

Quick GPU check:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm ingest_cuda nvidia-smi
```

If you want auto-detection, set `EMBEDDING_DEVICE=auto` in `.env` or pass it via `-e`.

Ingest behavior is controlled via environment variables (see `.env.example` and `docker-compose.yml`):

* `INGEST_MODE`: reserved for future runners (currently unused)
* `INGEST_ONLY_PRI`: `true` or `false`
* `INGEST_LANGS`: comma-separated tags (currently the ingest runner only processes `ara`)
* `INGEST_WORK_LIMIT`: limit number of works (default is 200 when unset)
* `CHUNK_TARGET_WORDS`: default 300
* `EMBEDDINGS_ENABLED`: `true` or `false`
* `EMBEDDING_DEVICE`: `cpu` or `cuda`
* `EMBEDDING_MODEL`: default multilingual MiniLM

Curated facet tags are managed in `curated_tags.txt`. For domain-expert editing instructions, see `docs/curated-tags.md`.

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

Indices follow `openiti_chunks_v*`. Use alias `openiti_chunks` for all reads/writes, and ensure exactly one backing index has `is_write_index=true`.

---

## Licensing

The OpenITI RELEASE dataset is licensed under CC BY-NC-SA 4.0. This project does not include corpus data and does not alter the original licensing terms.

You are responsible for complying with the OpenITI license when deploying or redistributing derived indexes.

---

## Status

Active development. Expect iteration in schema, analyzers, ingest logic, and UI wiring.

---

## Evaluation Workflow (Paper)

The API container includes a full reproducible workflow for conference/paper experiments.

### Core Pipeline

* `make eval-run` -> run retrieval configs (`baseline`, `normalized`, `variant_aware`, `full_pipeline`)
* `make eval-metrics` -> compute Table X + Table Y metrics
* `make eval-tables` -> render markdown tables and Table Z CSV
* `make eval-record` -> append run metadata to `data/eval/output/experiment_runs.csv`
* `make eval-all` -> run `eval-run`, `eval-metrics`, `eval-tables`, `eval-record`

### Query + Judgments Authoring

* `make eval-scaffold` -> generate placeholder `queries.placeholder.json` and `qrels.placeholder.json`
* `make eval-import-forms` -> convert expert CSV forms into `data/eval/queries.json` and `data/eval/qrels.json`
* Expert materials:
  * `docs/domain_expert_guidlines.md`
  * `data/eval/forms/queries_form.csv`
  * `data/eval/forms/qrels_form.csv`

### Corpus Sizing + Multi-Subset Runs

* `make eval-corpus-plan EVAL_TARGET_LINES=1000000,5000000,20000000`
  * estimates `INGEST_WORK_LIMIT` to hit target line counts
* `make eval-run-subsets EVAL_SUBSET_MANIFEST=/app/data/eval/subsets.sample.json`
  * runs ingest + eval for small/medium/full subsets from one manifest
  * can update `data/eval/scalability.json` with measured run paths and indexing time

### QA + Analysis Utilities

* `make eval-qrels-audit` -> consistency/completeness checks for queries and qrels
* `make eval-qualitative` -> baseline vs full-pipeline qualitative cases for error analysis
* `make eval-scalability-measure` -> measured scalability CSV including avg/p50/p95 latency

### Evaluation Data Location

All inputs/outputs live under `data/eval/`:

* Inputs: `queries.json`, `qrels.json`, `scalability.json`, `subsets.sample.json`
* Outputs: `output/runs`, `output/metrics`, `output/tables`, `output/experiment_runs.csv`, `output/audit`, `output/qualitative_cases.csv`

Placeholder dry-run example:

```bash
make eval-scaffold
make eval-all EVAL_QUERIES=/app/data/eval/queries.placeholder.json EVAL_QRELS=/app/data/eval/qrels.placeholder.json
```

---

## Acknowledgements

* OpenITI Project and contributors
* KITAB / AKU initiatives
* OpenSearch, Qdrant, and PostgreSQL communities
