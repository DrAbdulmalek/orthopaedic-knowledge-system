"""أدوات التطبيع المعجمية المشتركة بين وحدات المصطلحات."""

from __future__ import annotations

from ..alignment.normalizer import normalize_arabic
from ..alignment.similarity import tokenize


def norm_en(term: str) -> str:
    """تطبيع المطابقة الإنجليزي: توكين + lowercase."""
    return " ".join(tokenize(term))


def norm_ar(term: str) -> str:
    """تطبيع المطابقة العربي."""
    return normalize_arabic(term)
