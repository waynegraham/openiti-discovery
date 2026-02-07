from __future__ import annotations

import argparse
from pathlib import Path

from .runner import main as runner_main
from .metrics import main as metrics_main
from .tables import main as tables_main


# Thin wrapper to keep a single entrypoint from Make.
# We call subcommands by reusing their CLIs through argument manipulation.
def main() -> None:
    parser = argparse.ArgumentParser(description="Run full evaluation pipeline (run -> metrics -> tables).")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--metrics-dir", required=True)
    parser.add_argument("--tables-dir", required=True)
    parser.add_argument("--scalability-manifest", required=True)
    parser.add_argument("--configs", default="baseline,normalized,variant_aware,full_pipeline")
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--langs", default="ara")
    parser.add_argument("--pri-only", action="store_true")
    args = parser.parse_args()

    import sys

    sys.argv = [
        "runner",
        "--queries",
        args.queries,
        "--output-dir",
        args.run_dir,
        "--configs",
        args.configs,
        "--size",
        str(args.size),
        "--langs",
        args.langs,
    ] + (["--pri-only"] if args.pri_only else [])
    runner_main()

    sys.argv = [
        "metrics",
        "--run-dir",
        args.run_dir,
        "--qrels",
        args.qrels,
        "--out-dir",
        args.metrics_dir,
        "--p-at",
        "10",
        "--recall-at",
        "100",
        "--success-at",
        "10",
    ]
    metrics_main()

    sys.argv = [
        "tables",
        "--metrics-dir",
        args.metrics_dir,
        "--out-dir",
        args.tables_dir,
        "--scalability-manifest",
        args.scalability_manifest,
    ]
    tables_main()

    print("evaluation pipeline complete")


if __name__ == "__main__":
    main()
