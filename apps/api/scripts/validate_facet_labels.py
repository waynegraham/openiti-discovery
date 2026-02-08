from __future__ import annotations

import argparse
import csv
from pathlib import Path

TRUTHY_ACTIVE = {"1", "true", "yes"}
KNOWN_FACETS = {"period", "region", "tags", "lang", "version"}
REQUIRED_COLUMNS = {"facet", "key", "label_en", "label_ar", "active"}


def _repo_root() -> Path:
    # apps/api/scripts/validate_facet_labels.py -> repo root
    return Path(__file__).resolve().parents[3]


def _is_active(raw_value: str | None) -> bool:
    value = (raw_value or "true").strip().lower()
    return value in TRUTHY_ACTIVE


def validate_rows(
    rows: list[dict[str, str]],
    *,
    start_line: int = 2,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_active_pairs: set[tuple[str, str]] = set()

    for idx, row in enumerate(rows):
        line_number = start_line + idx
        facet = (row.get("facet") or "").strip()
        key = (row.get("key") or "").strip()
        label_en = (row.get("label_en") or "").strip()
        label_ar = (row.get("label_ar") or "").strip()
        active = _is_active(row.get("active"))

        if facet and facet not in KNOWN_FACETS:
            warnings.append(
                f"line {line_number}: unknown facet '{facet}' (kept as draft warning)"
            )

        if not active:
            continue

        if not facet:
            errors.append(f"line {line_number}: active row missing facet")
        if not key:
            errors.append(f"line {line_number}: active row missing key")
        if not label_en:
            errors.append(f"line {line_number}: active row missing label_en")
        if not label_ar:
            errors.append(f"line {line_number}: active row missing label_ar")

        if facet and key:
            pair = (facet, key)
            if pair in seen_active_pairs:
                errors.append(
                    f"line {line_number}: duplicate active (facet,key)=({facet},{key})"
                )
            else:
                seen_active_pairs.add(pair)

    return errors, warnings


def validate_facet_labels_csv(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"], warnings

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_COLUMNS - fieldnames)
        if missing_columns:
            errors.append(
                "Missing required CSV columns: " + ", ".join(missing_columns)
            )
            return errors, warnings

        row_errors, row_warnings = validate_rows(list(reader), start_line=2)
        errors.extend(row_errors)
        warnings.extend(row_warnings)

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate config/facet_labels.csv editorial data."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=_repo_root() / "config" / "facet_labels.csv",
        help="Path to facet_labels.csv (default: config/facet_labels.csv)",
    )
    args = parser.parse_args()

    errors, warnings = validate_facet_labels_csv(args.path)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(
            f"Facet-label validation failed with {len(errors)} error(s) and {len(warnings)} warning(s)."
        )
        return 1

    print(
        f"Facet-label validation passed with {len(warnings)} warning(s): {args.path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
