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
