# OpenITI Deployment Storage Report

Generated: 2026-02-20  
Workspace: `e:\projects\openiti-discovery`

## 1) Corpus storage (host bind mount)

`api`/`ingest` mount `./RELEASE:/corpus/RELEASE:ro`.

| Path | Size |
|---|---:|
| `RELEASE` (all files) | 35.663 GB |
| `RELEASE` excluding `.git` | 21.359 GB |
| `RELEASE/.git` only | 14.304 GB |

Notes:
- For VPS sizing, corpus content is ~21.36 GB.
- If you clone `RELEASE` with full Git history, add ~14.3 GB overhead.

## 2) OpenITI runtime persistent volumes (Docker)

From `docker system df -v` (OpenITI volumes only):

| Volume | Service | Size |
|---|---|---:|
| `openiti-discovery_pg_data` | Postgres | 624.5 MB |
| `openiti-discovery_qdrant_data` | Qdrant | 555.3 MB |
| `openiti-discovery_os_data` | OpenSearch | 120.8 MB |
| `openiti-discovery_hf_cache` | API/ingest HF cache | 479.8 MB |
| **Total** |  | **1.780 GB** |

## 3) Container image footprint (OpenITI stack)

From `docker image ls`:

| Image | Size |
|---|---:|
| `openiti_api:dev` | 7.94 GB |
| `openiti-discovery-opensearch:latest` | 1.71 GB |
| `openiti-discovery-frontend:latest` | 927 MB |
| `postgres:18` | 456 MB |
| `qdrant/qdrant:v1.16` | 189 MB |
| **Core total** | **11.222 GB** |

Optional:

| Image | Size |
|---|---:|
| `opensearchproject/opensearch-dashboards:3` | 1.76 GB |

## 4) Existing index-size artifact (historical run)

From `data/eval/output/metrics/index_sizes_report.json` (timestamp: 2026-02-12):

| Metric | Value |
|---|---:|
| OpenSearch index (`openiti_chunks_v1`) | 2.98 GB |
| Corpus counted in that run | 21.36 GB |
| Qdrant points | 563,588 |
| Qdrant disk bytes | not reported by server |

This is useful as a prior ingest reference, but it may not match your current live volumes exactly.

## 5) VPS disk sizing guidance

Measured working set (core deploy path):

- Corpus (no `.git`): 21.359 GB
- OpenITI persistent volumes: 1.780 GB
- Core images: 11.222 GB
- **Subtotal: 34.361 GB**

Recommended disk tiers:

| Tier | Suggested disk | When to use |
|---|---:|---|
| Minimum viable | 60 GB | Very tight, little growth headroom |
| Practical baseline | 80 GB | Safer for logs, temp files, moderate index growth |
| Recommended | 120 GB | Comfortable for rebuilds, growth, optional dashboards |

If you keep full corpus Git history on-server (`RELEASE/.git`), add ~14.3 GB to all tiers.
