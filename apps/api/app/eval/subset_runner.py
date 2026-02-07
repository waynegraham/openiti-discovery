from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import text

from ..clients.opensearch_client import get_opensearch
from ..clients.qdrant_client import get_qdrant
from ..db import get_engine
from ..settings import settings


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "subset"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_module(module: str, args: list[str], env_overrides: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(env_overrides)
    cmd = [sys.executable, "-m", module, *args]
    subprocess.run(cmd, check=True, env=env)


def _reset_state(index_name: str, reset_vectors: bool) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE ingest_state, chunks, versions, works, authors RESTART IDENTITY CASCADE"))

    os_client = get_opensearch()
    try:
        os_client.indices.delete(index=index_name)
    except Exception:
        pass
    os_client.indices.create(index=index_name, ignore=400)

    if reset_vectors:
        q = get_qdrant()
        try:
            q.delete_collection(collection_name=settings.QDRANT_COLLECTION)
        except Exception:
            pass


def _update_manifest(
    *,
    manifest_path: Path,
    summary_rows: list[dict[str, Any]],
) -> None:
    payload = _load_json(manifest_path)
    runs = payload.get("runs", [])
    by_label = {str(r.get("label", "")): r for r in runs}

    for row in summary_rows:
        label = str(row["label"])
        if label not in by_label:
            continue
        entry = by_label[label]
        if row.get("run_full_pipeline_path"):
            run_path = Path(row["run_full_pipeline_path"])
            try:
                rel = run_path.relative_to(manifest_path.parent)
                entry["run_path"] = rel.as_posix()
            except Exception:
                entry["run_path"] = str(run_path)
        if row.get("indexing_hours") is not None:
            entry["indexing_hours"] = float(row["indexing_hours"])
        entry["index_name"] = row["index_name"]

    _write_json(manifest_path, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingest + evaluation across multiple subset definitions.")
    parser.add_argument("--subset-manifest", required=True, help="JSON with runs[{label,index_name,ingest_work_limit}]")
    parser.add_argument("--out-root", required=True, help="Directory for per-subset outputs")
    parser.add_argument("--queries", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--configs", default="baseline,normalized,variant_aware,full_pipeline")
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--langs", default="ara")
    parser.add_argument("--pri-only", action="store_true")
    parser.add_argument("--embeddings-enabled", default="true", choices=["true", "false"])
    parser.add_argument("--embedding-device", default="cpu")
    parser.add_argument("--scalability-manifest", default="", help="Optional manifest for app.eval.tables")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-tables", action="store_true")
    parser.add_argument("--skip-record", action="store_true")
    parser.add_argument("--no-reset-state", action="store_true")
    parser.add_argument("--update-manifest", default="", help="Optional manifest file to patch run_path/indexing_hours")
    args = parser.parse_args()

    subset_manifest = _load_json(Path(args.subset_manifest))
    runs = subset_manifest.get("runs", [])
    if not runs:
        raise SystemExit("No runs found in subset manifest")

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    for spec in runs:
        label = str(spec.get("label", "")).strip()
        index_name = str(spec.get("index_name", "")).strip()
        work_limit = int(spec.get("ingest_work_limit", 0))
        subdir = str(spec.get("run_subdir", "")).strip() or _slugify(label)
        if not label or not index_name:
            raise SystemExit("Each subset row must include label and index_name")
        if not args.skip_ingest and work_limit <= 0:
            raise SystemExit(f"subset '{label}' missing valid ingest_work_limit")

        subset_root = out_root / subdir
        run_dir = subset_root / "runs"
        metrics_dir = subset_root / "metrics"
        tables_dir = subset_root / "tables"
        run_dir.mkdir(parents=True, exist_ok=True)
        metrics_dir.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(parents=True, exist_ok=True)

        if not args.no_reset_state:
            _reset_state(index_name=index_name, reset_vectors=args.embeddings_enabled == "true")

        env_overrides = {
            "OPENSEARCH_INDEX_CHUNKS": index_name,
            "INGEST_WORK_LIMIT": str(work_limit),
            "INGEST_ONLY_PRI": "true" if args.pri_only else "false",
            "INGEST_LANGS": args.langs,
            "EMBEDDINGS_ENABLED": args.embeddings_enabled,
            "EMBEDDING_DEVICE": args.embedding_device,
        }

        ingest_hours: float | None = None
        if not args.skip_ingest:
            t0 = time.perf_counter()
            _run_module("app.ingest.run", [], env_overrides)
            ingest_hours = (time.perf_counter() - t0) / 3600.0

        if not args.skip_eval:
            runner_args = [
                "--queries",
                args.queries,
                "--output-dir",
                str(run_dir),
                "--configs",
                args.configs,
                "--size",
                str(args.size),
                "--langs",
                args.langs,
            ] + (["--pri-only"] if args.pri_only else [])
            _run_module("app.eval.runner", runner_args, env_overrides)

            _run_module(
                "app.eval.metrics",
                [
                    "--run-dir",
                    str(run_dir),
                    "--qrels",
                    args.qrels,
                    "--out-dir",
                    str(metrics_dir),
                    "--p-at",
                    "10",
                    "--recall-at",
                    "100",
                    "--success-at",
                    "10",
                ],
                env_overrides,
            )

            if not args.skip_tables and args.scalability_manifest:
                _run_module(
                    "app.eval.tables",
                    [
                        "--metrics-dir",
                        str(metrics_dir),
                        "--out-dir",
                        str(tables_dir),
                        "--scalability-manifest",
                        args.scalability_manifest,
                    ],
                    env_overrides,
                )

            if not args.skip_record:
                _run_module(
                    "app.eval.record",
                    [
                        "--queries",
                        args.queries,
                        "--qrels",
                        args.qrels,
                        "--run-dir",
                        str(run_dir),
                        "--metrics-dir",
                        str(metrics_dir),
                        "--tables-dir",
                        str(tables_dir),
                        "--out-csv",
                        str(subset_root / "experiment_runs.csv"),
                        "--append",
                    ],
                    env_overrides,
                )

        summary_rows.append(
            {
                "label": label,
                "index_name": index_name,
                "ingest_work_limit": work_limit,
                "indexing_hours": ingest_hours,
                "subset_output_dir": str(subset_root),
                "run_full_pipeline_path": str(run_dir / "run_full_pipeline.json"),
            }
        )

    summary = {
        "subset_manifest": args.subset_manifest,
        "out_root": str(out_root),
        "rows": summary_rows,
    }
    _write_json(out_root / "subset_runner_summary.json", summary)

    if args.update_manifest:
        _update_manifest(manifest_path=Path(args.update_manifest), summary_rows=summary_rows)

    print(f"wrote {out_root / 'subset_runner_summary.json'}")
    if args.update_manifest:
        print(f"updated {args.update_manifest}")


if __name__ == "__main__":
    main()
