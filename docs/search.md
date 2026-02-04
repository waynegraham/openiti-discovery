# Live Search Spec

Date: 2026-02-04
Owner: OpenITI Discovery
Status: In Progress

## Goal
Implement a live (submit-based) search experience in the Next.js frontend backed by the FastAPI search API and OpenSearch. Replace the static search page with real results, facets, and pagination.

"Live" here means: user submits a query and the page renders real results from the backend. No typeahead or streaming is required in this phase.

## Scope
In scope:
- Submit-based search
- Results with names, dates, type, and snippets
- Facets for period, region, tags, language, and version
- Pagination (default size 20) with a size selector
- Mode selector (bm25, vector, hybrid) with vector/hybrid disabled until embeddings are ready

Out of scope:
- Collection facet (deferred)
- Typeahead or query suggestions
- Vector embedding endpoint (until available)

## Data Sources
Primary metadata source:
- `RELEASE/OpenITI_metadata_2023-1-8.csv` (tab-delimited)

Curated tags list:
- `curated_tags.txt` (repo root)
Optional override:
- `CURATED_TAGS_PATH` env var (ingest)

## Mapping Rules
### Period
Use `GAL@period-*` tags from the metadata CSV. Store the raw tag and a display label.

Example values:
- `GAL@period-premuhammad`
- `GAL@period-muhammad`

### Region
Use broad region tags ending with `_RE` with precedence:
1. `born@..._RE`
2. `resided@..._RE`
3. `died@..._RE`
4. `visited@..._RE`

If multiple values exist within the highest-priority category, allow multiple regions.

### Tags
Tags are limited to the curated list in `curated_tags.txt` (200 items). Tags not in the list are ignored for faceting.

### Version
Use `status` from CSV:
- `pri` -> PRI
- `sec` -> ALT (or SEC)

### Dates
Use `date` from CSV as AH (integer). Compute CE as:
- `ce = round(ah * 0.97023 + 621.57)`

Display both when available.

## Index Changes (OpenSearch)
OpenSearch documents should include additional fields to support the UI:
- `author_name_ar` (keyword, optional)
- `author_name_lat` (keyword, optional)
- `work_title_ar` (keyword, optional)
- `work_title_lat` (keyword, optional)
- `date_ah` (integer, optional)
- `date_ce` (integer, optional)
- `period` (keyword, optional)
- `region` (keyword or keyword array, optional)
- `tags` (keyword array, optional)
- `version_label` (keyword, derived from status)
- `type` (keyword, constant "Passage" for now)

Keep existing fields:
- `chunk_id`, `work_id`, `version_id`, `author_id`, `lang`, `is_pri`, `title`, `content`

Note: collection facet is deferred and should not be indexed yet.

Operational note:
- New fields require a new index version + re-ingest (do not update mappings in place).

## API Changes
Endpoint: `GET /search`

Parameters:
- `q` (required)
- `mode` = `bm25|vector|hybrid` (bm25 default)
- `page` (1-based, default 1)
- `size` (default 20, max 100)
- `langs` (comma-separated)
- `pri_only` (bool)
- `vector` (required for vector/hybrid until embeddings endpoint exists)

Response additions:
- `total` (total hits)
- `page`
- `size`
- `facets`: object with counts for
  - `period`
  - `region`
  - `tags`
  - `lang`
  - `version`

Each result should include:
- `chunk_id`, `score`, `highlight`, and source fields for display
- If highlight is present, the UI should render highlight snippet(s) for the body

## Facet Aggregations (OpenSearch)
Add terms aggregations in `bm25_search` for:
- `period`
- `region`
- `tags`
- `lang`
- `version_label`

## Frontend Changes
Location: `apps/frontend/app/[locale]/search/page.tsx`

- Replace static data with an API call to `/search` (server-side fetch)
- Render facets from response
- Render pagination and size selector
- Render mode selector with `vector` and `hybrid` visible but disabled

Snippet rule:
- Prefer OpenSearch highlights; fallback to truncated `content`

## Notes
- If metadata fields are not in OpenSearch yet, the API may need to hydrate from Postgres.
- Collection facet is deferred; do not display it in UI for now.
- For now, the UI always submits `mode=bm25` since vector/hybrid require a query vector.

## Open Questions
- None in current scope (curated tags list will be updated later by humans).
