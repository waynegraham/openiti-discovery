from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_work(engine: Engine, work_id: str) -> dict | None:
    sql = text(
        """
        SELECT
          w.work_id,
          w.author_id,
          w.title_ar,
          w.title_latn,
          w.work_year_start_ce,
          w.work_year_end_ce,
          a.name_ar AS author_name_ar,
          a.name_latn AS author_name_latn,
          a.death_year_ah,
          a.death_year_ce
        FROM works w
        JOIN authors a ON a.author_id = w.author_id
        WHERE w.work_id = :work_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"work_id": work_id}).mappings().first()
        return dict(row) if row else None


def list_work_versions(
    engine: Engine,
    work_id: str,
    preferred_langs: list[str] | None = None,
) -> list[dict]:
    preferred_langs = preferred_langs or []
    lang_rank_expr = "999"
    params: dict[str, object] = {"work_id": work_id}

    if preferred_langs:
        rank_parts: list[str] = []
        for idx, lang in enumerate(preferred_langs):
            key = f"pref_lang_{idx}"
            params[key] = lang
            rank_parts.append(f"WHEN :{key} THEN {idx}")
        lang_rank_expr = f"CASE v.lang {' '.join(rank_parts)} ELSE 999 END"

    sql = text(
        f"""
        SELECT
          v.version_id,
          v.work_id,
          v.lang,
          v.is_pri,
          v.source_uri,
          v.repo_path
        FROM versions v
        WHERE v.work_id = :work_id
        ORDER BY
          v.is_pri DESC,
          {lang_rank_expr},
          v.version_id
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]
