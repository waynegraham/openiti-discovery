from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ..ingest.run import discover_200_pri_arabic


def _count_lines(path: Path) -> int:
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def _parse_targets(raw: str) -> list[int]:
    vals: list[int] = []
    for part in raw.split(","):
        s = part.strip().replace("_", "")
        if not s:
            continue
        vals.append(int(s))
    if not vals:
        raise SystemExit("No targets provided")
    return sorted(vals)


def _plan(corpus_root: Path, targets: list[int]) -> list[dict[str, Any]]:
    max_target = max(targets)
    discovered = discover_200_pri_arabic(corpus_root, target_works=10_000_000)
    if not discovered:
        raise SystemExit(f"No texts discovered under {corpus_root}")

    results: list[dict[str, Any]] = []
    cumulative = 0
    work_limit = 0
    target_idx = 0

    for t in discovered:
        work_limit += 1
        cumulative += _count_lines(t.abs_path)

        while target_idx < len(targets) and cumulative >= targets[target_idx]:
            target_lines = targets[target_idx]
            results.append(
                {
                    "target_lines": target_lines,
                    "recommended_ingest_work_limit": work_limit,
                    "estimated_lines_at_limit": cumulative,
                }
            )
            target_idx += 1

        if cumulative >= max_target and target_idx >= len(targets):
            break

    while target_idx < len(targets):
        results.append(
            {
                "target_lines": targets[target_idx],
                "recommended_ingest_work_limit": None,
                "estimated_lines_at_limit": cumulative,
                "note": "target not reached; corpus too small under current filters",
            }
        )
        target_idx += 1

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate INGEST_WORK_LIMIT values needed to hit target corpus line counts."
    )
    parser.add_argument(
        "--targets",
        default="1000000,5000000,20000000",
        help="Comma-separated line targets (e.g. 1000000,5000000,20000000)",
    )
    parser.add_argument(
        "--corpus-root",
        default=os.getenv("CORPUS_ROOT", ""),
        help="Path to RELEASE root (default: CORPUS_ROOT env)",
    )
    parser.add_argument("--out-json", default="", help="Optional output JSON path")
    args = parser.parse_args()

    corpus_root = Path(args.corpus_root).resolve()
    if not corpus_root.exists():
        raise SystemExit(f"Corpus root does not exist: {corpus_root}")

    targets = _parse_targets(args.targets)
    rows = _plan(corpus_root, targets)

    payload = {
        "corpus_root": str(corpus_root),
        "targets": targets,
        "plan": rows,
    }

    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}")

    for row in rows:
        print(
            "target_lines={target_lines} recommended_ingest_work_limit={recommended_ingest_work_limit} "
            "estimated_lines_at_limit={estimated_lines_at_limit}".format(**row)
        )


if __name__ == "__main__":
    main()
