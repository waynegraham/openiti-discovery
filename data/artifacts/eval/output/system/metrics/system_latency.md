# Milestone 8 Latency Report

- Page size: `20`
- Classification bands: `<50ms Excellent`, `<100ms Good`, `100-300ms Acceptable`, `>300ms Poor`
- Note: latency bands are report-only for Milestone 8.

| Config | Samples | Avg (ms) | P50 (ms) | P95 (ms) | Class |
|---|---:|---:|---:|---:|---|
| hybrid_ck100_rrf30 | 5 | 1804.52 | 173.69 | 6694.62 | Poor |
| hybrid_ck100_rrf60 | 5 | 175.94 | 174.66 | 189.12 | Acceptable |
| hybrid_ck100_rrf90 | 5 | 189.16 | 188.55 | 199.45 | Acceptable |
| hybrid_ck200_rrf30 | 5 | 281.28 | 273.82 | 312.80 | Poor |
| hybrid_ck200_rrf60 | 5 | 276.95 | 268.44 | 326.80 | Poor |
| hybrid_ck200_rrf90 | 5 | 260.41 | 264.54 | 276.45 | Acceptable |
| hybrid_ck400_rrf30 | 5 | 283.52 | 283.23 | 313.27 | Poor |
| hybrid_ck400_rrf60 | 5 | 278.02 | 279.69 | 289.30 | Acceptable |
| hybrid_ck400_rrf90 | 5 | 302.40 | 291.03 | 352.86 | Poor |
| mode_bm25 | 5 | 22.77 | 12.38 | 47.22 | Excellent |
| mode_hybrid | 5 | 209.99 | 206.42 | 236.85 | Acceptable |
| mode_vector | 5 | 2002.28 | 217.82 | 7331.22 | Poor |
