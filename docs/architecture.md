# Architecture

This document describes the system architecture for **OpenITI Discovery**, including data flow, component responsibilities, and design decisions. The goal is to make the system understandable, extensible, and safe to evolve as the corpus and features grow.

---

## Design Principals

1. **Corpus-first design**
The OpenITI RELEASE corpus structure and metadata drive the data model and indexing strategy.
2. **Local-first, deployable later**
All components run locally via Docker Compose, with no hard dependency on cloud services.
3. **Hybrid retrieval by default**
Lexical (BM25) and semantic (vector) search are treated as complementary, not competing.
4. **Version-aware text access**
Works, versions, and passages are distinct entities. PRI versions are first-class but not exclusive.
5. **Index evolution without downtime**
Search indices are versioned and accessed via aliases.

---

## High-Level Architecture

```text
┌──────────────────┐
│  OpenITI RELEASE │
│  (Git repository)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Ingest Pipeline │
│  (Python)        │
└─────┬────┬───────┘
      │    │
      │    ├───────────────┐
      ▼                    ▼
┌───────────────┐   ┌────────────────┐
│ PostgreSQL    │   │ OpenSearch     │
│ (metadata)    │   │ (BM25 search)  │
└───────────────┘   └────────────────┘
        │                    │
        └──────────┬─────────┘
                   ▼
           ┌────────────────┐
           │ Qdrant          │
           │ (vector search) │
           └────────────────┘
                   │
                   ▼
           ┌────────────────┐
           │ FastAPI        │
           │ (search API)   │
           └────────────────┘
                   │
                   ▼
           ┌────────────────┐
           │ Next.js UI     │
           │ (client)       │
           └────────────────┘
```

---

## Core Components

### OpenITI RELEASE Corpus

* Authoritative source of text and metadata
* Organized by author → work → version
* Uses OpenITI mARkdown for structural annotation
* Mounted read-only into containers

---

## Ingest Pipeline

This is preliminary and will eventually get migrated into a more robust system.

**Language**: Python
**Execution**: One-shot container (`docker compose --profile ingest`)

### Responsibilities

* Load metadata CSVs into PostgreSQL
* Walk corpus directory structure
* Parse OpenITI mARkdown
* Normalize Arabic-script text
* Chunk text into passages (~300 words)
* Generate embeddings (CPU or GPU)
* Index passages into OpenSearch and Qdrant

### Key Properties

* **Idempotent**: supports restart via checkpoints
* **Configurable**: full corpus or subset
* **Parallelizable**: CPU multiprocessing
* **Version-aware**: preserves PRI and alternates

---

## PostgreSQL

**Role**: Canonical relational store.

**Stores**

* Authors
* Works
* Versions
* Passage metadata (IDs, offsets, structure)
* Ingest state and checkpoints
* Reuse graph edges (when enabled)

**Purpose**

* Authoritative metadata source
* Stable identifiers for citations and links
* Query-time joins for faceting and display

---

## OpenSearch

**Role**: Lexical retrieval and filtering

**Indexed Data**

* Passage text (multi-field analyzers)
* Work/version/author identifiers
* Language and version flags
* Titles and structural labels

**Features Used**

* BM25 scoring
* Custom Arabic-script analyzers
* Highlighting
* Faceted filtering
* Index aliases for safe upgrades

Each passage is indexed as a single document.

---

## Qdrant

**Role**: Vector similarity search

**Stored Data**

* Passage embeddings
* Passage identifiers (matching OpenSearch docs)

**Usage**

* Semantic concept search
* Similar-passage discovery
* Backstop for low-recall lexical queries

Qdrant is queried in parallel with OpenSearch during hybrid retrieval.

---

## FastAPI Backend

**Role**: Search orchestration and API

**Responsibilities**

* Accept search and browse requests
* Execute lexical queries in OpenSearch
* Execute vector queries in Qdrant
* Fuse results (hybrid ranking)
* Fetch metadata from PostgreSQL
* Return normalized API responses

The backend contains no UI logic and minimal presentation concerns.

---

## Next.js Frontend

**Role**: User interface

**Features**

* Unified search interface
* Faceted filtering
* Passage-level result display
* Jump-to-context reading
* Version switching

The frontend is intentionally thin and stateless.

---

## Data Model Overview

### Entities

```pgsql
Author
 └── Work
      └── Version
           └── Passage (chunk)
```

* **Author**: canonical name, death date
* **Work**: conceptual text entity
* **Version**: specific digital text (PRI or alternate)
* **Passage**: retrieval and reading unit

Passages are immutable once indexed

---

## Passage Chunking Strategy

* Target size: ~300 words
* Prefer structural boundaries when available
* Fallback to fixed-size segmentation
* Neighbor pointers stored for reading flow

Chunking is designed to balance:

* search precision
* semantic embedding quality
* readable context size

---

## Search Flow

1. User submits query
2. Backend runs:
    * BM25 search in OpenSearch
    * Vector search in Qdrant
3. Results are fused (rank fusion)
4. Metadata is hydrated from PostgreSQL
5. Final ranked list returned to UI

---

## Index Versioning Strategy

* Indices are versioned (`openiti_chunks_vN`)
* A stable alias (`openiti_chunks`) points to the active index
* Reindexing is done offline
* Alias is switched atomically

This allows analyzer and schema changes without downtime.

---

## Extensibility

Planned or optional extensions:

* Phrase reuse detection (reuse graph)
* Named entity extraction and faceting
* Passage comparison across versions
* User annotations and saved queries

The architecture isolates these features to avoid core redesign.

---

## Non-Goals

* Full TEI support
* Real-time collaborative editing
* Inline text correction or emendation

These are intentionally out of scope.

---

## Failure Modes and Mitigations

| Risk                 | Mitigation              |
| -------------------- | ----------------------- |
| Large ingest failure | Checkpointed ingestion  |
| Analyzer change      | Versioned indices       |
| Embedding drift      | Regenerate vectors only |
| Corpus updates       | Incremental re-ingest   |

---

## Summary 

The OpenITI Discovery architecture is designed to:

* respect the structure and scale of the OpenITI corpus
* support serious research workflows
* evolve safely as methods and expectations change

It favors clarity, explicit modeling, and recoverable processes over cleverness.
---

## Search API Addendum (2026-02-08)

To align architecture with current retrieval behavior:

- FastAPI exposes `POST /embed` (batch-first) for query/passage embeddings.
- `GET /search` returns both `requested_mode` and `effective_mode`.
- Hybrid mode uses classic RRF fusion with configurable `rrf_k` and candidate depth.
- If Qdrant is unavailable in hybrid requests, API degrades to BM25 (`effective_mode=bm25`) and returns warning `qdrant_unavailable_fallback_bm25`.
- Facets are computed and returned only in BM25 effective mode.
- Highlight output is sanitized to allow `<em>` only.
- Canonical text normalization is shared between ingest and embedding/search via config.
