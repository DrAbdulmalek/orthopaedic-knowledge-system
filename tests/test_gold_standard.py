"""اختبار المعيار الذهبي المصغر — دقة المحاذاة تقاس ولا تُدّعى."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orthopaedic_knowledge.alignment import align, make_sim_fn

from pilot.femoral_neck_chapter import AR_SENTENCES, EN_SENTENCES, GOLD_PAIRS

SIM = make_sim_fn()


def _gold_sets():
    gold_aligned = set()
    for g in GOLD_PAIRS:
        tgts = g["tgt"] if isinstance(g["tgt"], list) else [g["tgt"]]
        for t in tgts:
            gold_aligned.add((g["src"], t))
    return gold_aligned


def test_gold_standard_f1_threshold():
    result = align(
        [t for _, t in EN_SENTENCES], [t for _, t in AR_SENTENCES], SIM
    )
    gold = _gold_sets()
    predicted = set()
    for a in result.alignments:
        if a.is_unaligned:
            continue
        for s in a.src_indexes:
            for t in a.tgt_indexes:
                predicted.add((s, t))

    tp = len(gold & predicted)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    # عتبة قبول صريحة للنسخة الأولى (تُشدَّد تدريجياً مع توسع المعيار الذهبي)
    assert f1 >= 0.90, f"F1={f1:.3f} P={precision:.3f} R={recall:.3f} tp={tp} fp={fp} fn={fn}"


def test_gold_1_to_2_detected():
    result = align(
        [t for _, t in EN_SENTENCES], [t for _, t in AR_SENTENCES], SIM
    )
    split_found = any(
        len(a.tgt_indexes) == 2 and 5 in a.src_indexes
        for a in result.alignments
        if not a.is_unaligned
    )
    assert split_found, "انقسام المترجم (جملة 6 → جملتان) لم يُلتقط"
