from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_chunk_with_neighbors(engine: Engine, chunk_id: str) -> dict | None:
    """
    Returns chunk + neighbor ids and minimal metadata.
    """
    sql = text(
        """
        SELECT
          c.chunk_id,
          c.version_id,
          c.work_id,
          c.author_id,
          c.chunk_index,
          c.heading_text,
          c.heading_path,
          c.text_raw,
          c.text_norm,
          c.prev_chunk_id,
          c.next_chunk_id
        FROM chunks c
        WHERE c.chunk_id = :chunk_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"chunk_id": chunk_id}).mappings().first()
        return dict(row) if row else None


def resolve_chunk_for_version(
    engine: Engine,
    work_id: str,
    version_id: str,
    target_chunk_index: int,
) -> dict | None:
    sql = text(
        """
        SELECT
          c.chunk_id,
          c.chunk_index
        FROM chunks c
        WHERE
          c.work_id = :work_id
          AND c.version_id = :version_id
          AND c.chunk_index <= :target_chunk_index
        ORDER BY c.chunk_index DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(
            sql,
            {
                "work_id": work_id,
                "version_id": version_id,
                "target_chunk_index": target_chunk_index,
            },
        ).mappings().first()
        return dict(row) if row else None
