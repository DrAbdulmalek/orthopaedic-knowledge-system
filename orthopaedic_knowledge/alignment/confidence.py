"""درجة الثقة المركبة — مفككة دائماً (لا رقم بلا تفسير)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .normalizer import is_arabic
from .similarity import _cross_lingual_lexical, length_ratio_penalty, number_match, token_overlap


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """تفكيك درجة الثقة — يُخزَّن JSON بجوار كل محاذاة."""

    lexical: float        # تشابه لفظي/قاموسي 0..1
    semantic: float | None  # تضمينات ONNX محلية إن توفرت، وإلا None
    numbers: float        # مطابقة الأرقام (0.5 محايد)
    length_ratio: float   # عقوبة نسبة الأطوال

    def composite(self, w_lex: float = 0.5, w_sem: float = 0.4, w_num: float = 0.1) -> float:
        """الوزن الدلالي يُعاد توزيعه على اللفظي عندما لا يوجد نموذج محلي."""
        if self.semantic is None:
            score = 0.72 * self.lexical + 0.28 * self.numbers
        else:
            score = w_lex * self.lexical + w_sem * max(0.0, min(1.0, self.semantic)) + w_num * self.numbers
        return round(min(1.0, max(0.0, score)) * self.length_ratio, 4)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_confidence(src: str, tgt: str, semantic: float | None = None) -> tuple[float, ConfidenceBreakdown]:
    """احسب الثقة وأعدها مع تفكيكها — نفس الدالة يفحصها اختبار Gold Standard."""
    lex = token_overlap(src, tgt) if is_arabic(src) == is_arabic(tgt) else _cross_lingual_lexical(src, tgt)
    br = ConfidenceBreakdown(
        lexical=round(lex, 4),
        semantic=round(semantic, 4) if semantic is not None else None,
        numbers=number_match(src, tgt),
        length_ratio=round(length_ratio_penalty(src, tgt), 4),
    )
    return br.composite(), br
