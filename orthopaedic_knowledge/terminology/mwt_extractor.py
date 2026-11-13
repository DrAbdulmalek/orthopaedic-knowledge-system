"""استخراج المصطلحات المركبة (MWT) من أزواج المحاذاة.

كل مرشح يُولد UNPROVEN بالضرورة — المحرك يقترح ولا يعتمد أبداً.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..alignment.similarity import tokenize

EN_STOP_EDGES = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "and", "or", "is", "are", "was", "were", "be", "may", "can",
    "this", "that", "its", "their", "when", "while", "into", "than", "then",
    "not", "no", "other", "such", "each", "most", "more", "less", "between",
    "after", "before", "during", "within", "without", "which", "these", "those",
}
AR_STOP_EDGES = {
    "في", "من", "على", "إلى", "عن", "مع", "أو", "او", "و", "هذا", "هذه",
    "التي", "الذي", "قد", "لا", "ما", "هو", "هي", "بين", "عند", "كل", "بعد",
    "قبل", "حيث", "لكن", "أن", "ان", "إن", "ا",
}

MEDICAL_HINTS = (
    "fracture", "necrosis", "artery", "vein", "nerve", "joint", "bone",
    "ligament", "tendon", "cartilage", "femoral", "tibial", "pelvic",
    "arthroplasty", "osteosynthesis", "fixation", "dislocation", "syndrome",
    "classification", "necrosis", "cast",
)


@dataclass
class TermCandidate:
    en_term: str
    en_norm: str
    count: int
    ar_variants: Counter = field(default_factory=Counter)
    example_alignments: list[int] = field(default_factory=list)

    @property
    def preferred_ar(self) -> str | None:
        return self.ar_variants.most_common(1)[0][0] if self.ar_variants else None

    def to_dict(self) -> dict:
        return {
            "en_term": self.en_term, "en_norm": self.en_norm, "count": self.count,
            "ar_variants": dict(self.ar_variants.most_common()),
            "example_alignments": self.example_alignments[:10],
            "preferred_ar": self.preferred_ar,
        }


def _en_ngrams(tokens: list[str], lo: int = 1, hi: int = 4):
    for size in range(lo, hi + 1):
        for i in range(len(tokens) - size + 1):
            yield tokens[i : i + size]


def extract_en_candidates(src_texts: list[str]) -> Counter:
    """عدّاد n-grams الإنجليزية التي لا تبدأ/تنتهي بكلمة وظيفية."""
    counts: Counter = Counter()
    for text in src_texts:
        toks = tokenize(text)
        for gram in _en_ngrams(toks):
            if gram[0] in EN_STOP_EDGES or gram[-1] in EN_STOP_EDGES:
                continue
            if len(gram[0]) < 2 or len(gram[-1]) < 2:
                continue
            counts[" ".join(gram)] += 1
    return counts


def _score(candidate: str, count: int) -> float:
    words = candidate.split()
    score = float(count) * (1.0 + 0.15 * (len(words) - 1))
    if any(h in candidate.lower() for h in MEDICAL_HINTS):
        score *= 1.6
    return score


def _ar_variants(text: str, allowed: set[str], lo: int = 1, hi: int = 2) -> Counter:
    """مرشحات عربية موثوقة فقط (أحاديات + ثنائيات): يُقبل n-gram إن احتوى
    رمزاً مرسوماً في القاموس البذري لمصطلح المصدر — لا روابط بلا دليل معجمي."""
    if not allowed:
        return Counter()
    variants: Counter = Counter()
    toks = tokenize(text)
    for size in range(lo, hi + 1):
        for i in range(len(toks) - size + 1):
            span = toks[i : i + size]
            if span[0] in AR_STOP_EDGES or span[-1] in AR_STOP_EDGES:
                continue
            surface: set[str] = set()
            from ..alignment.lexicon import _ar_variants as _tok_variants

            for tok in span:
                surface |= _tok_variants(tok)
            if surface & allowed:
                variants[" ".join(span)] += 1
    return variants


def _seed_tokens_for(en_gram: str) -> set[str]:
    """الرموز العربية المرسومة في القاموس لرموز مصطلح المصدر."""
    from ..alignment.lexicon import _en_stems, get_default_lexicon

    lexicon = get_default_lexicon()
    allowed: set[str] = set()
    for et in en_gram.lower().split():
        for stem in _en_stems(et):
            for group in lexicon.groups.get(stem, ()):
                allowed |= set(group)
    return allowed


def _minimal_spans(counter: Counter, allowed: set[str], cap: int = 3) -> Counter:
    """أدنى مدى مرسوم (Minimal Mapped Span): المرشح يُسقط إن كان **جزء منه**
    مرشحاً بنفسه — «ازيل الجبس» يُسقط لأن «الجبس» وحدها مرسومة في القاموس.
    النتيجة: تصاميم نقية قصيرة بدل عبارات فعلية/مركبة ضجيجية."""
    from ..alignment.lexicon import _ar_variants as tok_vars

    def is_mapped(span: tuple[str, ...]) -> bool:
        return any(tok_vars(t) & allowed for t in span)

    kept: list[str] = []
    for gram in sorted(counter.keys(), key=lambda g: (len(g.split()), g)):
        toks = tuple(gram.split())
        if len(toks) > 1 and any(is_mapped(toks[i : i + size])
                                 for size in range(1, len(toks))
                                 for i in range(len(toks) - size + 1)):
            continue
        kept.append(gram)
    kept.sort(key=lambda g: (-counter[g], len(g.split()), g))
    return Counter({g: counter[g] for g in kept[:cap]})


def extract_terms(aligned_pairs: list[dict], min_count: int = 1, top_k: int | None = None) -> list[TermCandidate]:
    """استخرج مرشحات ثنائية من سجلات المحاذاة (المحاذى فقط — UNALIGNED مستبعد).

    أداء O(total_gram_instances): المرشحات تُشتق من جملة كل زوج نفسها في
    ممر واحد — لا مسح شامل لكل ``counts`` عند كل زوج (كان O(N²) ويجمّد على
    كتاب كامل)، ولا حاجة لفحص الوجود لاحقاً لأن الاشتقاق من النص نفسه.
    """
    counts: Counter = Counter()
    occurrences: defaultdict[str, list[int]] = defaultdict(list)
    ar_counter: defaultdict[str, Counter] = defaultdict(Counter)
    seed_cache: dict[str, set[str]] = {}

    for pair in aligned_pairs:
        if pair["align_type"].startswith("UNALIGNED"):
            continue
        aid = pair["alignment_id"]
        src_join = " ".join(s["text"] for s in pair["src"])
        tgt_join = " ".join(t["text"] for t in pair["tgt"])
        for gram, c in extract_en_candidates([src_join]).items():
            counts[gram] += c
            occurrences[gram].append(aid)
            allowed = seed_cache.get(gram)
            if allowed is None:
                allowed = _seed_tokens_for(gram)
                seed_cache[gram] = allowed
            if allowed:
                ar_counter[gram].update(_ar_variants(tgt_join, allowed))

    candidates = [
        TermCandidate(
            en_term=g, en_norm=g.lower(), count=c,
            ar_variants=_minimal_spans(ar_counter.get(g, Counter()), seed_cache[g]),
            example_alignments=occurrences.get(g, [])[:10],
        )
        for g, c in counts.items()
        if c >= min_count
    ]
    candidates.sort(key=lambda c: _score(c.en_term, c.count), reverse=True)
    return candidates[:top_k] if top_k else candidates
