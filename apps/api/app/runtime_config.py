from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    # apps/api/app/runtime_config.py -> repo root
    return Path(__file__).resolve().parents[3]


def _config_path(name: str) -> Path:
    return _repo_root() / "config" / name


@lru_cache(maxsize=1)
def search_runtime() -> dict[str, Any]:
    path = _config_path("search_runtime.yml")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data


@lru_cache(maxsize=1)
def text_normalization_config() -> dict[str, Any]:
    path = _config_path("text_normalization.yml")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data


@lru_cache(maxsize=1)
def normalization_version() -> str:
    cfg = text_normalization_config()
    val = cfg.get("version")
    return str(val) if val else "unknown"


@lru_cache(maxsize=1)
def facet_labels() -> dict[str, dict[str, str]]:
    path = _config_path("facet_labels.csv")
    if not path.exists():
        return {}

    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            active = str(row.get("active", "true")).strip().lower()
            if active not in ("1", "true", "yes"):
                continue
            facet = (row.get("facet") or "").strip()
            key = (row.get("key") or "").strip()
            label = (row.get("label_en") or "").strip()
            if not facet or not key or not label:
                continue
            out.setdefault(facet, {})[key] = label
    return out

