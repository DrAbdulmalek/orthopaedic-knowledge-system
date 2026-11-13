"""مصنف قرارات الدمج: DUPLICATE / DELTA / CONFLICT — بشفافية كاملة للأسباب.

قواعد التعارض الثلاث (تظهر للمراجع لحسمها ولا تُحسم آلياً أبداً):
1. numbers          — نفس الموضوع، مجموعتا أرقام متباينة تماماً (6 أسابيع ≠ 12).
2. classification   — نظاما تصنيف مُسمّيان مختلفان لنفس الإصابة (Garden ≠ Pauwels).
3. recommendation   — توصية سالبة مقابل موجبة على نفس الموضوع (يُفضَّل ≠ يُجنَّب).
"""

from __future__ import annotations

from .en_similarity import modality_en, new_facts, numbers_en, systems_en

CONFLICT_TYPES = ("numbers", "classification", "recommendation")


def detect_conflicts(spine_text: str, other_text: str) -> list[dict]:
    """اقرأ التعارضات الصلبة بين وحدتين مرتبطتين — كل نوع بدليله الموثق."""
    conflicts: list[dict] = []

    spine_nums, other_nums = numbers_en(spine_text), numbers_en(other_text)
    if (spine_nums and other_nums and spine_nums.isdisjoint(other_nums)
            and len(spine_nums) <= 5 and len(other_nums) <= 5):
        conflicts.append({
            "conflict_type": "numbers",
            "spine_detail": {"numbers": sorted(spine_nums)},
            "other_detail": {"numbers": sorted(other_nums)},
        })

    spine_sys, other_sys = systems_en(spine_text), systems_en(other_text)
    if spine_sys and other_sys and spine_sys.isdisjoint(other_sys):
        conflicts.append({
            "conflict_type": "classification",
            "spine_detail": {"systems": sorted(spine_sys)},
            "other_detail": {"systems": sorted(other_sys)},
        })

    spine_mod, other_mod = modality_en(spine_text), modality_en(other_text)
    if {spine_mod, other_mod} == {"pos", "neg"}:
        conflicts.append({
            "conflict_type": "recommendation",
            "spine_detail": {"modality": spine_mod},
            "other_detail": {"modality": other_mod},
        })
    return conflicts


def classify(
    score: float,
    lexical: float,
    semantic: float | None,
    spine_text: str,
    other_text: str,
    *,
    dup_threshold: float,
    link_floor: float,
) -> tuple[str, str, dict]:
    """أعد (decision, reason, new_facts) — قواعد مرتبة: التعارض ثم التكرار ثم الإضافة.

    التمييز الحاسم: «hard facts» جديدة (أرقام/أنظمة تصنيف) ترفع التطابق
    العالي إلى DELTA؛ أما الكلمات الناقصة المجردة (مرادفات صياغة) في
    التطابق العالي فلا — وإلا ما ضاع DUPLICATE أبداً.
    """
    facts = new_facts(other_text, spine_text)
    hard_new = bool(facts["numbers"] or facts["systems"])
    has_new = hard_new or bool(facts["missing_terms"])
    if score >= link_floor:
        if detect_conflicts(spine_text, other_text):
            return "CONFLICT", "موضوع واحد بأدلة متعارضة — بانتظار حسم المراجع", facts
        if score >= dup_threshold:
            if hard_new:
                return "DELTA", f"تطابق {score:.2f} مع حقائق رقمية/تصنيفية جديدة فوق مرساة العمود الفقري", facts
            return "DUPLICATE", f"تطابق {score:.2f} بلا معلومات جديدة — يكفي إثبات العمود الفقري", facts
        if has_new:
            return "DELTA", f"ارتباط جزئي {score:.2f} مع معلومات غير موجودة في العمود الفقري", facts
        return "DUPLICATE", f"إعادة صياغة لنفس المعلومة (تطابق {score:.2f}) بلا إضافات", facts
    return "DELTA", f"بلا مرساة في العمود الفقري (أعلى تطابق {score:.2f}) — معلومة مستقلة", facts
