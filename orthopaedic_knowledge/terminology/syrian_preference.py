"""ترجيح المصطلحات السورية — المبدأ 5 في المبادئ المعمارية.

عند تعدد المرادفات العربية لمفهوم واحد:
* المصطلح السوري المعتمد (في القائمة المحمية أدناه أو في مسرد المستخدم)
  يُمنح الوزن الأعلى ويصبح preferred (اقتراحاً).
* البقية تُحفظ كـ Contextual Synonyms مع سياق ظهورها — لا تُحذف أبداً.

القرار النهائي للمراجع البشري؛ هذا المقيّم يقترح فقط (UNPROVEN).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..alignment.normalizer import normalize_arabic

# البذرة السورية المعتمدة — تُوسَّع من مسرد المستخدم عبر from_csv()
SYRIAN_SEED: set[str] = {
    # (بعد التطبيع) مصطلحات الاستخدام الطبي السوري المعتاد
    "جبس",            # plaster cast
    "جبيره",          # splint
    "غرفه العمليات",  # operating room
    "صوره شعاعيه",    # X-ray film
    "اشعه",           # X-ray
    "طعم عظمي",       # bone graft
    "غرز",            # sutures
    "اسعاف",          # ambulance
    "مستشفى",         # hospital
    "عياده الكسور",   # fracture clinic
    "ممرض",           # nurse
    "طبيب",           # physician
    "خمج",            # infection (الاستخدام الشامي/السوري)
    "كدمه",           # bruise
    "التواء",         # sprain
}


def load_syrian_lexicon_csv(path: str) -> set[str]:
    """حمّل قائمة مصطلحات سورية معتمدة من CSV محلي (عمود واحد، UTF-8،
    سطور # تعليقات). يعيد مجموعة مطبَّعة جاهزة للتمرير إلى choose_preferred
    وstore_all — مسار توسيع المحمي دون تعديل الكود."""
    import csv
    from pathlib import Path

    lexicon: set[str] = set()
    with Path(path).open(encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if row and row[0].strip() and not row[0].startswith("#"):
                lexicon.add(normalize_arabic(row[0]))
    return lexicon


@dataclass(frozen=True)
class PreferenceDecision:
    """نتيجة الترجيح — الشفافية إلزامية."""

    preferred: str
    dialect_weight: float
    contextual_synonyms: tuple[str, ...]
    reason: str


def _norm(term: str) -> str:
    return normalize_arabic(term)


def syrian_weight(ar_term: str, extra_lexicon: set[str] | None = None) -> float:
    """1.0 إن كان المصطلح ضمن المحمي السوري، وإلا 0.0.

    يقبل الشكل المعرف (الجبس → جبس) — المطابقة على الجذر بلا «ال».
    """
    lexicon = SYRIAN_SEED | (extra_lexicon or set())
    n = _norm(ar_term)
    if n in lexicon:
        return 1.0
    if len(n) > 4 and n.startswith("ال") and n[2:] in lexicon:
        return 1.0
    return 0.0


def choose_preferred(
    variants: dict[str, int] | Counter,
    extra_lexicon: set[str] | None = None,
    syrian_weight_value: float = 1.0,
    frequency_weight: float = 0.5,
) -> PreferenceDecision:
    """اختر المصطلح المفضل: الترجيح السوري أولاً ثم التواتر.

    score = syrian_weight * W_s + normalized_frequency * W_f
    """
    items = list(dict(variants).items())
    if not items:
        return PreferenceDecision("", 0.0, (), "لا مرادفات")
    max_freq = max(c for _, c in items) or 1
    scored = sorted(
        items,
        key=lambda kv: (
            syrian_weight(kv[0], extra_lexicon) * syrian_weight_value
            + (kv[1] / max_freq) * frequency_weight,
            kv[1],
        ),
        reverse=True,
    )
    preferred, pref_count = scored[0]
    w = syrian_weight(preferred, extra_lexicon)
    if w > 0:
        reason = f"مصطلح سوري معتمد (وزن {w}) + تواتر {pref_count}"
    else:
        reason = f"أعلى تواتر ({pref_count}) — لا مقابل سوري في المحمي"
    return PreferenceDecision(
        preferred=preferred,
        dialect_weight=w,
        contextual_synonyms=tuple(t for t, _ in scored[1:]),
        reason=reason,
    )
