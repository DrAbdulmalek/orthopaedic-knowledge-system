"""المصطلحات: MWT + مخزن مفاهيم + ترجيح سوري."""

from .concept_store import detect_conflicts, store_all, store_candidate
from .mwt_extractor import TermCandidate, extract_terms
from .normalizer_ar import norm_ar, norm_en
from .syrian_preference import PreferenceDecision, choose_preferred, syrian_weight

__all__ = [
    "extract_terms", "TermCandidate", "store_candidate", "store_all", "detect_conflicts",
    "choose_preferred", "PreferenceDecision", "syrian_weight", "norm_en", "norm_ar",
]
