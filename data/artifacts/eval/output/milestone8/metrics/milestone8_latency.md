# Milestone 8 Latency Report

- Page size: `20`
- Classification bands: `<50ms Excellent`, `<100ms Good`, `100-300ms Acceptable`, `>300ms Poor`
- Note: latency bands are report-only for Milestone 8.

| Config | Samples | Avg (ms) | P50 (ms) | P95 (ms) | Class |
|---|---:|---:|---:|---:|---|
| hybrid_ck100_rrf30 | 5 | 1561.15 | 272.97 | 5423.72 | Poor |
| hybrid_ck100_rrf60 | 5 | 268.48 | 266.68 | 279.83 | Acceptable |
| hybrid_ck100_rrf90 | 5 | 272.21 | 273.77 | 279.07 | Acceptable |
| hybrid_ck200_rrf30 | 5 | 284.83 | 287.74 | 296.51 | Acceptable |
| hybrid_ck200_rrf60 | 5 | 276.63 | 273.86 | 287.31 | Acceptable |
| hybrid_ck200_rrf90 | 5 | 268.98 | 270.86 | 276.23 | Acceptable |
| hybrid_ck400_rrf30 | 5 | 272.65 | 271.52 | 281.35 | Acceptable |
| hybrid_ck400_rrf60 | 5 | 283.39 | 274.14 | 304.90 | Poor |
| hybrid_ck400_rrf90 | 5 | 272.19 | 272.74 | 275.88 | Acceptable |
| mode_bm25 | 5 | 8.43 | 6.76 | 13.88 | Excellent |
| mode_hybrid | 5 | 277.16 | 276.55 | 285.55 | Acceptable |
| mode_vector | 5 | 1571.57 | 272.99 | 5480.03 | Poor |
