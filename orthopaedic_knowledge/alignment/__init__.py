"""المحاذاة: تطبيع + تقطيع + قاموس ثنائي + تشابه + ثقة مفككة + DP."""

from .aligner import Alignment, AlignmentResult, align, flag_issues
from .confidence import ConfidenceBreakdown, compute_confidence
from .embedder import build_embedder
from .lexicon import BilingualLexicon, get_default_lexicon, set_default_lexicon
from .normalizer import is_arabic, normalize_arabic, strip_diacritics
from .segmenter import segment_block, split_sentences
from .similarity import lexical_similarity


def make_sim_fn(embedder=None, settings=None):
    """اجمع (لفظي/قاموسي + دلالي + أرقام) في دالة واحدة تعيد (ثقة، تفكيك).

    ``embedder`` — مغلف ONNX محلي اختياري؛ ``settings`` — إعدادات اختيارية.
    """
    from .confidence import compute_confidence
    from .normalizer import is_arabic
    from .similarity import _cross_lingual_lexical, token_overlap

    def sim(a: str, b: str) -> tuple[float, dict]:
        if is_arabic(a) != is_arabic(b):
            lex = _cross_lingual_lexical(a, b)
        else:
            lex = token_overlap(a, b)
        sem = None
        if embedder is not None:
            sem = max(0.0, min(1.0, embedder.similarity(a, b)))
        score, br = compute_confidence(a, b, semantic=sem)
        return score, br.to_dict() | {"pairs_lexical": round(lex, 4)}

    return sim


__all__ = [
    "Alignment", "AlignmentResult", "align", "flag_issues",
    "ConfidenceBreakdown", "compute_confidence",
    "build_embedder", "BilingualLexicon", "get_default_lexicon", "set_default_lexicon",
    "is_arabic", "normalize_arabic", "strip_diacritics",
    "segment_block", "split_sentences", "lexical_similarity", "make_sim_fn",
]
