# Milestone 8 Latency Report

- Page size: `20`
- Classification bands: `<50ms Excellent`, `<100ms Good`, `100-300ms Acceptable`, `>300ms Poor`
- Note: latency bands are report-only for Milestone 8.

| Config | Samples | Avg (ms) | P50 (ms) | P95 (ms) | Class |
|---|---:|---:|---:|---:|---|
| hybrid_ck100_rrf30 | 5 | 1711.38 | 292.29 | 5977.37 | Poor |
| hybrid_ck100_rrf60 | 5 | 291.72 | 290.48 | 306.98 | Poor |
| hybrid_ck100_rrf90 | 5 | 289.77 | 284.57 | 303.23 | Poor |
| hybrid_ck200_rrf30 | 5 | 293.39 | 299.95 | 303.22 | Poor |
| hybrid_ck200_rrf60 | 5 | 312.86 | 308.79 | 327.50 | Poor |
| hybrid_ck200_rrf90 | 5 | 309.11 | 305.29 | 328.23 | Poor |
| hybrid_ck400_rrf30 | 5 | 301.62 | 297.01 | 318.26 | Poor |
| hybrid_ck400_rrf60 | 5 | 322.68 | 318.42 | 338.12 | Poor |
| hybrid_ck400_rrf90 | 5 | 334.35 | 314.82 | 395.49 | Poor |
| mode_bm25 | 5 | 9.30 | 7.30 | 15.46 | Excellent |
| mode_hybrid | 5 | 283.16 | 276.57 | 299.27 | Acceptable |
| mode_vector | 5 | 1652.76 | 269.31 | 5789.20 | Poor |
