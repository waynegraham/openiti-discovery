from __future__ import annotations

from app.repos.works import list_work_versions


class _FakeResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _FakeConn:
    def __init__(self):
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params):
        self.last_sql = str(sql)
        self.last_params = dict(params)
        return _FakeResult()


class _FakeEngine:
    def __init__(self):
        self.conn = _FakeConn()

    def connect(self):
        return self

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_list_work_versions_omits_numeric_order_when_no_preferred_langs():
    engine = _FakeEngine()
    list_work_versions(engine, "w1", [])
    sql = engine.conn.last_sql or ""

    assert "ORDER BY" in sql
    assert "CASE v.lang WHEN 'unknown' THEN 999 ELSE 0 END" in sql
    assert "v.is_pri DESC" in sql
    assert "v.version_id" in sql
    assert engine.conn.last_params == {"work_id": "w1"}


def test_list_work_versions_adds_case_rank_when_preferred_langs_present():
    engine = _FakeEngine()
    list_work_versions(engine, "w1", ["fa", "ar"])
    sql = engine.conn.last_sql or ""

    assert "CASE v.lang" in sql
    assert "WHEN :pref_lang_0 THEN 0" in sql
    assert "WHEN :pref_lang_1 THEN 1" in sql
    assert "WHEN 'unknown' THEN 999 ELSE 998 END" in sql
    assert engine.conn.last_params == {
        "work_id": "w1",
        "pref_lang_0": "fa",
        "pref_lang_1": "ar",
    }
    assert sql.index("CASE v.lang") < sql.index("v.is_pri DESC")
