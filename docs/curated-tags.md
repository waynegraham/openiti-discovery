# Curated Tags Guide (Domain Experts)

This guide explains how to update `curated_tags.txt`, which controls which metadata tags appear as searchable facets in OpenITI Discovery.

## What This File Does

`curated_tags.txt` is an allow-list. During ingest:

1. The pipeline reads metadata tags from `RELEASE/OpenITI_metadata_2023-1-8.csv`.
2. Only tags that exactly match a line in `curated_tags.txt` are kept in the indexed `tags` field.
3. Tags not in the file are ignored for faceting.

Practical impact:

* Add a tag to make it eligible for facet counts.
* Remove a tag to hide it from facets on next ingest.

## Editing Rules

Edit file: `curated_tags.txt` (repo root).

Rules:

* One tag per line.
* Keep exact spelling and punctuation from metadata.
* UTF-8 text is required (Arabic is supported).
* No inline comments. Any non-empty line is treated as a real tag.
* Avoid duplicates.

Examples:

```text
GAL@hadith
_FIQH
JK@كتب التاريخ
```

## Recommended Editorial Workflow

1. Open `curated_tags.txt`.
2. Add/remove tags based on the taxonomy you want in the search facets.
3. Save as UTF-8.
4. Run a quick sanity check:
   `Get-Content curated_tags.txt | Measure-Object -Line`
5. Commit the change with a clear message (for example: `curated_tags: add tafsir taxonomy tags`).

## Verify New Tags Exist in Metadata (Optional but Recommended)

If a tag is missing from metadata, it will never appear in facets.

PowerShell example (`YOUR_TAG_HERE`):

```powershell
rg -n "YOUR_TAG_HERE" RELEASE/OpenITI_metadata_2023-1-8.csv
```

No match means the tag is not present in current metadata.

## Apply Changes to Search

After updating `curated_tags.txt`, re-run ingest so OpenSearch documents are rebuilt with the new tag allow-list.

CPU:

```bash
docker compose --profile ingest run --rm ingest
```

GPU:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm --gpus all ingest_cuda
```

If API images are stale, rebuild first:

```bash
docker compose build api
```

## Notes

* Tag curation is separate from period/region extraction.
* `period` and `region` facets are derived from metadata patterns, not from `curated_tags.txt`.
