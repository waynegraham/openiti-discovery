# PostgreSQL Migration Spec

This migration spec is designed for:

* stable IDs from OpenITI metadata
* version-aware indexing (`PRI` vs alternates)
* chunk-level retrieval + reading navigation
* resumable ingestion with checkpoints
* future extensions (NER, reuse, additional metadata) without repainting the house

There are no ORM assumptions. You can implement this with Alembic, Prisma, Drizzle, plain SQL migrations, whatever.

---

## Conventions

### ID strategy

Use **text IDs** that match OpenITI identifiers (or your canonical mapping of them). Don’t invent integer surrogate keys unless you have a very good reason. Stable identifiers are the whole point.

* `author_id TEXT` (OpenITI author URI/ID)
* `work_id TEXT`
* `version_id TEXT`
* `chunk_id TEXT` (derived: stable function of `version_id` + `chunk_index`)

### Timestamps

All timestamps are `timestamptz` in UTC.

### Text storage

Store **raw and normalized** chunk text in Postgres for now (simplifies reading view and debugging). If it grows too big, you can later move chunk bodies out (or store only in OpenSearch) while keeping the same schema.

---

## Migration 001: `authors`

### Purpose

Canonical author registry for filtering and display.

### Columns

* `author_id TEXT PRIMARY KEY`
* `name_ar TEXT` (Arabic-script canonical name if available)
* `name_latn TEXT` (transliteration / Latin label if available)
* `kunya TEXT NULL`
* `nisba TEXT NULL`
* `death_year_ah INTEGER NULL`
* `death_year_ce INTEGER NULL`
* `birth_year_ah INTEGER NULL`
* `birth_year_ce INTEGER NULL`
* `metadata JSONB NOT NULL DEFAULT '{}'` (pass-through for extra fields)
* `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Indexes

* `idx_authors_death_year_ce` on (`death_year_ce`)
* `idx_authors_name_ar_trgm` (optional later; requires `pg_trgm`) for author name lookup

### Notes

Keep author name fields flexible; OpenITI metadata can change and isn’t uniform.

---

## Migration 002: works

### Purpose

Work-level entity (conceptual text), used for grouping versions and bibliographic hunting.

### Columns

* `work_id TEXT PRIMARY KEY`
* `author_id TEXT NOT NULL REFERENCES authors(author_id) ON UPDATE CASCADE ON DELETE RESTRICT`
* `title_ar TEXT NULL`
* `title_latn TEXT NULL`
* `genre TEXT NULL`
* `work_year_start_ce INTEGER NULL` (optional if derivable)
* `work_year_end_ce INTEGER NULL`
* `metadata JSONB NOT NULL DEFAULT '{}'`
* `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Indexes

* `idx_works_author_id on (author_id)`
* `idx_works_title_ar_trgm` (optional later)

### Notes

Not all works have clean dates; store what you have.

---

## Migration 003: versions

### Purpose

Specific digital text instances (files) that belong to a work. This is the unit you ingest from the corpus.

### Columns

* `version_id TEXT PRIMARY KEY`
* `work_id TEXT NOT NULL REFERENCES works(work_id) ON UPDATE CASCADE ON DELETE RESTRICT`
* `is_pri BOOLEAN NOT NULL DEFAULT false`
* `lang TEXT NOT NULL` Suggested values: `ara`, `fas`, `ota` (or a chosen convention). Use a `CHECK` constraint.
* `source_uri TEXT NULL` (provenance if known)
* `repo_path TEXT NOT NULL` (path within RELEASE repo to the text file)
* `checksum_sha256 TEXT NULL` (optional: detect changes)
* `word_count BIGINT NULL`
* `char_count BIGINT NULL`
* `metadata JSONB NOT NULL DEFAULT '{}'`
* `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Constraints

* `CHECK (lang IN ('ara','fas','ota'))` (extendable)
* Unique: optional `UNIQUE (repo_path)` if one file maps to one version

### Indexes

* `idx_versions_work_id on (work_id)`
* `idx_versions_is_pri on (is_pri)`
* `idx_versions_lang on (lang)`
* `idx_versions_repo_path on (repo_path)`

### Notes

* `repo_path` is critical for ingestion and debugging.
* If you later store multiple file paths per version (rare), move paths to a separate table.

---

## Migration 004: `chunks`

### Purpose

Passage/chunk retrieval unit for search results and reading view. Each chunk is ordered within its version and linked to neighbors.

## Columns

* `chunk_id TEXT PRIMARY KEY`
* `version_id TEXT NOT NULL REFERENCES versions(version_id) ON UPDATE CASCADE ON DELETE RESTRICT`
* `work_id TEXT NOT NULL REFERENCES works(work_id) ON UPDATE CASCADE ON DELETE RESTRICT`
* `author_id TEXT NOT NULL REFERENCES authors(author_id) ON UPDATE CASCADE ON DELETE RESTRICT`
* `chunk_index INTEGER NOT NULL (0-based or 1-based, but be consistent)`
* `heading_path TEXT[] NULL` e.g. ['كتاب الطهارة','باب المياه'] or empty
* `heading_text TEXT NULL` (closest heading for display)
* `start_char_offset INTEGER NULL` (offset in the version text, if you compute it)
* `end_char_offset INTEGER NULL`
* `text_raw TEXT NOT NULL`
* `text_norm TEXT NOT NULL`
* `token_count INTEGER NULL` (optional: for tuning)
* `word_count INTEGER NULL`
* `prev_chunk_id TEXT NULL REFERENCES chunks(chunk_id) ON UPDATE CASCADE ON DELETE SET NULL`
* `next_chunk_id TEXT NULL REFERENCES chunks(chunk_id) ON UPDATE CASCADE ON DELETE SET NULL`
* `metadata JSONB NOT NULL DEFAULT '{}'`
* `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Constraints

* `UNIQUE (version_id, chunk_index)` (prevents duplicates)
* Optional sanity check: `CHECK (chunk_index >= 0)`

### Indexes

* `idx_chunks_version_id` on (`version_id`)
* `idx_chunks_work_id` on (`work_id`)
* `idx_chunks_author_id` on (`author_id`)
* `idx_chunks_version_chunk_index` on (`version_id`, `chunk_index`)
* Optional: `idx_chunks_heading_path_gin` on (`heading_path`) using GIN for filtering by section
* Optional: `idx_chunks_text_norm_gin_trgm` (later) for quick local string hunting

### Notes

Storing `work_id` and `author_id` redundantly avoids joins for common queries. That’s intentional.

Neighbor links make reading navigation trivial and fast.

---

## Migration 005: ingest_state

### Purpose

Resumable ingestion and audit. Tracks progress per version and optionally per chunk.

### Columns

* `version_id TEXT PRIMARY KEY REFERENCES versions(version_id) ON UPDATE CASCADE ON DELETE CASCADE`
* `status TEXT NOT NULL` Suggested enum-like values: `discovered`, `metadata_resolved`, `parsed`, `chunked`, indexed_bm25, embedded, `complete`, `failed`
* `last_step_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `last_chunk_index INTEGER NULL` (progress marker for partial ingestion)
* `opensearch_index TEXT NULL` (which concrete index was used, e.g. openiti_chunks_v1)
* `qdrant_collection TEXT NULL`
* `error_message TEXT NULL`
* `error_context JSONB NOT NULL DEFAULT '{}'`
* `attempt_count INTEGER NOT NULL DEFAULT 0`
* `locked_by TEXT NULL` (worker id / hostname)
* `locked_at TIMESTAMPTZ NULL`
* `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Constraints / Indexes

* `CHECK (attempt_count >= 0)`
* Index: `idx_ingest_state_status` on (`status`)
* Index: `idx_ingest_state_locked_at` on (`locked_at`)

### Locking semantics (recommended)

* Worker sets `locked_by` + `locked_at` when starting a version
* If worker dies, lock is considered stale after a configurable TTL (enforced in code)
* Avoids two workers ingesting the same version concurrently

---

## Shared Utilities (Recommended in migrations)

### Updated-at trigger

Apply a standard trigger to set `updated_at = now()` on update for all tables.

### Optional extensions

If you want fuzzy search on author/work titles in Postgres:

* `pg_trg`m extension (optional)
* trigram indexes on `authors.name_ar`, `works.title_ar`

Don’t enable these unless you actually use them.

---

## Example: Chunk ID generation (spec-level)

`chunk_id` should be a stable deterministic function. For example:

* `chunk_id = version_id || "::" || chunk_index`
* optionally add fixed padding: `::000123`

Do not use UUIDs unless you enjoy reindexing.

---

## Minimal migration ordering

1. `authors`
2. `works`
3. `versions`
4. `chunks`
5. `ingest_state`
6. triggers / indexes / extensions (optional)