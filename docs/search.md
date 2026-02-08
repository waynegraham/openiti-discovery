# Search Spec (BM25 + Vector + Hybrid)

Date: 2026-02-08
Owner: OpenITI Discovery
Status: Approved for implementation

## Goal
Deliver a submit-based search UX in Next.js that supports:
- `bm25`
- `vector`
- `hybrid` (BM25 + vector reranking via RRF)

No typeahead or streaming in this phase.

## Scope
In scope:
- Server-rendered search results from FastAPI `GET /search`
- Batch-first embedding endpoint `POST /embed`
- Real mode switching in frontend (`bm25`, `vector`, `hybrid`)
- Page-number pagination for all modes
- Facet filtering applied consistently across all modes
- Facets returned only for `bm25` and hidden in non-BM25 modes
- Safe snippet rendering with highlight sanitization (`<em>` only)
- Degraded hybrid fallback when Qdrant is unavailable

Out of scope:
- Collection facet
- Typeahead/query suggestions
- Typed stable result DTO replacing free-form `source`

## Data Sources
- Metadata: `RELEASE/OpenITI_metadata_2023-1-8.csv` (tab-delimited)
- Curated tags allow-list: `curated_tags.txt`
- Facet labels (domain-editable): `config/facet_labels.csv`
- Canonical text normalization config: `config/text_normalization.yml`
- Search/runtime knobs: `config/search_runtime.yml`

## Mapping Rules
### Period
- Source: `GAL@period-*` tags from metadata
- Store raw key for filtering, return user-facing label in facets

### Region
- Source: broad tags ending with `_RE` with precedence:
1. `born@..._RE`
2. `resided@..._RE`
3. `died@..._RE`
4. `visited@..._RE`
- If multiple values exist in highest-priority class, retain all

### Tags
- Keep only tags in `curated_tags.txt`

### Version
- Source: metadata `status`
- Mapping: `pri -> PRI`, `sec -> ALT`

### Dates
- `date_ah` from metadata as integer
- `date_ce = round(ah * 0.97023 + 621.57)`

## Canonical Normalization
- Query text embedding must use the same normalization policy as ingest (`text_norm`)
- Canonical policy is defined in `config/text_normalization.yml`
- `/embed` and `/search` must report normalization config version identifier

## OpenSearch Document Fields
Required searchable/display fields:
- `chunk_id`
- `work_id`, `version_id`, `author_id`
- `lang`, `is_pri`
- `title`, `content`
- `author_name_ar`, `author_name_lat`
- `work_title_ar`, `work_title_lat`
- `date_ah`, `date_ce`
- `period`, `region`, `tags`
- `version_label`
- `type` (constant `Passage`)

Operational rule:
- Mapping changes require a new index version and alias switch. No in-place mapping edits.

## API Contract
### POST `/embed`
Batch-first request:
```json
{
  "texts": ["string"],
  "input_type": "query"
}
```

Response:
```json
{
  "vectors": [[0.0]],
  "embedding_model": "string",
  "embedding_model_version": "string",
  "normalization_version": "string"
}
```

Constraints (configurable via `config/search_runtime.yml`):
- max query length default: 256 chars
- max batch size default: 32

### GET `/search`
Parameters:
- `q` (required)
- `mode` = `bm25|vector|hybrid` (default `bm25`)
- `page` (1-based)
- `size` (default 20, max 100)
- `langs` (comma-separated)
- `pri_only` (bool)
- facet filters (period/region/tags/lang/version) apply to all modes

Response core:
- `query`
- `requested_mode`
- `effective_mode`
- `warnings` (array)
- `total`
- `page`
- `size`
- `results[]` where each hit includes `chunk_id`, `score`, `source`, optional `highlight`
- `embedding_model`, `embedding_model_version`, `normalization_version`

Facet behavior:
- Return `facets` only when `effective_mode=bm25`
- Non-BM25: omit or return empty facets; frontend hides facet UI counts
- Facet buckets must be label-ready from backend:
  - `key`
  - `label`
  - `count`

## Hybrid Retrieval
- Use classic Reciprocal Rank Fusion (RRF):
  - `score(doc) = 1 / (rrf_k + rank_bm25) + 1 / (rrf_k + rank_vector)`
- Default `rrf_k = 60`, configurable in `config/search_runtime.yml`
- Candidate pool depth default:
  - `candidate_k = max(100, page * size * 5)`, capped by config (default cap `1000`)

### Degraded Mode
If `mode=hybrid` and Qdrant is unavailable:
- return HTTP `200`
- set `effective_mode="bm25"`
- include `warnings=["qdrant_unavailable_fallback_bm25"]`

## Pagination
- Public contract remains page-number based (`page`, `size`)
- Internal implementation may use offset/cursor as needed
- Deep-page retrieval quality in hybrid depends on `candidate_k`; tune with telemetry

## Highlight Sanitization
- OpenSearch highlights may contain markup
- Sanitize before returning/rendering
- Allow only `<em>` tags, strip all other tags/attributes

## Facet Aggregations (BM25 only)
- `period`
- `region`
- `tags`
- `lang`
- `version_label`

## Frontend Contract Notes
Location: `apps/frontend/app/[locale]/search/page.tsx`

- Enable mode selector for all three modes
- Call `/search` with selected mode and filters
- Hide facet count panels in `vector`/`hybrid`
- Render backend label-ready facets in `bm25`
- Continue using free-form `source` for display fields
- Render sanitized highlight snippets first, fallback to truncated `source.content`

## Domain-Expert Label Workflow
See `docs/facet-labels.md` for editorial workflow and validation expectations.

## Future Refinement
- Consider weighted RRF after evaluation (`w_bm25`, `w_vector`)
- Consider typed result contracts once UI fields stabilize
- Consider vector/hybrid facet estimates only if UX need outweighs count instability
