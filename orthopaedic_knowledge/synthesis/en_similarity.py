"""محرك التشابه إنجليزي↔إنجليزي — أساس ربط الكتب الخمسة.

بلا نموذج: تشابه معجمي (Containment) + تداخل الأرقام — محافظ ومفهوم.
مع نموذج ONNX محلي: متجهات دلالية مُشفَّرة دفعة واحدة تُدمج مع المعجمي.
لا شبكة في الحالتين؛ ومجلد نموذج محدد ومعطوب = فشل صريح (Fail-Closed).
"""

from __future__ import annotations

import re

_EN_STOP = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "and", "or", "is", "are", "was", "were", "be", "been", "may",
    "can", "this", "that", "its", "their", "when", "while", "into", "than",
    "then", "not", "no", "other", "such", "each", "most", "more", "less",
    "between", "after", "before", "during", "within", "without", "which",
    "these", "those", "it", "as", "also", "both", "but", "if", "so",
    # الأفعال المساعدة — لا محتوى موضوعياً فيها، وسقوطها يحسّن الاحتواء
    "should", "would", "must", "will", "shall", "do", "does", "did",
    "has", "have", "had",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
# أرقام تصنيفية: type/grade/stage/class + رقم أو رقم روماني (Garden type II)
_CLASS_NUM_RE = re.compile(
    r"\b(?:type|grade|stage|class|degree)\s+([IVXivx]{1,4}|\d+)\b"
)
# أسماء أنظمة التصنيف المسماة (Garden classification, Denis system, …)
_SYSTEM_RE = re.compile(
    r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})?)\s+"
    r"(classification|score|system|criteria|staging)\b"
)

_NEG_MODAL = ("contraindicated", "avoid", "should not", "must not", "not recommended", "no longer")
_POS_MODAL = ("recommended", "preferred", "indicated", "treatment of choice", "is the standard")


def tokens_en(text: str) -> list[str]:
    toks = _TOKEN_RE.findall(text.lower())
    return [t for t in toks if t not in _EN_STOP and len(t) > 1]


def numbers_en(text: str) -> set[str]:
    """الأرقام الحرفية + الأرقام التصنيفية (الرومانية تُطبَّع إلى ح بزرگ)."""
    found = set(_NUMBER_RE.findall(text))
    for m in _CLASS_NUM_RE.finditer(text):
        raw = m.group(1)
        found.add(raw.upper() if raw.isalpha() else raw)
    return found


def systems_en(text: str) -> set[str]:
    """أنظمة التصنيف المذكورة (Garden, Pauwels, Denis, …).
    تطبيع: تجريد أداة التعريف المطلقة «The» من بداية الاسم الملتقط."""
    return {
        m.group(1).replace("The ", "", 1) if m.group(1).startswith("The ") else m.group(1)
        for m in _SYSTEM_RE.finditer(text)
    }


def modality_en(text: str) -> str:
    """صيغة التوصية: neg / pos / none — أساس كشف تعارض التوصيات."""
    low = text.lower()
    neg = any(w in low for w in _NEG_MODAL)
    pos = any(w in low for w in _POS_MODAL)
    if neg and not pos:
        return "neg"
    if pos and not neg:
        return "pos"
    return "none"


def containment(a: list[str], b: list[str]) -> float:
    """|A∩B| / min(|A|,|B|) — الاحتواء أنسب من Jaccard للصياغات المختلفة."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / min(len(sa), len(sb))


def lexical_similarity(text_a: str, text_b: str) -> float:
    return round(containment(tokens_en(text_a), tokens_en(text_b)), 4)


def new_facts(other_text: str, spine_text: str, cap: int = 8) -> dict:
    """ما في وحدة الكتاب الآخر وغياب عن وحدة العمود الفقري — أساس DELTA."""
    spine_toks = set(tokens_en(spine_text))
    missing = [t for t in tokens_en(other_text) if t not in spine_toks]
    spine_nums = numbers_en(spine_text)
    return {
        "numbers": sorted(numbers_en(other_text) - spine_nums),
        "systems": sorted(systems_en(other_text) - systems_en(spine_text)),
        "missing_terms": missing[:cap],
    }


class SemanticScorer:
    """غلاف اختياري فوق OnnxEmbedder — تشفير دفعي مرة واحدة لكل كتاب."""

    def __init__(self, model_dir: str) -> None:
        from ..alignment.embedder import build_embedder

        # مجلد محدد ومعطوب → استثناء صريح هنا (لا سقوط صامت)
        self.embedder = build_embedder(model_dir)
        if self.embedder is None:  # لا يحدث مع model_dir غير فارغ — دفاعية
            raise RuntimeError("model_dir محدد لكن build_embedder أعاد None")

    def encode(self, texts: list[str]):
        return self.embedder.encode_all(texts)

    def similarity_matrix(self, spine_vecs, other_vecs) -> list[list[float]]:
        np = self.embedder._np
        sim = spine_vecs @ other_vecs.T          # متجهات مطبَّعة → cosine مباشرة
        return [[float(v) for v in row] for row in sim]
