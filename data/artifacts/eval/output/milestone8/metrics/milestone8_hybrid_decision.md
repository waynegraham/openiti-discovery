# Milestone 8 Hybrid Tuning Decision

- Baseline config: `full_pipeline`
- Baseline table: `/artifacts/eval/output/milestone8/baseline_metrics/table_x_retrieval_performance.csv`
- Baseline metrics: `{"precision_at_10": 0.0, "recall_at_100": 0.0, "map": 0.0, "task_success_rate_pct": 0.0}`
- Candidate grid: `candidate_k=[100, 200, 400]`, `rrf_k=[30, 60, 90]`
- Representative subset manifest: `/artifacts/milestone8/input/subsets.sample.json`

## Selected Configuration
- Config: `hybrid_ck100_rrf30`
- candidate_k: `100`
- rrf_k: `30`
- precision@10: `0.0000`
- recall@100: `0.0000`
- MAP: `0.0000`
- task_success_rate_pct: `0.0000`

Rationale: highest MAP among no-regression candidates, with task success and recall as tie-breakers.

Full matrix: `/artifacts/eval/output/milestone8/metrics/milestone8_hybrid_matrix.csv`