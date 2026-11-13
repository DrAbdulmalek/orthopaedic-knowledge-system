"""اختبارات انحدار لإصلاحات مراجعة 2026-11 (v0.1.1).

كل اختبار هنا كان فشلاً حقيقياً قبل الإصلاح المقابل:
تصدير BLOCKED، حماية PROVEN، الصفحات المزيفة، عزل الجداول/التعليقات،
ربط ONNX بالفشل الصريح، اللواحق الضميرية، مُحمّل المسرد السوري.
"""

import json
import tempfile
from pathlib import Path

import pytest

from orthopaedic_knowledge.alignment import align, make_sim_fn
from orthopaedic_knowledge.alignment.embedder import build_embedder
from orthopaedic_knowledge.alignment.lexicon import BUILTIN_SEED, BilingualLexicon
from orthopaedic_knowledge.ingestion.layout_parser import blocks_from_text
from orthopaedic_knowledge.ingestion.models import TextBlock
from orthopaedic_knowledge.integration.tbx import build_tbx, load_concepts
from orthopaedic_knowledge.integration.tmx import export_tmx
from orthopaedic_knowledge.pipeline import run_pipeline
from orthopaedic_knowledge.storage import CorrectionsStore, connect
from orthopaedic_knowledge.terminology import extract_terms, load_syrian_lexicon_csv, syrian_weight
from orthopaedic_knowledge.terminology.syrian_preference import choose_preferred


# ─────────────────────────── 1) تصدير BLOCKED ممنوع ───────────────────────────

def _seed_pair(tmp_path: Path, status: str) -> Path:
    conn = connect(tmp_path / "k.db")
    try:
        conn.execute("INSERT INTO books (book_code) VALUES ('ORTHO101')")
        conn.execute("INSERT INTO documents (book_id, lang, chapter) VALUES (1,'en','CH04')")
        conn.execute("INSERT INTO documents (book_id, lang, chapter) VALUES (1,'ar','CH04')")
        conn.execute(
            """INSERT INTO segments (sentence_id, lang, doc_id, text, text_norm, page)
               VALUES ('ORTHO101_CH04_P110_S001','en',1,'A sentence.','a sentence',110)"""
        )
        conn.execute(
            """INSERT INTO segments (sentence_id, lang, doc_id, text, text_norm, page)
               VALUES ('ORTHO101_CH04_P110_S001','ar',2,'جملة.','جمله',110)"""
        )
        conn.execute(
            """INSERT INTO alignments (src_refs, tgt_refs, book_code, align_type, confidence,
                                       confidence_breakdown, status)
               VALUES ('["ORTHO101_CH04_P110_S001"]','["ORTHO101_CH04_P110_S001"]','ORTHO101',
                       '1:1', 0.9, '{}', ?)""",
            (status,),
        )
        conn.commit()
    finally:
        conn.close()
    return tmp_path / "k.db"


def test_tmx_never_exports_blocked(tmp_path):
    db = _seed_pair(tmp_path, "BLOCKED")
    from orthopaedic_knowledge.storage import connect as _connect

    conn = _connect(db)
    try:
        path = export_tmx(conn, tmp_path / "m.tmx")
        assert "<tu " not in path.read_text(encoding="utf-8")
    finally:
        conn.close()


def test_tmx_still_exports_unproven(tmp_path):
    db = _seed_pair(tmp_path, "UNPROVEN")
    from orthopaedic_knowledge.storage import connect as _connect

    conn = _connect(db)
    try:
        path = export_tmx(conn, tmp_path / "m.tmx")
        assert "<tu " in path.read_text(encoding="utf-8")   # الفلترة تستهدف BLOCKED فقط
    finally:
        conn.close()


def test_tbx_excludes_blocked_concepts():
    conn = connect(":memory:")
    try:
        conn.execute("INSERT INTO concepts (concept_id, status) VALUES ('C-000001','BLOCKED')")
        conn.execute("INSERT INTO concepts (concept_id, status) VALUES ('C-000002','UNPROVEN')")
        conn.commit()
        entries = {c["concept_id"] for c in load_concepts(conn)}
        assert "C-000001" not in entries and "C-000002" in entries
        assert "C-000001" not in build_tbx(load_concepts(conn))
    finally:
        conn.close()


# ─────────────────────────── 2) حماية PROVEN في التصحيحات ───────────────────────

def test_correction_never_demotes_proven_term(tmp_path):
    store = CorrectionsStore(tmp_path / "c.db")
    conn = connect(tmp_path / "k.db")
    try:
        conn.execute("INSERT INTO concepts (concept_id) VALUES ('C-000001')")
        conn.execute(
            """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, status)
               VALUES ('C-000001','en','Cast','cast','preferred','UNPROVEN')"""
        )
        conn.execute(
            """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, status)
               VALUES ('C-000001','ar','الجبس','الجبس','preferred','PROVEN')"""
        )
        conn.commit()
        store.record("term", "cast", "ar_preferred", "الجبيرة الجبسية", reviewer="DR_A")
        assert store.apply_ar_preferred(conn, "cast") == 1
        rows = {r["term_text"]: (r["role"], r["status"]) for r in conn.execute(
            "SELECT term_text, role, status FROM terms WHERE lang='ar'")}
        assert rows["الجبس"] == ("preferred", "PROVEN")          # لم يُنزَّل — الحماية إلزامية
        assert rows["الجبيرة الجبسية"][0] == "preferred"
    finally:
        conn.close()
        store.close()


# ─────────────────────────── 3) الصفحات المزيفة وعزل التيارات ───────────────────

def test_blocks_from_text_never_invents_pages():
    text = "الفقرة الأولى.\n\nالفقرة الثانية.\n\nالفقرة الثالثة."
    doc = blocks_from_text(text, "ORTHO101", "CH04", "ar")
    assert len(doc.blocks) == 3
    assert {b.page for b in doc.blocks} == {1}   # لا P001..P003 مختلقة


def test_blocks_from_text_marks_table_cells():
    doc = blocks_from_text("نص متن عادي.\nGarden\tI\tII\tIII\n", "ORTHO101", "CH04", "ar")
    kinds = [b.kind for b in doc.blocks]
    assert "table_cell" in kinds


def test_pipeline_excludes_nonbody_from_alignment():
    """التعليقات تُخزَّن segments كاملة لكنها لا تُحاذى مع المتن."""
    from pilot.femoral_neck_chapter import build_mock_documents

    src, tgt = build_mock_documents()
    tgt.blocks.append(TextBlock(page=113, text="شكل 4: تشريح الدورة الدموية للفخذ.", kind="caption"))
    with tempfile.TemporaryDirectory() as td:
        summary = run_pipeline(src, tgt, Path(td) / "k.db", Path(td) / "c.db")
        assert summary["non_body_excluded"] >= 1
        conn = connect(Path(td) / "k.db")
        try:
            assert conn.execute(
                "SELECT COUNT(*) c FROM segments WHERE kind='caption'").fetchone()["c"] >= 1
            refs: list[str] = []
            for row in conn.execute("SELECT src_refs, tgt_refs FROM alignments"):
                refs += json.loads(row["src_refs"]) + json.loads(row["tgt_refs"])
            caption_ids = [r["sentence_id"] for r in conn.execute(
                "SELECT sentence_id FROM segments WHERE kind='caption'")]
            assert all(sid not in refs for sid in caption_ids)
        finally:
            conn.close()


# ─────────────────────────── 4) ONNX: فشل صريح لا صمت ───────────────────────────

def test_build_embedder_fails_loud_on_explicit_broken_dir():
    with pytest.raises(RuntimeError):
        build_embedder("/nonexistent/model/dir")   # مجلد محدد صراحةً ومعطوب


def test_build_embedder_none_means_lexical_mode():
    assert build_embedder(None) is None            # غياب النموذج قرار تصميمي، ليس فشلاً


# ─────────────────────────── 5) extract_terms — الدقة واللغة ─────────────────────

def test_extract_terms_handles_trailing_punctuation():
    """«avascular necrosis,» بفاصلة لاحقة — المرشح يوجد ويرتبط بمرشح عربي."""
    pair = {
        "alignment_id": 1, "align_type": "1:1", "confidence": 0.8, "status": "UNPROVEN",
        "src": [{"sentence_id": "X", "text": "The risk of avascular necrosis, and nonunion, is real."}],
        "tgt": [{"sentence_id": "Y", "text": "خطر النخر اللاوعائي وعدم التحام حقيقي."}],
    }
    cands = {c.en_term: c for c in extract_terms([pair])}
    assert "avascular necrosis" in cands
    assert cands["avascular necrosis"].ar_variants


def test_ar_variants_match_pronominal_suffixes():
    lex = BilingualLexicon()
    # supply → ترويه؛ النص «ترويته» باللاحقة الضميرية — يجب أن يطابق
    assert lex.overlap("receives its supply", "ترويته الدموية") >= 0.4


def test_seed_language_fixes():
    assert "قرصات" not in BUILTIN_SEED.values()
    assert "انصتاب" not in BUILTIN_SEED.values()
    assert BUILTIN_SEED["nonunion"] == "عدم التحام|التحام"
    assert BUILTIN_SEED["ulcers"] == "قرحات|قرحه"
    assert BUILTIN_SEED["thrombosis"] == "خثار"
    assert syrian_weight("الجبيرة") == 1.0            # جبيره في المحمي (لا غبره)


# ─────────────────────────── 6) مُحمّل المسرد السوري ─────────────────────────────

def test_load_syrian_lexicon_csv(tmp_path):
    csv_path = tmp_path / "syrian.csv"
    csv_path.write_text("# تعليق\nطبيب\nالترقيع\n", encoding="utf-8")
    lex = load_syrian_lexicon_csv(str(csv_path))
    assert "طبيب" in lex and "الترقيع" in lex
    decision = choose_preferred({"الترقيع": 2, "الترميم": 2}, extra_lexicon=lex)
    assert decision.preferred == "الترقيع"            # مسرد المستخدم حسم التعادل


# ─────────────────────────── 7) memoization — النتائج محفوظة ─────────────────────

def test_aligner_memoization_preserves_gold_result():
    from pilot.femoral_neck_chapter import AR_SENTENCES, EN_SENTENCES

    sim = make_sim_fn()
    result = align([t for _, t in EN_SENTENCES], [t for _, t in AR_SENTENCES], sim)
    types = [a.align_type for a in result.alignments]
    assert types.count("1:1") == 11 and types.count("1:2") == 1
