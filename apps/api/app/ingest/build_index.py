from __future__ import annotations

import argparse
import os
from pathlib import Path

from .run import build_discovery_index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a precomputed discovery index to avoid expensive corpus tree scans."
    )
    parser.add_argument(
        "--corpus-root",
        default=os.getenv("CORPUS_ROOT", ""),
        help="Path to RELEASE root (default: CORPUS_ROOT env)",
    )
    parser.add_argument(
        "--out-json",
        required=True,
        help="Output path for discovery index JSON (e.g. /artifacts/discovery/discovery_index.v1.json)",
    )
    args = parser.parse_args()

    corpus_root = Path(args.corpus_root).resolve()
    if not corpus_root.exists():
        raise SystemExit(f"Corpus root does not exist: {corpus_root}")

    out_json = Path(args.out_json)
    stats = build_discovery_index(corpus_root, out_json)
    print(
        "Built discovery index: indexed_entries={indexed_entries} skipped_missing_files={skipped_missing_files} out={out_json}".format(
            **stats
        )
    )


if __name__ == "__main__":
    main()
