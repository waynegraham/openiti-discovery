## Developer Onboarding

This document explains how to set up a local development environment for OpenITI Discovery, understand the moving parts, and make safe changes without breaking the corpus or search stack.

It assumes basic familiarity with Docker, Python, and JavaScript.

---

## What This Project Is (and Is Not)

### This project is

* A local-first research platform for discovering texts in the OpenITI corpus
* A hybrid search system (BM25 + semantic vectors)
* A system designed to evolve without redoing everything from scratch

### This project is not

* A text editing platform
* A TEI or manuscript transcription system
* A lightweight demo with no consequences

You are working with **BILLIONS** of words. Be deliberate.

---

## Prerequisites

### Required

* Docker Engine ≥ 29.x
* Docker Compose plugin
* Git
* At least 16 GB RAM (32+ strongly recommended for ingest)

### Optional but Helpful

* NVIDIA GPU (for embedding generation)
* curl or similar HTTP client
* A text editor that handles large files gracefully

---

## Repository Layout (Expected)

```text
.
├── apps/
│   ├── api/                 # FastAPI backend
│   └── frontend/            # Next.js frontend
├── docs/                    # Architecture, ingestion, onboarding
├── opensearch/
│   └── templates/           # Index templates
├── data/
│   └── artifacts/           # Logs, checkpoints, derived data
├── docker-compose.yml
├── README.md
└── RELEASE/                 # OpenITI corpus (local clone)
```

> ⚠️ The `RELEASE/` directory is not part of this repository and must be cloned separately.

---

## Initial Setup

### 1. Clone the Repositories

```bash
git clone https://github.com/waynegraham/openiti-discovery.git
cd openiti-discovery

git clone https://github.com/OpenITI/RELEASE.git
```

The corpus should live at:

```bash
./RELEASE
```

It will be mounted read-only into containers.

---

## 2. Start Core Services

Start only what you need for development:

```bash
docker compose up -d postgres opensearch qdrant api frontend
```

Verify:

* API: http://localhost:8000
* Frontend: http://localhost:3000
* OpenSearch: http://localhost:9200

---

## OpenSearch Setup (One-Time)

### Apply Index Template

```bash
curl -X PUT http://localhost:9200/_index_template/openiti_chunks_template_v1 \
  -H "Content-Type: application/json" \
  -d @opensearch/templates/openiti_chunks_template.json
```

### Create Initial Index

```bash
curl -X PUT http://localhost:9200/openiti_chunks_v1
```

Attach alias and write target:

```bash
curl -X POST http://localhost:9200/_aliases \
  -H "Content-Type: application/json" \
  -d '{"actions":[{"add":{"index":"openiti_chunks_v1","alias":"openiti_chunks","is_write_index":true}}]}'
```

All search code should target the alias, never the concrete index.

---

## Running Ingest (Safely)

### ⚠️ Do NOT run a full ingest casually

A full ingest can take many hours and generate millions of records.

### Development Ingest (Recommended)

Use subset mode:

```
docker compose --profile ingest run --rm ingest
```

With environment variables set (via `.env` or shell):

```env
INGEST_MODE=subset
INGEST_ONLY_PRI=true
INGEST_LANGS=ara
INGEST_WORK_LIMIT=200
EMBEDDING_DEVICE=cpu
```

This gives you:

* realistic data
* fast iteration
* minimal pain

---

## Development Workflow

### Backend (FastAPI)

* Code lives in `apps/api/`
* Entry point: `app.main:app`
* Uses environment variables for all configuration
* Avoid hardcoding index names or paths

Typical changes:

* search query logic
* ranking / fusion logic
* metadata hydration
* API response shaping

Restart API after changes:

```bash
docker compose restart api
```

---

## Frontend (Next.js)

* Code lives in `apps/frontend/`
* Runs in dev mode by default
* Talks to API via `NEXT_PUBLIC_API_BASE_URL`

Typical changes:

* search UI
* result display
* reading view
* filters and facets

Hot reload should work automatically.

---

## Making Changes Safely

### Analyzer or Mapping Changes

> Never modify an existing index in place.

Correct process:

1. Create a new index version (openiti_chunks_v2)
2. Reindex data
3. Switch alias
4. Delete old index (optional)

This avoids downtime and broken queries.

---

### Chunking or Normalization Changes

These affect:

* passage IDs
* embeddings
* reuse detection

Assume you must reindex if you change:

* chunk size
* normalization rules
* passage ID logic

Do not mix chunking strategies in one index.

---

### Embedding Model Changes

Embeddings can be regenerated independently.

You may:

* reuse OpenSearch index
* recreate only the Qdrant collection

But you must keep:

* embedding dimension
* distance metric consistent within a collection.

---

## Debugging Tips

### OpenSearch

* Use OpenSearch Dashboards if enabled
* Inspect analyzers with `_analyze`
* Check mappings before ingest

### PostgreSQL

* Verify counts:
    * works
    * versions
    * passages
* Check ingest checkpoints before rerunning jobs

### Qdrant

* Test nearest-neighbor queries manually
* Confirm vector count matches passage count

---

## Common Mistakes

| Mistake                         | Why It’s Bad             |
| ------------------------------- | ------------------------ |
| Running full ingest by accident | Time + disk explosion    |
| Editing analyzers in-place      | Corrupts index semantics |
| Using `latest` image tags       | Non-reproducible builds  |
| Changing chunking mid-ingest    | Broken IDs and resume    |
| Hardcoding paths                | Breaks Docker isolation  |

## Code Style and Expectations

* Prefer clarity over cleverness
* Document assumptions
* Keep ingestion deterministic
* Assume someone else will read your code later
* Treat corpus data as immutable

---

## Getting Help

If something seems unclear:

1. Read `docs/architecture.md`
2. Read `docs/ingestion.md`
3. Check the OpenITI RELEASE README
4. Then ask a specific question

Vague problems get vague answers.

---

## Final Notes

This project is designed for:

* long-running jobs
* large data
* iterative improvement

Small shortcuts tend to become permanent liabilities.

Build like you’ll be maintaining this in three years.

Welcome aboard.
