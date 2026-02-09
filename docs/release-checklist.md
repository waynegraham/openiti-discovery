# Release Checklist

Milestone 8 release gate checklist. Mark each section after running `make milestone-8`.

## Ingest

- [ ] Ingest resume behavior validated (no duplicate complete versions, deterministic restart).
- [ ] Subset manifest path used for representative benchmark context (`data/eval/subsets.sample.json`).

## Search Modes

- [ ] `bm25` search smoke passes.
- [ ] `vector` search smoke passes.
- [ ] `hybrid` search smoke passes.

## Filters and Facets

- [ ] Facet filters accepted by search endpoint.
- [ ] BM25 facet payload present and valid.

## Degraded Fallback

- [ ] Hybrid request degrades to `effective_mode=bm25` when Qdrant is unavailable.
- [ ] Warning `qdrant_unavailable_fallback_bm25` is present.

## Reading Routes

- [ ] `/chunks/{chunk_id}` route reachable for a discovered chunk.
- [ ] `/works/{work_id}` and `/works/{work_id}/versions` routes reachable for a discovered work.
- [ ] `/works/{work_id}/versions/{version_id}/chunks/resolve` route reachable for discovered version.

## Quality and Latency Artifacts

- [ ] No-regression quality gate passes against `full_pipeline` baseline.
- [ ] Hybrid tuning decision artifact generated.
- [ ] Latency report generated (classification is report-only).

