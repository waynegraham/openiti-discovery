# Facet Labels Workflow

This document defines how non-technical domain experts edit facet labels used by search.

## Purpose

Facet keys are machine-facing (`GAL@period-*`, `_RE`, etc.).
The UI should show human-friendly labels provided by backend-ready facet payloads.

## Source of Truth

Edit file: `config/facet_labels.csv`

Required columns:
- `facet`
- `key`
- `label_en`
- `label_ar`
- `notes`
- `active`

## Editing Rules

- One row per facet key.
- Keep `facet` and `key` exact; labels can be updated freely.
- Set `active=false` to hide a label without deleting history.
- Do not add inline comments in CSV fields.

## Recommended Workflow

1. Domain expert edits `config/facet_labels.csv`.
2. Run validation script (to be added during implementation):
   - duplicate `(facet,key)` rows
   - missing `label_en`/`label_ar` for active rows
   - unknown facet names
3. Build step converts CSV into runtime map used by API.
4. API returns label-ready facets (`key`, `label`, `count`).

## Ownership

- Domain experts own label text.
- Engineers own schema, validation, and runtime loading.

## Notes

- Keep labels short for facet chips.
- Prefer stable terminology over frequent wording churn.
