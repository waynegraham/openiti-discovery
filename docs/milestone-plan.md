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

Acceptance criteria:
- Interrupted ingest can resume without reprocessing completed versions.
- `SKIP_EXISTING` behavior is implemented and documented.
- Checkpoint state transitions are deterministic and observable (`discovered -> ... -> complete`).
- Restart scenario test passes: stop mid-run, restart, same final counts as uninterrupted run.

## Milestone 4: Chunking and Text Fidelity

Scope: Replace MVP chunking/text handling with structure-aware chunking plus real raw text slices.

Acceptance criteria:
- Chunking prefers structural boundaries when available, with fixed-size fallback.
- `text_raw` is no longer copied from normalized text.
- `start_char_offset` and `end_char_offset` are populated for new ingests.
- Chunk IDs remain stable across reruns with unchanged config/input.
- Regression test verifies chunk continuity (`prev_chunk_id` and `next_chunk_id`) and offsets.

## Milestone 5: Reading Experience Completion

Scope: Implement real navigation for result actions and contextual reading.

Acceptance criteria:
- `Open Passage` opens a functional passage view using `chunk_id`.
- `View Work` routes to a work-level view.
- Jump-to-context works via neighbor traversal.
- Version switching is implemented for works with multiple versions.
- Frontend integration test confirms route navigation and API wiring.

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
