from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.clients.opensearch_client import get_opensearch
from app.clients.qdrant_client import get_qdrant
from app.db import get_engine
from app.ingest.run import _metadata_is_pri, load_metadata
from app.language import UNKNOWN_LANGUAGE, normalize_language_tag
from app.settings import settings


LOG = logging.getLogger("openiti.backfill.languages")


def _determine_effective_lang(meta: dict | None, db_lang: str | None) -> str:
    source_lang = normalize_language_tag((meta or {}).get("lang"))
    if source_lang != UNKNOWN_LANGUAGE:
        return source_lang
    fallback = normalize_language_tag(db_lang)
    return fallback


def _determine_effective_is_pri(meta: dict | None, db_is_pri: bool) -> bool:
    return _metadata_is_pri(
        status=(meta or {}).get("status"),
        version_label=(meta or {}).get("version_label"),
        fallback=bool(db_is_pri),
    )


def _update_opensearch(version_id: str, lang: str, is_pri: bool, version_label: str | None, dry_run: bool) -> int:
    if dry_run:
        return 0

    client = get_opensearch()
    script_lines = [
        "ctx._source.lang = params.lang;",
        "ctx._source.is_pri = params.is_pri;",
    ]
    if version_label is not None:
        script_lines.append("ctx._source.version_label = params.version_label;")

    res = client.update_by_query(
        index=settings.OPENSEARCH_INDEX_CHUNKS,
        conflicts="proceed",
        refresh=True,
        body={
            "script": {
                "lang": "painless",
                "source": " ".join(script_lines),
                "params": {
                    "lang": lang,
                    "is_pri": bool(is_pri),
                    "version_label": version_label,
                },
            },
            "query": {"term": {"version_id": version_id}},
        },
    )
    return int(res.get("updated") or 0)


def _update_qdrant(version_id: str, lang: str, is_pri: bool, version_label: str | None, dry_run: bool) -> int:
    qdrant = get_qdrant()
    offset = None
    updated = 0
    while True:
        points, offset = qdrant.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter={"must": [{"key": "version_id", "match": {"value": version_id}}]},
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        if not points:
            break
        updated += len(points)
        if not dry_run:
            qdrant.set_payload(
                collection_name=settings.QDRANT_COLLECTION,
                payload={
                    "lang": lang,
                    "is_pri": bool(is_pri),
                    "version_label": version_label,
                },
                points=[p.id for p in points],
            )
        if offset is None:
            break
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time language normalization backfill for DB, OpenSearch, and Qdrant.",
    )
    parser.add_argument(
        "--corpus-root",
        default=os.getenv("CORPUS_ROOT", ""),
        help="Path to OpenITI RELEASE root (for metadata CSV lookup).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

    corpus_root = Path(args.corpus_root).resolve() if args.corpus_root else None
    metadata_by_path: dict[str, dict] = {}
    metadata_by_version: dict[str, dict] = {}
    if corpus_root and corpus_root.exists():
        metadata_by_path, metadata_by_version = load_metadata(corpus_root, curated_tags=set())
    else:
        LOG.warning("CORPUS_ROOT missing or unavailable; source metadata precedence may be partial.")

    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT version_id, repo_path, lang, is_pri, metadata
                FROM versions
                ORDER BY version_id
                """
            )
        ).mappings().all()

    updated_versions = 0
    updated_os_docs = 0
    updated_qdrant_points = 0

    for row in rows:
        version_id = str(row["version_id"])
        repo_path = str(row.get("repo_path") or "")
        metadata = row.get("metadata") or {}
        source_meta = metadata_by_path.get(repo_path) or metadata_by_version.get(version_id) or {}

        effective_lang = _determine_effective_lang(source_meta, row.get("lang"))
        effective_is_pri = _determine_effective_is_pri(source_meta, bool(row.get("is_pri")))
        effective_version_label = (source_meta.get("version_label") or metadata.get("version_label") or "").strip() or None

        if effective_lang == UNKNOWN_LANGUAGE:
            LOG.warning(
                "Language metadata missing/unmapped for version_id=%s (repo_path=%s). Using unknown.",
                version_id,
                repo_path,
            )

        if (
            normalize_language_tag(row.get("lang")) == effective_lang
            and bool(row.get("is_pri")) == effective_is_pri
        ):
            # still keep index stores in sync
            updated_os_docs += _update_opensearch(
                version_id,
                effective_lang,
                effective_is_pri,
                effective_version_label,
                args.dry_run,
            )
            updated_qdrant_points += _update_qdrant(
                version_id,
                effective_lang,
                effective_is_pri,
                effective_version_label,
                args.dry_run,
            )
            continue

        if not args.dry_run:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE versions
                        SET lang = :lang,
                            is_pri = :is_pri,
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('version_label', CAST(:version_label AS text)),
                            updated_at = now()
                        WHERE version_id = :version_id
                        """
                    ),
                    {
                        "version_id": version_id,
                        "lang": effective_lang,
                        "is_pri": effective_is_pri,
                        "version_label": effective_version_label,
                    },
                )
        updated_versions += 1
        updated_os_docs += _update_opensearch(
            version_id,
            effective_lang,
            effective_is_pri,
            effective_version_label,
            args.dry_run,
        )
        updated_qdrant_points += _update_qdrant(
            version_id,
            effective_lang,
            effective_is_pri,
            effective_version_label,
            args.dry_run,
        )

    LOG.info(
        "Backfill complete dry_run=%s versions_updated=%d opensearch_docs_updated=%d qdrant_points_touched=%d",
        args.dry_run,
        updated_versions,
        updated_os_docs,
        updated_qdrant_points,
    )


if __name__ == "__main__":
    main()
