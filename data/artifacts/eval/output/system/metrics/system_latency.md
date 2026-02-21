# Milestone 8 Latency Report

- Page size: `20`
- Classification bands: `<50ms Excellent`, `<100ms Good`, `100-300ms Acceptable`, `>300ms Poor`
- Note: latency bands are report-only for Milestone 8.

| Config | Samples | Avg (ms) | P50 (ms) | P95 (ms) | Class |
|---|---:|---:|---:|---:|---|
| hybrid_ck100_rrf30 | 5 | 13262.89 | 11983.20 | 17968.82 | Poor |
| hybrid_ck100_rrf60 | 5 | 11491.42 | 11573.82 | 11948.63 | Poor |
| hybrid_ck100_rrf90 | 5 | 11401.23 | 11172.60 | 12104.34 | Poor |
| hybrid_ck200_rrf30 | 5 | 11388.08 | 11347.41 | 11720.35 | Poor |
| hybrid_ck200_rrf60 | 5 | 11398.09 | 11333.10 | 11629.44 | Poor |
| hybrid_ck200_rrf90 | 5 | 11821.90 | 11326.43 | 13256.66 | Poor |
| hybrid_ck400_rrf30 | 5 | 11719.60 | 11564.36 | 12551.35 | Poor |
| hybrid_ck400_rrf60 | 5 | 11253.18 | 11208.13 | 11368.50 | Poor |
| hybrid_ck400_rrf90 | 5 | 11408.48 | 11384.93 | 11817.51 | Poor |
| mode_bm25 | 5 | 17.69 | 13.69 | 29.87 | Excellent |
| mode_hybrid | 5 | 13751.74 | 13059.24 | 15774.25 | Poor |
| mode_vector | 5 | 14827.02 | 13539.64 | 19231.35 | Poor |
