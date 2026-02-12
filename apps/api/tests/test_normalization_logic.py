from __future__ import annotations

import unicodedata
import pytest

from app.text_normalization import normalize_arabic_script, CHAR_MAP, DIGIT_MAP, WHITESPACE_RE

def test_nfkc_normalization_stability():
    """Verify that decomposed characters are stabilized before mapping."""
    # Lam-Alef ligature can be stored as one point or two.
    # NFKC should collapse them.
    decomposed = "\u0644\u0627" # ل + ا
    composed = "\uFEFB"         # لا
    assert normalize_arabic_script(decomposed) == normalize_arabic_script(composed)

def test_ya_and_maqsurah_unification():
    """
    Verify the 'Unified Persian' requirement:
    All Ya variants (Arabic, Maqsurah, Hamza-on-Ya) must become Persian Yeh.
    """
    arabic_ya = "ي"          # U+064A
    alif_maqsurah = "ى"      # U+0649
    hamza_on_ya = "ئ"       # U+0626
    persian_yeh = "ی"        # U+06CC

    assert normalize_arabic_script(arabic_ya) == persian_yeh
    assert normalize_arabic_script(alif_maqsurah) == persian_yeh
    assert normalize_arabic_script(hamza_on_ya) == persian_yeh

def test_kaf_standardization():
    """Ensure Arabic Kaf collapses to Persian Kaf."""
    arabic_kaf = "ك"  # U+0643
    persian_kaf = "ک" # U+06A9
    assert normalize_arabic_script(arabic_kaf) == persian_kaf

def test_digit_conversion():
    """Verify Arabic numerals are converted to Persian numerals."""
    arabic_num = "٠١٢٣٤٥٦٧٨٩"
    persian_num = "۰۱۲۳۴۵۶۷۸۹"
    assert normalize_arabic_script(arabic_num) == persian_num

def test_invisible_whitespace_and_zwnj():
    """
    Ensure WHITESPACE_RE treats ZWNJ and non-breaking spaces as word breaks.
    """
    # Use Unicode escapes for everything to be 100% sure
    # می (m-y) + ZWNJ + روم (r-w-m)
    # \u0631 is the Persian/Arabic 'Reh' ر
    zwnj_text = "\u0645\u064A\u200C\u0631\u0648\u0645"
    normalized = normalize_arabic_script(zwnj_text)

    # It should replace the ZWNJ with a space, resulting in "می روم"
    assert " " in normalized

    # Expected: Persian Meem + Yeh + Space + REH + Waw + Meem
    expected = "\u0645\u06CC \u0631\u0648\u0645"
    assert normalized == expected

def test_diacritic_and_tatweel_removal():
    """Verify stripping of harakat and kashida."""
    text = "كِتَــــابٌ" # 'Kitab' with tatweel and multiple diacritics
    normalized = normalize_arabic_script(text)
    # Result should be Persian Kaf and no noise
    assert normalized == "کتاب"

def test_alef_variant_collapse():
    """Verify all Alif chairs collapse to a plain Alif."""
    variants = ["أ", "إ", "آ", "ٱ"]
    for v in variants:
        assert normalize_arabic_script(v) == "ا"

def test_empty_and_whitespace_only_handling():
    """Ensure the function is resilient to empty inputs."""
    assert normalize_arabic_script("") == ""
    assert normalize_arabic_script("   ") == ""
    assert normalize_arabic_script(None) == ""
