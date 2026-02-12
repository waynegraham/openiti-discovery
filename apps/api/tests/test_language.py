from __future__ import annotations

from app import language


def test_normalize_language_tag_uses_alias_mapping():
    assert language.normalize_language_tag("ara") == "ar"
    assert language.normalize_language_tag("ENG") == "en"
    assert language.normalize_language_tag("fas") == "fa"


def test_normalize_language_tag_returns_unknown_for_missing_or_unmapped():
    assert language.normalize_language_tag("") == "unknown"
    assert language.normalize_language_tag(None) == "unknown"
    assert language.normalize_language_tag("zzz") == "unknown"


def test_configured_supported_languages_defaults_to_ar_en(monkeypatch):
    monkeypatch.setattr(language.settings, "SUPPORTED_LANGUAGES", "")
    assert language.configured_supported_languages() == ["ar", "en"]


def test_normalize_language_values_deduplicates_and_normalizes():
    assert language.normalize_language_values(["ara", "ar", "eng", "zzz"]) == ["ar", "en", "unknown"]
