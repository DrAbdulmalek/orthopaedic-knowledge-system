from orthopaedic_knowledge.alignment import align, flag_issues, make_sim_fn
from orthopaedic_knowledge.alignment.lexicon import BilingualLexicon
from orthopaedic_knowledge.alignment.similarity import lexical_similarity

from pilot.femoral_neck_chapter import AR_SENTENCES, EN_SENTENCES

SIM = make_sim_fn()


def _texts(pairs):
    return [t for _, t in pairs]


def test_lexicon_overlap_true_vs_false_pair():
    lex = BilingualLexicon()
    true_pair = lex.overlap(_texts(EN_SENTENCES)[0], _texts(AR_SENTENCES)[0])
    false_pair = lex.overlap(_texts(EN_SENTENCES)[0], _texts(AR_SENTENCES)[9])
    assert true_pair > 0.5
    assert true_pair > false_pair + 0.2


def test_monolingual_perfect_pairs():
    src = ["Osteosynthesis preserves the femoral head.", "Early mobilization reduces risk."]
    result = align(src, src, SIM)
    assert [a.align_type for a in result.alignments] == ["1:1", "1:1"]
    # 0.72×1.0 + 0.28×0.5 (أرقام محايدة) = 0.86 — عتبة مقصودة أدنى من 1
    assert all(a.confidence > 0.8 for a in result.alignments)


def test_bilingual_chapter_mostly_aligned():
    result = align(_texts(EN_SENTENCES), _texts(AR_SENTENCES), SIM)
    types = [a.align_type for a in result.alignments]
    assert types.count("1:1") == 11          # 12 جملة مصدر، إحداها 1:2
    assert "1:2" in types                     # انقسام المترجم مُلتقط
    assert result.skipped_src == 0 and result.skipped_tgt == 0


def test_omission_surfaces_as_unaligned():
    # حذف جملتَي الجبس (محتواهما فريد في نهاية الفصل) — لا يوجد مقابل منزاح
    result = align(_texts(EN_SENTENCES), _texts(AR_SENTENCES)[:-2], SIM)
    types = [a.align_type for a in result.alignments]
    assert types.count("UNALIGNED") == 2
    flags = flag_issues(result)
    assert any(f["flag_type"] == "SUSPECTED_OMISSION" for f in flags)
    # الجملتان المفقودتان هما الأخيرتان تحديداً (10 و11)
    assert result.alignments[-1].is_unaligned and 11 in result.alignments[-1].src_indexes
    assert result.alignments[-2].is_unaligned and 10 in result.alignments[-2].src_indexes


def test_unrelated_texts_do_not_align():
    src = ["Quarterly revenue increased.", "The committee approved the budget."]
    result = align(src, _texts(AR_SENTENCES), SIM)
    assert all(a.confidence < 0.4 for a in result.alignments if not a.is_unaligned)


def test_broken_sim_fn_is_fail_closed():
    def broken(a, b):
        raise RuntimeError("انفجار متعمد")
    result = align(["a", "b"], ["x", "y"], broken)
    # لا محاذاة مختلقة: كل شيء UNALIGNED
    assert all(a.align_type == "UNALIGNED" for a in result.alignments)
