"""اختبارات الفشل الآمن: تلف البيانات → BLOCKED مسجل، لا تخمين ولا صمت."""

import tempfile
from pathlib import Path

from orthopaedic_knowledge.fail_closed import BlockedItemError, block_item, fail_closed
from orthopaedic_knowledge.pipeline import run_pipeline
from orthopaedic_knowledge.storage import connect


def test_fail_closed_marks_and_raises():
    conn = connect(":memory:")
    try:
        raised = False
        try:
            with fail_closed(conn, "segment", "X", "unit-test"):
                raise ValueError("بيانات تالفة")
        except BlockedItemError as exc:
            raised = True
            assert "unit-test" in str(exc) and "X" in str(exc)
        assert raised
        rows = list(conn.execute("SELECT * FROM qa_blocks"))
        assert len(rows) == 1
        assert rows[0]["reason"] == "بيانات تالفة"
        assert rows[0]["entity_key"] == "X"
    finally:
        conn.close()


def test_blocked_item_error_not_double_recorded():
    """BlockedItemError يعني «مسجل مسبقاً» — لا يُسجل ثانيةً (لا ازدواج)."""
    conn = connect(":memory:")
    try:
        block_item(conn, "block", "K", "stage", "سجل مسبقاً")
        try:
            with fail_closed(conn, "block", "K", "stage"):
                raise BlockedItemError("مسجل مسبقاً")
        except BlockedItemError:
            pass
        n = conn.execute("SELECT COUNT(*) c FROM qa_blocks").fetchone()["c"]
        assert n == 1
    finally:
        conn.close()


def test_invalid_block_blocked_but_pipeline_survives():
    """الكتلة التالفة (صفحة 0) من بيانات الـ pilot تُرفض والخط يكمل سليماً."""
    from pilot.femoral_neck_chapter import build_mock_documents

    src, tgt = build_mock_docs()
    with tempfile.TemporaryDirectory() as td:
        summary = run_pipeline(
            src, tgt,
            Path(td) / "knowledge.db",
            Path(td) / "corrections.db",
        )
        assert summary["blocked_blocks"] >= 1
        conn = connect(Path(td) / "knowledge.db")
        try:
            blocks = list(conn.execute("SELECT * FROM qa_blocks WHERE stage='ingestion'"))
            assert len(blocks) >= 1
            assert "page غير صالح" in blocks[0]["reason"]
            assert conn.execute("SELECT COUNT(*) c FROM segments WHERE lang='ar'").fetchone()["c"] >= 13
        finally:
            conn.close()


def build_mock_docs():
    from pilot.femoral_neck_chapter import build_mock_documents

    return build_mock_documents()


def test_block_item_explicit_api():
    conn = connect(":memory:")
    try:
        block_item(conn, "term", "AVN", "qa", "تعارض مصطلحات", {"k": 1})
        row = conn.execute("SELECT detail_json FROM qa_blocks LIMIT 1").fetchone()
        assert '"k": 1' in row["detail_json"]
    finally:
        conn.close()
