"""خط الإنتاج التجريبي الكامل — فصل «كسور عنق الفخذ» ببيانات وهمية.

يربط كل مراحل المنظومة في مسار واحد قابل للتكرار محلياً:

1. بيانات وهمية (كتل واعية للتخطيط + كتلة تالفة لإثبات الفشل الآمن).
2. تقطيع جمل بمعرفات Provenance: ORTHO101_CH04_P110_S001 …
3. محاذاة 1:1 / 1:2 / UNALIGNED مع درجة ثقة **مفككة**.
4. حفظ في SQLite (knowledge.db) بتصنيف إلزامي UNPROVEN.
5. مصطلحات + ترجيح سوري (جبس ← مفضل، جبيرة جبسية ← Contextual Synonym).
6. عرض توضيحي لحلقة التصحيح: قرار مراجع → corrections.db → إعادة تطبيق آلي.
7. تصدير النتيجة إلى TMX وXLSX (أوراق: Alignments / Terms / Blocked).
8. تقرير QA بواجهة عربية.

الاستخدام:  orthok pilot --out out/pilot      (أو python -m pilot.run_pilot)
"""

from __future__ import annotations

import json
from pathlib import Path

from orthopaedic_knowledge import __version__
from orthopaedic_knowledge.integration import export_tmx, export_xlsx
from orthopaedic_knowledge.pipeline import run_pipeline
from orthopaedic_knowledge.qa import export_report
from orthopaedic_knowledge.storage import CorrectionsStore, connect

from .femoral_neck_chapter import build_mock_documents

# قرار مراجع بشري حقيقي الشكل: الترجمة المفضلة لمفهوم AVN
# (تُسجل قاعدة دائمة في corrections.db وتُطبَّق آلياً في كل تشغيل لاحق)
DEMO_CORRECTION = {
    "entity": "term",
    "entity_key": "avascular necrosis",
    "field": "ar_preferred",
    "new_value": "النخر العظمي اللاوعائي",
    "reviewer": "DR_DEMO",
}


def run_official_pilot(out_dir: str | Path = Path("out/pilot")) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    knowledge_db = out / "knowledge.db"
    corrections_db = out / "corrections.db"
    for stale in (knowledge_db, corrections_db):  # الـ pilot عرض نظيف كل مرة
        if stale.exists():
            stale.unlink()

    src_doc, tgt_doc = build_mock_documents()
    summary: dict = {"version": __version__}

    # 2–5: الخط الكامل (تقطيع → محاذاة → حفظ → مصطلحات + ترجيح سوري)
    summary["pipeline"] = run_pipeline(src_doc, tgt_doc, knowledge_db, corrections_db)

    # 6: حلقة التصحيح المستمرة — إثبات Auto-apply
    summary["corrections_demo"] = _demonstrate_corrections(knowledge_db, corrections_db)

    # 7: التصدير النهائي — TMX + XLSX (+ CSV اختياري للجداول الخام)
    conn = connect(knowledge_db)
    try:
        tmx_path = export_tmx(conn, out / "memory.tmx", min_confidence=0.3)
        xlsx_path = export_xlsx(conn, out / "alignments.xlsx")
        report_path = export_report(conn, out / "qa_report.html")
    finally:
        conn.close()
    summary["outputs"] = {
        "tmx": str(tmx_path),
        "xlsx": str(xlsx_path),
        "qa_report": str(report_path),
        "knowledge_db": str(knowledge_db),
        "corrections_db": str(corrections_db),
    }
    return summary


def _demonstrate_corrections(knowledge_db: Path, corrections_db: Path) -> dict:
    """قرار مراجع → قاعدة دائمة → تطبيق آلي فوري → إثبات بالسجلات."""
    store = CorrectionsStore(corrections_db)
    conn = connect(knowledge_db)
    try:
        before = conn.execute(
            """SELECT t.term_text FROM terms t JOIN terms e
                 ON e.concept_id=t.concept_id AND e.lang='en'
               WHERE e.term_norm=? AND t.lang='ar' AND t.role='preferred'""",
            (DEMO_CORRECTION["entity_key"],),
        ).fetchone()
        before_txt = before["term_text"] if before else None

        cid = store.record(
            DEMO_CORRECTION["entity"], DEMO_CORRECTION["entity_key"],
            DEMO_CORRECTION["field"], DEMO_CORRECTION["new_value"],
            old_value=before_txt, reviewer=DEMO_CORRECTION["reviewer"],
        )
        applied = store.apply_ar_preferred(conn, DEMO_CORRECTION["entity_key"])

        after = conn.execute(
            """SELECT t.term_text FROM terms t JOIN terms e
                 ON e.concept_id=t.concept_id AND e.lang='en'
               WHERE e.term_norm=? AND t.lang='ar' AND t.role='preferred'""",
            (DEMO_CORRECTION["entity_key"],),
        ).fetchone()
        return {
            "correction_id": cid,
            "rule": f"{DEMO_CORRECTION['entity_key']} → {DEMO_CORRECTION['new_value']}",
            "before_auto_apply": before_txt,
            "after_auto_apply": after["term_text"] if after else None,
            "applied": bool(applied),
            "applications_log": store.applications(),
        }
    finally:
        conn.close()
        store.close()


if __name__ == "__main__":
    print(json.dumps(run_official_pilot(), ensure_ascii=False, indent=2))
