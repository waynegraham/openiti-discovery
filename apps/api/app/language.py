from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from .settings import settings


CANONICAL_LANGUAGES = ("ar", "en", "fa")
UNKNOWN_LANGUAGE = "unknown"

_LANG_TOKEN_RE = re.compile(r"[a-z]{2,3}(?:\d+)?(?:-[a-z0-9]{2,8})?")


def _repo_root() -> Path:
    # apps/api/app/language.py -> repo root
    return Path(__file__).resolve().parents[3]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _normalize_token(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


@lru_cache(maxsize=1)
def language_aliases() -> dict[str, str]:
    path = _repo_root() / settings.LANGUAGE_ALIASES_FILE
    aliases: dict[str, str] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw_aliases = data.get("aliases") if isinstance(data, dict) else {}
        if isinstance(raw_aliases, dict):
            for raw_key, raw_value in raw_aliases.items():
                key = _normalize_token(str(raw_key))
                value = _normalize_token(str(raw_value))
                if key and value in (*CANONICAL_LANGUAGES, UNKNOWN_LANGUAGE):
                    aliases[key] = value

    # Always keep canonical identities available.
    for lang in CANONICAL_LANGUAGES:
        aliases.setdefault(lang, lang)
    aliases.setdefault(UNKNOWN_LANGUAGE, UNKNOWN_LANGUAGE)
    return aliases


def normalize_language_tag(value: str | None) -> str:
    normalized = _normalize_token(value)
    if not normalized:
        return UNKNOWN_LANGUAGE
    mapped = language_aliases().get(normalized)
    if mapped:
        return mapped
    # OpenITI path/version suffixes often encode language as ara1/eng1/fas1.
    normalized_no_suffix = re.sub(r"\d+$", "", normalized)
    if normalized_no_suffix != normalized:
        mapped = language_aliases().get(normalized_no_suffix)
        if mapped:
            return mapped
    return UNKNOWN_LANGUAGE


def configured_supported_languages() -> list[str]:
    langs: list[str] = []
    for raw in _split_csv(settings.SUPPORTED_LANGUAGES):
        normalized = normalize_language_tag(raw)
        if normalized == UNKNOWN_LANGUAGE:
            continue
        if normalized not in langs:
            langs.append(normalized)
    return langs or ["ar", "en"]


def normalize_language_values(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for raw in values:
        normalized = normalize_language_tag(raw)
        if normalized not in out:
            out.append(normalized)
    return out or None


def infer_language_from_text(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return UNKNOWN_LANGUAGE

    for token in _LANG_TOKEN_RE.findall(raw.lower()):
        normalized = normalize_language_tag(token)
        if normalized != UNKNOWN_LANGUAGE:
            return normalized
    return normalize_language_tag(raw)
