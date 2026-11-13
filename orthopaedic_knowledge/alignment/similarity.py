"""مقاييس التشابه — لغوي (دائماً متاح) وثنائي اللغة عبر القاموس البذري."""

from __future__ import annotations

import math
import re

from .normalizer import is_arabic, normalize_arabic

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+(?:[-'][\w\u0600-\u06FF]+)*", re.UNICODE)
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

_EN_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "as", "is", "are", "was", "were", "be", "been", "may", "can",
    "and", "or", "but", "not", "its", "this", "that", "these", "those",
    "it", "their", "when", "while", "into", "than", "then", "such", "other",
}
_AR_STOPWORDS = {
    "في", "من", "على", "إلى", "عن", "مع", "أو", "او", "و", "هذا", "هذه",
    "ذلك", "التي", "الذي", "قد", "لا", "ما", "هو", "هي", "بين", "عند",
    "كل", "بعد", "قبل", "حيث", "لكن", "أن", "ان", "إن",
}


def tokenize(text: str) -> list[str]:
    if is_arabic(text or ""):
        return _TOKEN_RE.findall(normalize_arabic(text or ""))
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def content_tokens(text: str) -> list[str]:
    toks = tokenize(text)
    stops = _AR_STOPWORDS if is_arabic(text or "") else _EN_STOPWORDS
    return [t for t in toks if t not in stops and len(t) > 1]


def token_overlap(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(set(ta) & set(tb)) / len(set(ta) | set(tb))


def char_ngram_similarity(a: str, b: str, n: int = 3) -> float:
    def grams(s: str) -> set[str]:
        s = " ".join(content_tokens(s))
        return {s[i : i + n] for i in range(len(s) - n + 1)} if len(s) >= n else ({s} if s else set())

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def numbers(text: str) -> set[str]:
    return {m.group().replace(",", ".") for m in _NUM_RE.finditer(text or "")}


def number_match(a: str, b: str) -> float:
    na, nb = numbers(a), numbers(b)
    if not na and not nb:
        return 0.5      # محايد: لا عقوبة على النثر الخالي من الأرقام
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)


def length_ratio_penalty(a: str, b: str, sigma: float = 0.45) -> float:
    la, lb = len((a or "").strip()), len((b or "").strip())
    if la == 0 or lb == 0:
        return 0.0
    ratio = lb / la
    if not (0.1 < ratio < 10.0):
        return 0.05
    return math.exp(-0.5 * (math.log(ratio) / sigma) ** 2)


def _cross_lingual_lexical(src: str, tgt: str) -> float:
    """تشابه لفظي لزوج ثنائي اللغة عبر القاموس البذري (الجانب اللفظي فقط)."""
    from .lexicon import get_default_lexicon

    en, ar = (tgt, src) if is_arabic(src) else (src, tgt)
    return get_default_lexicon().overlap(en, ar)


def lexical_similarity(a: str, b: str) -> float:
    """ثنائي اللغة: 0.72 قاموس + 0.28 أرقام | أحادي: 0.55 لفظي + 0.30 محارف + 0.15 أرقام."""
    if not (a or "").strip() or not (b or "").strip():
        return 0.0
    if is_arabic(a) != is_arabic(b):
        base = 0.72 * _cross_lingual_lexical(a, b) + 0.28 * number_match(a, b)
        return base * length_ratio_penalty(a, b)
    base = 0.55 * token_overlap(a, b) + 0.30 * char_ngram_similarity(a, b) + 0.15 * number_match(a, b)
    return base * length_ratio_penalty(a, b)
