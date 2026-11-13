"""تقطيع الجمل بمحاكاة SRX — مضبوط للنص الطبي (اختصارات، كسور عشرية، عربي)."""

from __future__ import annotations

import re

_ABBREVIATIONS = {
    "fig", "figs", "e.g", "i.e", "vs", "cf", "approx", "no", "nos", "vol",
    "pp", "p", "ch", "ed", "eds", "et al", "al", "dr", "prof", "jr", "st",
    "inc", "ltd", "dept", "tab", "tbl", "post-op", "pre-op", "intra-op",
    "د", "أ.د", "الط", "ص",
}
_PLACE = "\x00"
_ABBREV_RE = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in sorted(_ABBREVIATIONS, key=len, reverse=True)) + r")\.",
    re.IGNORECASE,
)
_DECIMAL_RE = re.compile(r"(?<=\d)\.(?=\d)")
_BOUNDARY_RE = re.compile(r"(?<=[.!?؟…])\s+(?=(?:[A-Z0-9(\"'\u0600-\u06FF]))")


def split_sentences(text: str, lang: str = "en") -> list[str]:
    """قسّم فقرة إلى جمل مع حماية الاختصارات والأرقام العشرية."""
    if not text or not text.strip():
        return []
    protected = _DECIMAL_RE.sub(_PLACE, _ABBREV_RE.sub(r"\1" + _PLACE, text.strip()))
    parts = _BOUNDARY_RE.split(protected)
    return [p.replace(_PLACE, ".").strip() for p in parts if p and p.strip()]


def segment_block(block_text: str, lang: str) -> list[str]:
    """جمل كتلة واحدة — الكتلة هي وحدة التخطيط والجملة وحدة المحاذاة."""
    return split_sentences(block_text, lang)
