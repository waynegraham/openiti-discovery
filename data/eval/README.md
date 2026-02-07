# Evaluation Workflow for Paper Claims

This folder contains templates used by `app.eval` scripts.

## Files

- `queries.sample.json`: starter query set with categories matching your outline.
- `qrels.sample.json`: relevance judgments (replace placeholder IDs with real IDs).
- `scalability.sample.json`: inputs for Table Z.
- `queries.placeholder.json`: generated filler query pack for smoke-testing pipeline.
- `qrels.placeholder.json`: generated placeholder judgments (`TODO_*` IDs).
- `output/`: generated runs, metrics, and tables.

## Fast Start (Placeholder Workflow)

From repo root:

```bash
make eval-scaffold
make eval-all EVAL_QUERIES=/app/data/eval/queries.placeholder.json EVAL_QRELS=/app/data/eval/qrels.placeholder.json
```

This intentionally produces low/zero retrieval metrics until you replace placeholder qrels with judged IDs.

## Query file format

```json
{
  "queries": [
    {
      "id": "Q1",
      "category": "known_entity",
      "text": "query text",
      "variants": ["orthographic variant"],
      "expansions": ["optional thematic expansion"]
    }
  ]
}
```

## Qrels format

Each qrel row can include passage/work/author IDs. Metrics are computed by granularity from whichever IDs are present.

```json
{
  "qrels": [
    {
      "query_id": "Q1",
      "passage_id": "chunk_id",
      "work_id": "work_id",
      "author_id": "author_id",
      "relevance": 1
    }
  ]
}
```

## Outputs

- `table_x_retrieval_performance.csv`
- `table_y_granularity.csv`
- `table_z_scalability.csv`
- Markdown versions in `output/tables/`
- `category_breakdown.csv` for the five query categories
- `experiment_runs.csv` cumulative experiment log (one row per retrieval config per run)
