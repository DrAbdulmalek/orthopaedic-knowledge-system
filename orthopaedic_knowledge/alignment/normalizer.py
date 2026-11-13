"""تطبيع النص العربي لمطابقة المصطلحات — تحفظي (لا يدمج معاني مختلفة)."""

from __future__ import annotations

import re
import unicodedata

_TASHKEEL_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_ALEF_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
_MAQSURA = str.maketrans({"ى": "ي"})
_AR_LETTER_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def normalize_arabic(text: str, unify_taa_marbuta: bool = True) -> str:
    """تطبيع المطابقة: NFKC ← حذف تشكيل وتطويل ← توحيد همزات ← ى→ي ← ة→ه.

    لا يُطبَّق على النص المعروض — على فهارس المطابقة فقط.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = _TASHKEEL_RE.sub("", out)
    out = out.replace(_TATWEEL, "")
    out = out.translate(_ALEF_MAP)
    out = out.translate(_MAQSURA)
    if unify_taa_marbuta:
        out = out.replace("ة", "ه")
    return " ".join(out.split()).strip()


def strip_diacritics(text: str) -> str:
    """حذف التشكيل والتطويل فقط — دون توحيد الحروف."""
    out = _TASHKEEL_RE.sub("", unicodedata.normalize("NFKC", text or ""))
    return out.replace(_TATWEEL, "")


def is_arabic(text: str) -> bool:
    return bool(_AR_LETTER_RE.search(text or ""))
