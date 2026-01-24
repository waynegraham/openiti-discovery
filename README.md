# OpenITI Discovery

A local-first, extensible full-text and semantic discovery platform for the **OpenITI RELEASE** corpus of Islamicate texts in **Arabic**, **Persian**, and O**ttoman Turkish**.

The project provides hybrid lexical + semantic search, metadata-driven filtering, and passage-level navigation over the entire OpenITI corpus, with an architecture designed to scale from local research use to public deployment.

---

## Project Goals

* Full-corpus indexing of the OpenITI RELEASE repository
* High-quality full-text search for Arabic-script languages
* Semantic (embedding-based) concept search
* Passage-level retrieval with jump-to-context reading
* Version-aware text discovery (PRI vs alternate versions)
* Support for phrase reuse and bibliographic research workflows
* Local development via Docker Compose, with a clear path to hosting

---

## Corpus

This project targets the [OpenITI RELEASE](https://github.com/OpenITI/RELEASE) repository.

The corpus consists of:

* Thousands of works and versions
* Billions of words
* Structured OpenITI mARkdown
* Rich metadata (authors, dates, genres, collections, etc.)

The corpus itself is not included in this repository. 

> You must clone it separately and mount it into the stack.

---

## Architecture Overview

### Core Components

| Component            | Purpose                                               |
| -------------------- | ----------------------------------------------------- |
| **PostgreSQL 18**    | Canonical metadata, works, versions, passage pointers |
| **OpenSearch 3**     | Lexical (BM25) search, filtering, highlighting        |
| **Qdrant**           | Vector search for semantic retrieval                  |
| **FastAPI**          | Search orchestration, hybrid ranking, API             |
| **Next.js (≥16)**    | User interface (search + reading views)               |
| **Redis** (optional) | Caching, ingest checkpoints                           |
| **Docker Compose**   | Local orchestration                                   |

---

## Data Model (Conceptual)

```text
Author
 └── Work
      └── Version (PRI or alternate)
            └── Passage / Chunk (~300 words)
```

Passages are the primary retrieval unit for:

* search results
* semantic similarity
* reuse detection
* reading navigation

---

## Search Strategy

### Hybrid Retrieval (Default)

* Lexical search (BM25) via OpenSearch
* Semantic search (embeddings) via Qdrant
* Results fused at query time

This supports:

* concept search
* named entity search
* phrase and formulaic reuse
* bibliographic hunting

### Arabic-Script Optimization

Custom OpenSearch analyzers are used to handle:

* Arabic orthographic variation
* Persian letter normalization
* Ottoman Turkish (Arabic-script) text
* Optional ICU Unicode folding

Indexing uses **multi-field mappings** to balance recall and precision:

* normalized fields for general search
* no-stem / exact fields for names and phrases

---

## Repository Structure

```text
.
├── apps/
│   ├── api/                # FastAPI backend
│   └── frontend/           # Next.js frontend
├── opensearch/
│   └── templates/          # Index templates
├── data/
│   └── artifacts/          # Derived data, checkpoints
├── docker-compose.yml
├── README.md
└── RELEASE/                # OpenITI corpus (git submodule or local clone)
```

---

## Requirements

### Host System

* Docker Engine >= 29.x
* Docker Compose plugin
* Recommended: >= 32GB RAM for full corpus indexing
* Optional: NVIDIA GPU for faster embedding generation

### External Dependencies 

* OpenITI RELEASE corpus (cloned locally)
* Internet access for embedding model download (once)

---

## Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/waynegraham/openiti-discovery.git
cd openiti-discovery
git clone https://github.com/OpenITI/RELEASE.git
```

### 2. Start Core Services

```bash
docker compose up -d
```

### 3. Create OpenSearch Indices

Apply the index template (once):

```bash
curl -X PUT http://localhost:9200/_index_template/openiti_chunks_template_v1 \
  -H "Content-Type: application/json" \
  -d @opensearch/templates/openiti_chunks_template.json
```

Create the initial index:

```bash
curl -X PUT http://localhost:9200/openiti_chunks_v1
```

---

## Ingesting the Corpus

The ingestion pipeline is run as a one-shot container.

### Full Corpus Ingest

```bash
docker compose --profile ingest run --rm ingest
```

### Development/Subset Ingest

Control ingest behavior via environment variables:

```env
INGEST_MODE=subset
INGEST_ONLY_PRI=true
INGEST_LANGS=ara,fas
INGEST_WORK_LIMIT=500
EMBEDDING_DEVICE=cpu
```

This allows fast iteration without indexing the full corpus.

---

## Embeddings

* Embeddings are generated per passage
* GPU acceleration is supported but optional
* CPU-only mode is supported for development
* Vector storage is handled by Qdrant

Embedding configuration is controlled via environment variables.

---

## User Iterface

The frontend provides:

* Unified search box (hybrid by default)
* Faceted filtering (author, date, language, version)
* Snippet view with highlighted matches
* Passage-level jump-to-context reading
* Version awareness (`PRI` vs alternates)

Full document rendering is supported incrementally via passage navigation.

---

## Index Versioning

Indices are versioned:

```python
openiti_chunks_v1
openiti_chunks_v2
...
```

A stable alias (`openiti_chunks`) always points to the active index, enabling:

* safe reindexing
* analyzer changes
* schema evolution

---

## Licensing

The OpenITI RELEASE dataset is licensed under **CC BY-NC-SA 4.0**. This project contains **no corpus data** and does not alter the original licensing terms.

You are responsible for complying with OpenITI’s license when deploying or redistributing derived indexes.

---

## Status

This project is under active development.

Expect:

* schema iteration
* analyzer tuning
* incremental feature expansion (reuse detection, entity extraction)
* things to break

---

## Acknowledgements

* OpenITI Project and contributors
* KITAB / AKU initiatives
* OpenSearch, Qdrant, PostgreSQL communities