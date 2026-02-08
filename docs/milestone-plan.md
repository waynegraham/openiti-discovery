# Milestone Plan

This plan sequences implementation work into concrete milestones with acceptance criteria.

## Milestone 1: Platform Integrity (Hard Blockers)

Scope: Fix invalid OpenSearch template and validate index/alias bootstrap path.
Status: Complete (February 8, 2026)

Acceptance criteria:
- `opensearch/templates/openiti_chunks_template.json` parses as valid JSON.
- Template apply command succeeds against local OpenSearch with no manual edits.
- Versioned index creation plus alias attach works, and writes to alias succeed.
- A smoke query against alias returns HTTP 200.

Implementation notes:
- Added `make template-validate` to syntax-check template JSON before apply.
- Added `make smoke-alias` to validate alias write and query path.
- Added `make milestone-1` to run the full bootstrap integrity sequence.
- Updated alias action format for OpenSearch 3 compatibility (`must_exist:false` on remove).

## Milestone 2: Retrieval Filter Correctness (Vector/Hybrid)

Scope: Align Qdrant payload fields with vector filter/query contract.
Status: Complete (February 8, 2026)

Acceptance criteria:
- Ingest writes `period`, `region`, `tags`, and `version_label` into Qdrant payload.
- `vector` and `hybrid` searches honor those filters.
- For a controlled subset corpus, filtered hit IDs are consistent with expected constraints.
- API tests cover at least one filter for each of `period`, `region`, `tags`, and `version`.

Implementation notes:
- Added vector payload builder in ingest to always write `period`, `region`, `tags`, and `version_label` to Qdrant points.
- Centralized Qdrant filter construction for both `vector_search` and `vector_count` to keep behavior consistent.
- Normalized `version` query values (`pri` -> `PRI`, `sec/alt` -> `ALT`) before vector/hybrid dispatch.
- Added API tests verifying filter propagation and version normalization across `vector` and `hybrid` modes.
- Added ingest payload contract test to assert required filter fields are present in Qdrant payloads.

## Milestone 3: True Resumable Ingest

Scope: Implement restartable ingest from `ingest_state` with skip/resume logic.
Status: Complete (February 8, 2026)

Acceptance criteria:
- Interrupted ingest can resume without reprocessing completed versions.
- `SKIP_EXISTING` behavior is implemented and documented.
- Checkpoint state transitions are deterministic and observable (`discovered -> ... -> complete`).
- Restart scenario test passes: stop mid-run, restart, same final counts as uninterrupted run.

Implementation plan:
1. Define a strict ingest-state contract in code and docs.
2. Add a read path for `ingest_state` at startup to drive per-version decisions.
3. Implement `SKIP_EXISTING` (`true` default): skip versions with status `complete`, log skip reason, and keep counts.
4. Implement forced reprocess path (`SKIP_EXISTING=false`): re-run from chunk `0` with idempotent writes and stable chunk IDs.
5. Implement resume path for interrupted versions: continue from `last_chunk_index + 1` when status is `indexed_bm25` or `embedded`.
6. Keep transitions deterministic by centralizing allowed status progressions in one helper and rejecting invalid regressions.
7. Persist checkpoints after every successful batch flush (BM25 and embedding stages) so restarts lose at most one in-flight batch.
8. Add run summary metrics and logs: `processed`, `resumed`, `skipped_complete`, `failed`, `reprocessed`.
9. Add operator docs with exact env behavior and example SQL inspection queries for `ingest_state`.
10. Add a restart integration test that intentionally interrupts ingest mid-version and verifies resumed output matches uninterrupted output.
11. Add unit tests for decision matrix coverage (`complete`, `failed`, `parsed`, `indexed_bm25`, `embedded`, missing state).
12. Add CI wiring for the new resumable-ingest tests in backend test workflow.

Execution sequence:
1. Land state-machine and startup decision logic first.
2. Land chunk/batch resume mechanics second.
3. Land tests and docs third.
4. Gate completion on restart test parity and acceptance criteria pass.

Out of scope for Milestone 3:
- Multi-worker ingest locking/leases across concurrent runners.
- Re-chunk migration strategy when chunking config changes.
- UI surfaces for ingest-state monitoring.

## Milestone 4: Chunking and Text Fidelity

Scope: Replace MVP chunking/text handling with structure-aware chunking plus real raw text slices.
Status: Complete (February 8, 2026)

Acceptance criteria:
- Chunking prefers structural boundaries when available, with fixed-size fallback.
- `text_raw` is no longer copied from normalized text.
- `start_char_offset` and `end_char_offset` are populated for new ingests.
- Chunk IDs remain stable across reruns with unchanged config/input.
- Regression test verifies chunk continuity (`prev_chunk_id` and `next_chunk_id`) and offsets.

Implementation notes:
- Added a structure-aware chunk planner that splits by heading lines and chunks within sections.
- Added fixed-size fallback chunking when no structural headings are present.
- Replaced MVP `text_raw = text_norm` behavior with real raw text slices derived from absolute character spans.
- Populated `start_char_offset` and `end_char_offset` from raw text word spans during ingest.
- Kept deterministic chunk IDs (`{version_id}::{chunk_index}`) with stable ordering across reruns.
- Expanded ingest tests with Milestone 4 regression coverage for offsets, continuity, and ID stability.

## Milestone 5: Reading Experience Completion

Scope: Implement real navigation for result actions and contextual reading.
Status: Complete (February 8, 2026)

Acceptance criteria:
- `Open Passage` opens a functional passage view using `chunk_id`.
- `View Work` routes to a work-level view.
- Jump-to-context works via neighbor traversal.
- Version switching is implemented for works with multiple versions.
- Frontend integration test confirms route navigation and API wiring.

Implementation plan:
1. Add a dedicated passage route in frontend (`/[locale]/passage/[chunkId]`) that fetches `GET /chunks/{chunk_id}` and renders passage text plus metadata.
2. Replace inert result-action buttons in `apps/frontend/app/[locale]/search/page.tsx` with real links:
   - `Open Passage` -> `/${locale}/passage/${chunk_id}`
   - `View Work` -> `/${locale}/work/${work_id}` (from result source)
3. Add a work route (`/[locale]/work/[workId]`) to show work-level metadata and a list of available versions.
4. Introduce backend work-detail endpoints for frontend hydration:
   - `GET /works/{work_id}` returning title/author/date fields
   - `GET /works/{work_id}/versions` returning version list (`version_id`, `lang`, `is_pri`, ordering fields)
5. Extend the chunk API for version-scoped reading where needed:
   - keep `GET /chunks/{chunk_id}` for deep links
   - add resolver endpoint `GET /works/{work_id}/versions/{version_id}/chunks/resolve?target_chunk_index=...`
   - resolver contract: return exact match when present; otherwise nearest lower `chunk_index`; if none exists, return `404`
6. Implement passage neighbor navigation UI (`Previous` / `Next`) driven by `prev_chunk_id` and `next_chunk_id`, with disabled states at boundaries.
7. Implement version switching from both passage and work views:
   - choose a target chunk index from current passage
   - resolve nearest chunk in selected version (exact  index, else nearest lower index, else `404`)
   - navigate to resolved target chunk route
8. Define deterministic version ordering for UI defaults and selectors:
   - primary (`is_pri=true`) first
   - then language-preferred order driven by user locale/query context
   - then stable tie-breaker (`version_id`)
9. Add shared frontend utilities for route building and fetch error handling (`404`, empty-version work, missing source fields in search hits).
10. Add API unit tests for new work/version endpoints and version-switch chunk-resolution behavior.
11. Add frontend integration tests (Next.js route/API integration, not full browser E2E yet) for:
   - search result action navigation
   - passage page data load via `chunk_id`
   - neighbor traversal
   - work page load and version switch
   - locale parity for `en` and `ar` routes/pages
12. Add Makefile/CI wiring to run frontend integration tests in milestone validation.

Execution sequence:
1. Land backend read endpoints and tests first (work detail, version list, version-chunk resolution).
2. Land frontend routes and action-link wiring second (search -> passage/work overview).
3. Land passage neighbor traversal and version switch mechanics third.
4. Land frontend integration harness and CI wiring fourth.
5. Gate completion on all acceptance criteria and green API + frontend integration tests.

Out of scope for Milestone 5:
- Full-text reader annotations, highlights persistence, or bookmarking.
- Cross-work recommendations and editorial curation surfaces.
- Mobile-native app behavior beyond responsive web parity.
- Full Playwright browser E2E (deferred until after lightweight route/API integration tests).

## Milestone 6: Editorial/Config Workflow Completion

Scope: Complete facet label workflow and sync docs with real behavior.

Acceptance criteria:
- Facet-label validation script exists and runs in CI/local (`config/facet_labels.csv` checks).
- Validation covers duplicate keys, unknown facets, and missing labels on active rows.
- `README.md` and `docs/*.md` no longer conflict with implementation (`INGEST_MODE`, language support, current limits).
- A single current-behavior section documents known constraints.

## Milestone 7: Multi-language and Metadata Robustness

Scope: Move from Arabic-centric heuristics to stated metadata/language support.

Acceptance criteria:
- Ingest language filtering works for configured languages without hardcoded Arabic-only assumptions.
- Metadata-based version selection is deterministic and documented.
- Subset ingest can include at least two languages when present in corpus.
- Tests validate language filtering and PRI/ALT selection behavior.

## Milestone 8: Quality, Performance, and Release Readiness

Scope: Tune retrieval/latency and lock release standards.

Acceptance criteria:
- Baseline performance targets are defined and met on a representative subset.
- Hybrid settings (`candidate_k`, `rrf_k`) are benchmarked with recorded rationale.
- End-to-end test suite passes (`api` unit plus integration smoke for search modes).
- Release checklist is green: ingest, search modes, filters, facets, degraded fallback, and reading routes.

## Project-Level Definition of Done

1. All eight milestones meet acceptance criteria.
2. Docs reflect reality and are reproducible by a new developer.
3. No known P1 correctness gaps in ingest/search contracts.
4. A tagged release can be rebuilt and smoke-validated from scratch.
