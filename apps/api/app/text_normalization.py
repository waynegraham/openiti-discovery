from __future__ import annotations

import re
import unicodedata

from .runtime_config import text_normalization_config


AR_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670]")
TATWEEL_RE = re.compile(r"\u0640")

# conservative character normalizations
CHAR_MAP = str.maketrans({
    "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا",
    "ة": "ه",
    "ؤ": "و",
    # Collapse all Ya/Maqsurah variants to the Persian 'ی'
    "ئ": "ی",
    "ى": "ی",
    "ي": "ی",
    # Standardize Kaf
    "ك": "ک",
})

# Regional digit standardization (Arabic to Persian)
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
DIGIT_MAP = str.maketrans(AR_DIGITS, FA_DIGITS)

# Expanded Regex to catch both standard and "invisible" whitespace
WHITESPACE_RE = re.compile(r"[\s\u00A0\u200B\u200C\u200D]+")

def normalize_arabic_script(s: str) -> str:
    # Prevents "TypeError: normalize() argument 2 must be str, not None"
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)

    cfg = text_normalization_config().get("pipeline") or {}

    # 0. Canonical normalization (NFKC)
    s = unicodedata.normalize('NFKC', s)

    # 1. Noise Removal
    if bool(cfg.get("remove_tatweel", True)):
        s = TATWEEL_RE.sub("", s)

    if bool(cfg.get("remove_diacritics", True)):
        s = AR_DIACRITICS_RE.sub("", s)

    # 2. Linguistic Mapping
    if any(
        bool(cfg.get(k, True))
        for k in (
            "normalize_alef_variants",
            "normalize_persian_kaf_ya",
            "normalize_hamza_conservative",
        )
    ):
        s = s.translate(CHAR_MAP)

    # 3. Digit Mapping
    if bool(cfg.get("normalize_digits", True)):
        s = s.translate(DIGIT_MAP)

    # 4. Whitespace Cleanup
    s = WHITESPACE_RE.sub(" ", s).strip()

    return s
