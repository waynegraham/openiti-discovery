from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

from ..clients.opensearch_client import get_opensearch
from ..clients.qdrant_client import get_qdrant
from ..settings import settings


def _fmt_bytes(size_bytes: int | float | None) -> str:
    if not size_bytes:
        return "0 B"
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024.0 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    return f"{value:.2f} {units[idx]}"


def _normalize_qdrant_info(raw: Any) -> dict[str, Any]:
    if hasattr(raw, "model_dump"):
        return dict(raw.model_dump())
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "dict"):
        return dict(raw.dict())
    return {}


def _resolve_opensearch_indices(target: str) -> list[str]:
    client = get_opensearch()
    # Check alias first: `exists(index=alias)` may return True for aliases in OpenSearch.
    if client.indices.exists_alias(name=target):
        alias_view = client.indices.get_alias(name=target)
        return sorted(alias_view.keys())
    if client.indices.exists(index=target):
        return [target]
    raise SystemExit(f"OpenSearch target '{target}' is neither an index nor alias.")


def _opensearch_report(target: str) -> dict[str, Any]:
    client = get_opensearch()
    indices = _resolve_opensearch_indices(target)

    rows: list[dict[str, Any]] = []
    total_bytes = 0
    for index_name in indices:
        stats = client.indices.stats(index=index_name, metric="store")
        idx = stats.get("indices", {}).get(index_name, {})
        size_bytes = int(idx.get("total", {}).get("store", {}).get("size_in_bytes") or 0)
        total_bytes += size_bytes
        rows.append(
            {
                "index": index_name,
                "size_bytes": size_bytes,
                "size_human": _fmt_bytes(size_bytes),
            }
        )

    return {
        "target": target,
        "resolved_indices": rows,
        "total_size_bytes": total_bytes,
        "total_size_human": _fmt_bytes(total_bytes),
    }


def _qdrant_report(collection: str) -> dict[str, Any]:
    client = get_qdrant()
    info = _normalize_qdrant_info(client.get_collection(collection_name=collection))

    disk_bytes = int(info.get("disk_data_size") or 0)
    ram_bytes = int(info.get("ram_data_size") or 0)
    has_disk_metrics = ("disk_data_size" in info) or ("ram_data_size" in info)

    return {
        "collection": collection,
        "points_count": int(info.get("points_count") or 0),
        "vectors_count": int(info.get("vectors_count") or 0),
        "segments_count": int(info.get("segments_count") or 0),
        "disk_data_size_bytes": disk_bytes,
        "disk_data_size_human": _fmt_bytes(disk_bytes),
        "ram_data_size_bytes": ram_bytes,
        "ram_data_size_human": _fmt_bytes(ram_bytes),
        "disk_metrics_available": has_disk_metrics,
        "note": (
            ""
            if has_disk_metrics
            else "Qdrant server did not return disk/ram size fields for this collection."
        ),
    }


def _corpus_report(corpus_root: Path) -> dict[str, Any]:
    if not corpus_root.exists():
        raise SystemExit(f"Corpus root does not exist: {corpus_root}")

    total_bytes = 0
    file_count = 0
    for p in corpus_root.rglob("*"):
        if ".git" in p.parts:
            continue
        if p.is_file():
            total_bytes += p.stat().st_size
            file_count += 1

    return {
        "corpus_root": str(corpus_root),
        "file_count": file_count,
        "total_size_bytes": total_bytes,
        "total_size_human": _fmt_bytes(total_bytes),
    }


def _write_csv(path: Path, payload: dict[str, Any]) -> None:
    rows: list[dict[str, str]] = []

    os_data = payload["opensearch"]
    rows.append(
        {
            "section": "opensearch",
            "name": "target",
            "value": str(os_data["target"]),
            "unit": "",
            "extra": "",
        }
    )
    for idx in os_data["resolved_indices"]:
        rows.append(
            {
                "section": "opensearch",
                "name": f"index_size_bytes:{idx['index']}",
                "value": str(idx["size_bytes"]),
                "unit": "bytes",
                "extra": idx["size_human"],
            }
        )
    rows.append(
        {
            "section": "opensearch",
            "name": "total_size_bytes",
            "value": str(os_data["total_size_bytes"]),
            "unit": "bytes",
            "extra": os_data["total_size_human"],
        }
    )

    qd_data = payload["qdrant"]
    rows.extend(
        [
            {
                "section": "qdrant",
                "name": "collection",
                "value": str(qd_data["collection"]),
                "unit": "",
                "extra": "",
            },
            {
                "section": "qdrant",
                "name": "points_count",
                "value": str(qd_data["points_count"]),
                "unit": "count",
                "extra": "",
            },
            {
                "section": "qdrant",
                "name": "vectors_count",
                "value": str(qd_data["vectors_count"]),
                "unit": "count",
                "extra": "",
            },
            {
                "section": "qdrant",
                "name": "segments_count",
                "value": str(qd_data["segments_count"]),
                "unit": "count",
                "extra": "",
            },
            {
                "section": "qdrant",
                "name": "disk_data_size_bytes",
                "value": str(qd_data["disk_data_size_bytes"]),
                "unit": "bytes",
                "extra": qd_data["disk_data_size_human"],
            },
            {
                "section": "qdrant",
                "name": "ram_data_size_bytes",
                "value": str(qd_data["ram_data_size_bytes"]),
                "unit": "bytes",
                "extra": qd_data["ram_data_size_human"],
            },
        ]
    )

    corpus_data = payload["corpus"]
    rows.extend(
        [
            {
                "section": "corpus",
                "name": "corpus_root",
                "value": str(corpus_data["corpus_root"]),
                "unit": "",
                "extra": "",
            },
            {
                "section": "corpus",
                "name": "file_count",
                "value": str(corpus_data["file_count"]),
                "unit": "count",
                "extra": "",
            },
            {
                "section": "corpus",
                "name": "total_size_bytes",
                "value": str(corpus_data["total_size_bytes"]),
                "unit": "bytes",
                "extra": corpus_data["total_size_human"],
            },
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "name", "value", "unit", "extra"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report OpenSearch index size and Qdrant collection size."
    )
    parser.add_argument(
        "--opensearch-target",
        default=settings.OPENSEARCH_INDEX_CHUNKS,
        help="OpenSearch index or alias (default: OPENSEARCH_INDEX_CHUNKS)",
    )
    parser.add_argument(
        "--qdrant-collection",
        default=settings.QDRANT_COLLECTION,
        help="Qdrant collection name (default: QDRANT_COLLECTION)",
    )
    parser.add_argument(
        "--corpus-root",
        default=os.getenv("CORPUS_ROOT", "RELEASE"),
        help="Corpus root path used for corpus size calculation (default: CORPUS_ROOT env or RELEASE)",
    )
    parser.add_argument(
        "--out-json",
        default="data/eval/output/metrics/index_sizes_report.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-csv",
        default="data/eval/output/metrics/index_sizes_report.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    payload = {
        "opensearch": _opensearch_report(args.opensearch_target),
        "qdrant": _qdrant_report(args.qdrant_collection),
        "corpus": _corpus_report(Path(args.corpus_root).resolve()),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out_csv = Path(args.out_csv)
    _write_csv(out_csv, payload)

    os_data = payload["opensearch"]
    print(f"OpenSearch target: {os_data['target']}")
    for row in os_data["resolved_indices"]:
        print(
            f"  - {row['index']}: {row['size_human']} ({row['size_bytes']} bytes)"
        )
    print(
        f"  Total: {os_data['total_size_human']} ({os_data['total_size_bytes']} bytes)"
    )

    qd_data = payload["qdrant"]
    print(f"Qdrant collection: {qd_data['collection']}")
    print(f"  Points: {qd_data['points_count']}")
    print(f"  Vectors: {qd_data['vectors_count']}")
    print(f"  Segments: {qd_data['segments_count']}")
    print(
        f"  Disk data size: {qd_data['disk_data_size_human']} ({qd_data['disk_data_size_bytes']} bytes)"
    )
    print(
        f"  RAM data size: {qd_data['ram_data_size_human']} ({qd_data['ram_data_size_bytes']} bytes)"
    )
    if qd_data["note"]:
        print(f"  Note: {qd_data['note']}")

    corpus_data = payload["corpus"]
    print(f"Corpus root: {corpus_data['corpus_root']}")
    print(f"  Files: {corpus_data['file_count']}")
    print(
        f"  Total corpus size: {corpus_data['total_size_human']} ({corpus_data['total_size_bytes']} bytes)"
    )
    print(f"Wrote JSON: {out_json}")
    print(f"Wrote CSV: {out_csv}")


if __name__ == "__main__":
    main()
