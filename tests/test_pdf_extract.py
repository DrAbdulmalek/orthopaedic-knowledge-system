"""اختبارات استخراج PDF — القص بنطاق صفحات (--pages) وقواعد الفشل الواعي."""

from __future__ import annotations

import pytest

from orthopaedic_knowledge.ingestion.pdf_extract import (
    extract_pdf_blocks,
    parse_pages,
)


@pytest.fixture()
def sample_pdf(tmp_path):
    """PDF نصي من 5 صفحات — كل صفحة تحمل نصها الفريد."""
    fitz = pytest.importorskip("fitz")  # وحدة [pdf] اختيارية محلياً
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page()
        page.insert_text((72, 100), f"Page {i + 1} femoral neck fracture text.")
    doc.save(path)
    doc.close()
    return path


def test_parse_pages_ranges_and_errors():
    assert parse_pages(None) is None
    assert parse_pages("") is None
    assert parse_pages("3") == frozenset({3})
    assert parse_pages("2-4") == frozenset({2, 3, 4})
    assert parse_pages("1,3,5-6") == frozenset({1, 3, 5, 6})
    assert parse_pages("1، 3") == frozenset({1, 3})  # فاصلة عربية مقبولة
    with pytest.raises(ValueError, match="غير منطقي"):
        parse_pages("0-2")            # العدّاد يبدأ من 1
    with pytest.raises(ValueError, match="غير منطقي"):
        parse_pages("5-3")            # نهاية قبل البداية
    with pytest.raises(ValueError, match="تالف"):
        parse_pages("a-b")


def test_extract_full_then_sliced(sample_pdf):
    full = extract_pdf_blocks(sample_pdf, "MILLER", "CH04", "en")
    assert {b.page for b in full.blocks} == {1, 2, 3, 4, 5}

    sliced = extract_pdf_blocks(sample_pdf, "MILLER", "CH04", "en", pages="2-3")
    assert {b.page for b in sliced.blocks} == {2, 3}          # القص يعمل
    assert any("Page 2" in b.text for b in sliced.blocks)
    assert not any("Page 4" in b.text for b in sliced.blocks)
    # أرقام الإثبات تبقى أرقام الملف الأصلي — لا إعادة ترقيم
    assert {b.page for b in sliced.blocks} == {2, 3}


def test_extract_pages_out_of_range_yields_empty(sample_pdf):
    # نطاق خارج الملف لا يخطئ صامتاً بنص غريب — ينتج صفر كتلة (رفض آمن في التقطيع)
    doc = extract_pdf_blocks(sample_pdf, "MILLER", "CH04", "en", pages="99-100")
    assert doc.blocks == []
