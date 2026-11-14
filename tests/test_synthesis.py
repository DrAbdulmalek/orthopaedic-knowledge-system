"""اختبارات وحدة التوليف (المرحلة 2) — orthok synthesize.

كل قرار (DUPLICATE/DELTA/CONFLICT) يُختبر على مستوى القواعد ثم على مستوى
الدمج الثلاثي الوهمي الرسمي (MILLER + ROCKWOOD + APLEY) من طرف إلى طرف.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from orthopaedic_knowledge.ingestion.models import TextBlock
from orthopaedic_knowledge.synthesis import (
    build_units,
    classify,
    detect_conflicts,
    run_synthesis,
)
from orthopaedic_knowledge.synthesis.en_similarity import (
    containment,
    lexical_similarity,
    modality_en,
    new_facts,
    numbers_en,
    systems_en,
    tokens_en,
)
from orthopaedic_knowledge.synthesis.models import Unit
from pilot.run_synthesis_demo import run_official_synthesis_demo
from pilot.synthesis_demo import APLEY_UNITS, MILLER_UNITS, build_demo_documents


# ───────────────────── 1) الاستخلاص: أرقام/أنظمة/توصيات ─────────────────────

def test_numbers_extraction_includes_classification_roman():
    assert numbers_en("immobilized for 6 weeks") == {"6"}
    assert numbers_en("Garden type II and type IV") == {"II", "IV"}
    assert numbers_en("12 percent") == {"12"}


def test_systems_extraction():
    assert "Garden" in systems_en("The Garden classification has four types")
    assert "Denis" in systems_en("Denis system divides the sacrum into three zones")
    assert not systems_en("Garden type I fractures")   # اسم بلا كلمة نظام → ليس نظاماً


def test_modality_detection():
    assert modality_en("Screw fixation should be avoided") == "neg"
    assert modality_en("Arthroplasty is preferred in the elderly") == "pos"
    assert modality_en("The fracture unites in six weeks") == "none"


def test_containment_prefers_shorter_side():
    a_text = "The femoral head receives its blood supply primarily from the medial femoral circumflex artery."
    b_text = "The blood supply of the femoral head comes primarily from the medial femoral circumflex artery."
    a, b = tokens_en(a_text), tokens_en(b_text)
    assert containment(a, b) >= 0.85
    assert lexical_similarity("Totally unrelated text about knee meniscus tears", a_text) < 0.2


def test_new_facts_finds_missing_numbers():
    facts = new_facts("protected for 12 weeks", "immobilized for 6 weeks")
    assert facts["numbers"] == ["12"]


# ───────────────────── 2) المصنف: القرار الثلاثي ────────────────────────────

def _classify(score, spine, other, **kw):
    decision, reason, facts = classify(
        score, score, None, spine, other,
        dup_threshold=kw.get("dup_threshold", 0.8),
        link_floor=kw.get("link_floor", 0.55),
    )
    return decision, reason, facts


def test_high_score_without_new_hard_facts_is_duplicate():
    spine = MILLER_UNITS[0]
    other = "The blood supply of the femoral head comes primarily from the medial femoral circumflex artery."
    decision, _, _ = _classify(0.889, spine, other)
    assert decision == "DUPLICATE"


def test_high_score_with_new_numbers_is_delta():
    decision, _, facts = _classify(
        0.9, "protected for 6 weeks after surgery", "protected for 6 weeks then 12 weeks brace")
    assert decision == "DELTA" and "12" in facts["numbers"]


def test_partial_link_is_delta():
    decision, reason, _ = _classify(
        0.6, MILLER_UNITS[1], "Garden type I impacted valgus fractures may allow early weight bearing.")
    assert decision == "DELTA"
    assert "ارتباط" in reason or "معلومات" in reason


def test_below_floor_is_standalone_delta():
    decision, reason, _ = _classify(
        0.2, MILLER_UNITS[0], "Early mobilization reduces the risk of pneumonia in the elderly.")
    assert decision == "DELTA"


def test_conflict_takes_precedence_over_duplicate():
    spine = "The limb was immobilized for 6 weeks after osteosynthesis."
    other = "The limb was protected for 12 weeks after osteosynthesis."
    decision, _, _ = _classify(0.95, spine, other)
    assert decision == "CONFLICT"   # حتى التطابق العالي لا يطمر تعارضاً رقمياً


# ───────────────────── 3) قواعد التعارض الثلاث ──────────────────────────────

def test_numbers_conflict():
    got = detect_conflicts(
        "The limb was immobilized for 6 weeks after osteosynthesis.",
        "The limb was protected for 12 weeks after osteosynthesis.")
    assert [c["conflict_type"] for c in got] == ["numbers"]


def test_classification_conflict():
    got = detect_conflicts(MILLER_UNITS[1], APLEY_UNITS[0])
    assert [c["conflict_type"] for c in got] == ["classification"]


def test_recommendation_conflict():
    got = detect_conflicts(MILLER_UNITS[2], APLEY_UNITS[1])
    assert [c["conflict_type"] for c in got] == ["recommendation"]


def test_same_system_is_not_classification_conflict():
    assert not detect_conflicts(MILLER_UNITS[1], MILLER_UNITS[1])


# ───────────────────── 4) الوحدات ومعرفات الإثبات ────────────────────────────

def _doc(blocks):
    from orthopaedic_knowledge.ingestion import ChapterDocument

    doc = ChapterDocument(book_code="MILLER", chapter="CH04", lang="en")
    doc.blocks.extend(blocks)
    return doc


def test_unit_ids_follow_provenance_schema():
    units, blocked = build_units(_doc([
        TextBlock(page=110, text="First paragraph.", kind="body"),
        TextBlock(page=110, text="Fig. 4: anatomy.", kind="caption"),
        TextBlock(page=111, text="Garden\tI\tII", kind="table_cell"),
    ]), "MILLER", "CH04")
    assert blocked == [] and len(units) == 3
    for u in units:
        assert re.fullmatch(r"MILLER_CH04_P\d{3}_U\d{3}", u.unit_id)
    assert units[0].unit_id == "MILLER_CH04_P110_U001"
    assert units[1].kind == "caption"


def test_invalid_blocks_are_blocked_not_guessed():
    units, blocked = build_units(
        _doc([TextBlock(page=0, text="كتلة تالفة", kind="body")]), "MILLER", "CH04")
    assert units == [] and len(blocked) == 1


# ───────────────────── 5) الدمج الثلاثي من طرف إلى طرف ──────────────────────

def test_official_synthesis_demo_end_to_end(tmp_path):
    summary = run_official_synthesis_demo(tmp_path)
    pipeline = summary["pipeline"]
    assert pipeline["spine_book"] == "MILLER"
    assert pipeline["units_per_book"] == {"MILLER": 5, "ROCKWOOD": 4, "APLEY": 3}
    # أربعة تكرارات منهارة، إضانتان مستقلتان، ثلاثة تعارضات
    assert pipeline["decisions"] == {"DUPLICATE": 2, "DELTA": 2, "CONFLICT": 3}
    types = sorted(c["type"] for c in pipeline["conflicts"])
    assert types == ["classification", "numbers", "recommendation"]
    # المخرجات الثلاثة موجودة وغير فارغة
    for key, name in (("markdown", "unified_chapter.md"),
                      ("report", "synthesis_report.html"),
                      ("summary", "synthesis_summary.json")):
        p = Path(summary["outputs"][key])
        assert p.exists() and p.stat().st_size > 0, name
    md = Path(summary["outputs"]["markdown"]).read_text(encoding="utf-8")
    assert "DELTA" in md and "تعارضات المراجع" in md and "موثّق أيضاً" in md
    html = Path(summary["outputs"]["report"]).read_text(encoding="utf-8")
    assert "dir='rtl'" in html and "BLOCKED" in html


def test_synthesis_db_round_trip(tmp_path):
    run_official_synthesis_demo(tmp_path)
    import sqlite3

    conn = sqlite3.connect(tmp_path / "synthesis.db")
    conn.row_factory = sqlite3.Row
    try:
        # جدول links يسجّل كل القرارات المرتبطة (بأسبابها ودرجاتها)
        decisions = {r["decision"]: r["n"] for r in conn.execute(
            "SELECT decision, COUNT(*) n FROM links GROUP BY decision")}
        assert decisions == {"DUPLICATE": 2, "DELTA": 2, "CONFLICT": 3}
        reasons = {r["reason"] for r in conn.execute("SELECT reason FROM links")}
        assert all(reasons)   # لا قرار بلا سبب موثق
        rows = conn.execute("SELECT conflict_type, status FROM conflicts").fetchall()
        assert {r["status"] for r in rows} == {"BLOCKED"}     # التعارضات لا تُحسم آلياً
        deltas = conn.execute(
            "SELECT COUNT(*) n FROM deltas WHERE anchor_unit IS NULL").fetchone()["n"]
        assert deltas == 2                                     # الإضانتان المستقلتان
    finally:
        conn.close()


def test_synthesis_rejects_non_english(tmp_path):
    from orthopaedic_knowledge.ingestion import ChapterDocument

    ar = ChapterDocument(book_code="ARBOOK", chapter="CH04", lang="ar")
    spine, _ = build_demo_documents()
    with pytest.raises(ValueError, match="الإنجليزية"):
        run_synthesis(spine, [("ARBOOK", ar)], tmp_path / "s.db")


def test_synthesis_rejects_repeated_codes(tmp_path):
    spine, others = build_demo_documents()
    with pytest.raises(ValueError, match="فريدة"):
        run_synthesis(spine, [others[0], others[0]], tmp_path / "s.db")


def test_synthesis_without_spine_body_fails_closed(tmp_path):
    from orthopaedic_knowledge.ingestion import ChapterDocument

    empty = ChapterDocument(book_code="EMPTY1", chapter="CH04", lang="en")
    spine, _ = build_demo_documents()
    with pytest.raises(ValueError, match="عمود فقري"):
        run_synthesis(("EMPTY1", empty), [("ROCKWOOD", spine[1])], tmp_path / "s.db")


def test_spine_unit_anchor_links_carry_scores(tmp_path):
    run_official_synthesis_demo(tmp_path)
    import sqlite3

    conn = sqlite3.connect(tmp_path / "synthesis.db")
    conn.row_factory = sqlite3.Row
    try:
        links = conn.execute(
            "SELECT score, semantic FROM links ORDER BY link_id").fetchall()
        assert all(0.0 <= r["score"] <= 1.0 for r in links)
        assert all(r["semantic"] is None for r in links)   # الوضع المعجمي الصرف
    finally:
        conn.close()


def test_cli_synthesize_jsonl_end_to_end(tmp_path):
    """انحدار: --format jsonl عبر الـ CLI كان يفشل بـ FileNotFoundError
    (المحمّل يستقبل مساراً لا نصاً) — المسار الكامل يجب أن يعمل من طرف إلى طرف."""
    from orthopaedic_knowledge.cli import main
    from pilot.synthesis_demo import MILLER_UNITS, ROCKWOOD_UNITS, _doc

    work = tmp_path / "work"
    work.mkdir()
    spine_doc = _doc("MILLER", MILLER_UNITS, 110)
    other_doc = _doc("ROCKWOOD", ROCKWOOD_UNITS, 210)
    for doc, name in ((spine_doc, "miller_ch04.jsonl"), (other_doc, "rockwood_ch04.jsonl")):
        from orthopaedic_knowledge.ingestion.pdf_extract import export_blocks_jsonl

        export_blocks_jsonl(doc, work / name)

    db = tmp_path / "synthesis.db"
    rc = main([
        "synthesize",
        "--spine", str(work / "miller_ch04.jsonl"),
        "--spine-code", "MILLER",
        "--other", str(work / "rockwood_ch04.jsonl"), "ROCKWOOD",
        "--chapter", "CH04",
        "--format", "jsonl",
        "--db", str(db),
    ])
    assert rc == 0
    conn = sqlite3.connect(db)
    try:
        spine, conflicts, deltas = conn.execute(
            "SELECT (SELECT COUNT(*) FROM units u JOIN sources s ON u.source_id=s.source_id"
            " WHERE s.role='spine'),"
            " (SELECT COUNT(*) FROM conflicts),"
            " (SELECT COUNT(*) FROM deltas)"
        ).fetchone()
    finally:
        conn.close()
    assert spine == len(MILLER_UNITS)
    assert conflicts + deltas > 0  # النصوص المُعايَرة تنتج قرارات فعلاً
