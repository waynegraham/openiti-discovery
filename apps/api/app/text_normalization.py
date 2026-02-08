from __future__ import annotations

import re

from .runtime_config import text_normalization_config


AR_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670]")
TATWEEL_RE = re.compile(r"\u0640")

CHAR_MAP = str.maketrans(
    {
        "\u0671": "\u0627",  # ٱ -> ا
        "\u0623": "\u0627",  # أ -> ا
        "\u0625": "\u0627",  # إ -> ا
        "\u0622": "\u0627",  # آ -> ا
        "\u0649": "\u064A",  # ى -> ي
        "\u0629": "\u0647",  # ة -> ه
        "\u0624": "\u0648",  # ؤ -> و
        "\u0626": "\u064A",  # ئ -> ي
        "\u0643": "\u06A9",  # ك -> ک
        "\u064A": "\u06CC",  # ي -> ی
    }
)


def normalize_arabic_script(s: str) -> str:
    cfg = text_normalization_config().get("pipeline") or {}

    if bool(cfg.get("remove_tatweel", True)):
        s = TATWEEL_RE.sub("", s)
    if bool(cfg.get("remove_diacritics", True)):
        s = AR_DIACRITICS_RE.sub("", s)
    if any(
        bool(cfg.get(k, True))
        for k in (
            "normalize_alef_variants",
            "normalize_persian_kaf_ya",
            "normalize_hamza_conservative",
        )
    ):
        s = s.translate(CHAR_MAP)

    s = re.sub(r"\s+", " ", s).strip()
    return s

