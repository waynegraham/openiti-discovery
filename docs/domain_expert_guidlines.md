# Domain Expert Guidelines for Query and Relevance Judgments

## Purpose
Use this form to define historically realistic discovery queries and relevance judgments for evaluation of the OpenITI discovery pipeline.

## What You Need To Fill Out
You will complete two files:

1. `data/eval/forms/queries_form.csv` (queries)
2. `data/eval/forms/qrels_form.csv` (query relevance)

## File 1: Query Design (`queries_form.csv`)
Create 3-5 queries per category.

Required columns:
- `query_id`: stable ID (e.g., `Q001`, `Q002`)
- `category`: one of:
  - `known_entity`
  - `variant_orthography`
  - `conceptual_thematic`
  - `cross_textual_reuse`
  - `metadata_poor`
- `query_text`: primary user-like search string
- `variants_pipe`: spelling/orthographic variants separated by `|`
- `expansions_pipe`: exploratory or thematic expansions separated by `|`
- `notes`: optional rationale/context

## File 2: Relevance Judgments (`qrels_form.csv`)
For each query, add relevant results (prefer at least 3 passages where possible).

Required columns:
- `query_id`: must match an ID from `queries_form.csv`
- `passage_id`: chunk identifier
- `work_id`: work identifier
- `author_id`: author identifier
- `relevance`: `1` for relevant (`0` optional for non-relevant)
- `evidence_note`: short reason this item is relevant
- `judge_initials`: who made the judgment
- `confidence`: `high`, `medium`, or `low`

## Judgment Standard
Mark as relevant when the result would reasonably help a scholar complete the stated discovery task for that query.

Keep consistency across all queries:
- Same threshold for what counts as relevant
- Prefer passage-level evidence over broad topical similarity
- If uncertain, include row and mark `confidence=low`

## Workflow
1. Fill out both CSVs.
2. Return CSVs to project maintainer.
3. Maintainer converts CSV -> JSON for pipeline files:
   - `data/eval/queries.json`
   - `data/eval/qrels.json`
   - Command: `make eval-import-forms`

## Quality Checks Before Submission
- Every `query_id` in qrels exists in query form
- Category labels are exactly one of the five allowed values
- `variants_pipe` and `expansions_pipe` use `|` separators only
- No placeholder values like `TODO_*`
