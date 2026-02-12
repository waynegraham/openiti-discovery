from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_validator_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_facet_labels.py"
    spec = importlib.util.spec_from_file_location("facet_labels_validator", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_validator_warns_on_unknown_facet_and_allows_inactive_missing_labels():
    mod = _load_validator_module()
    rows = [
        {
            "facet": "custom_draft",
            "key": "draft_key",
            "label_en": "Draft EN",
            "label_ar": "",
            "active": "false",
        },
        {
            "facet": "unknown_facet",
            "key": "new_key",
            "label_en": "New EN",
            "label_ar": "جديد",
            "active": "true",
        },
        {
            "facet": "period",
            "key": "GAL@period-muhammad",
            "label_en": "Muhammad",
            "label_ar": "محمد",
            "active": "true",
        },
    ]

    errors, warnings = mod.validate_rows(rows)

    assert errors == []
    assert any("unknown facet" in msg for msg in warnings)


def test_validator_fails_duplicate_only_when_both_rows_active():
    mod = _load_validator_module()
    rows = [
        {"facet": "lang", "key": "ara", "label_en": "Arabic", "label_ar": "العربية", "active": "true"},
        {"facet": "lang", "key": "ara", "label_en": "Draft", "label_ar": "", "active": "false"},
        {"facet": "lang", "key": "ara", "label_en": "Arabic Alt", "label_ar": "العربية بديل", "active": "true"},
    ]

    errors, warnings = mod.validate_rows(rows)

    assert warnings == []
    assert any("duplicate active (facet,key)=(lang,ara)" in msg for msg in errors)


def test_validator_requires_labels_on_active_rows_only():
    mod = _load_validator_module()
    rows = [
        {"facet": "version", "key": "PRI", "label_en": "", "label_ar": "أساسي", "active": "true"},
        {"facet": "version", "key": "ALT", "label_en": "Alternate", "label_ar": "", "active": "true"},
        {"facet": "tags", "key": "GAL@test", "label_en": "", "label_ar": "", "active": "false"},
    ]

    errors, _warnings = mod.validate_rows(rows)

    assert any("active row missing label_en" in msg for msg in errors)
    assert any("active row missing label_ar" in msg for msg in errors)
