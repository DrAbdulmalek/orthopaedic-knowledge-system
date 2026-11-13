"""اختبارات التصدير: TMX صالح البنية، TBX، وXLSX بأوراقها الثلاث."""

import xml.etree.ElementTree as ET

from openpyxl import load_workbook

from orthopaedic_knowledge.integration import export_csv, export_tbx, export_tmx, export_xliff, export_xlsx
from orthopaedic_knowledge.storage import connect


def _seed_db(tmp_path):
    conn = connect(tmp_path / "k.db")
    conn.execute("INSERT INTO books (book_code) VALUES ('ORTHO101')")
    conn.execute("INSERT INTO documents (book_id, lang, chapter) VALUES (1,'en','CH04')")
    conn.execute("INSERT INTO documents (book_id, lang, chapter) VALUES (1,'ar','CH04')")
    conn.execute(
        """INSERT INTO segments (sentence_id, lang, doc_id, text, text_norm, page)
           VALUES ('ORTHO101_CH04_P110_S001','en',1,'The femoral head…','femoral head',110)"""
    )
    conn.execute(
        """INSERT INTO segments (sentence_id, lang, doc_id, text, text_norm, page)
           VALUES ('ORTHO101_CH04_P110_S001','ar',2,'رأس عظم الفخذ…','راس عظم الفخذ',110)"""
    )
    conn.execute(
        """INSERT INTO alignments (src_refs, tgt_refs, book_code, align_type, confidence,
                                   confidence_breakdown, status)
           VALUES ('["ORTHO101_CH04_P110_S001"]','["ORTHO101_CH04_P110_S001"]','ORTHO101','1:1',
                   0.87,'{}','UNPROVEN')"""
    )
    conn.execute("INSERT INTO concepts (concept_id, specialty) VALUES ('C-000001','Hip')")
    conn.execute(
        """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, dialect_weight, status)
           VALUES ('C-000001','ar','الجبس','جبس','preferred',1.0,'UNPROVEN')"""
    )
    conn.commit()
    return conn


def test_tmx_wellformed_with_props(tmp_path):
    conn = _seed_db(tmp_path)
    path = export_tmx(conn, tmp_path / "m.tmx", min_confidence=0.3)
    root = ET.parse(path).getroot()
    assert root.tag == "tmx" and root.attrib["version"] == "1.4"
    tu = root.find("body/tu")
    props = {p.attrib["type"]: p.text for p in tu.findall("prop")}
    assert props["x-alignment-id"] == "A-1"
    assert props["x-status"] == "UNPROVEN"
    assert props["x-provenance"] == "ORTHO101/CH04/p110"
    conn.close()


def test_tmx_min_confidence_filters(tmp_path):
    conn = _seed_db(tmp_path)
    path = export_tmx(conn, tmp_path / "m.tmx", min_confidence=0.9)
    content = path.read_text(encoding="utf-8")
    assert "<tu " not in content  # 0.87 < 0.9 → مستبعد
    conn.close()


def test_tbx_structure(tmp_path):
    conn = _seed_db(tmp_path)
    path = export_tbx(conn, tmp_path / "t.tbx")
    ns = {"t": "urn:iso:std:iso:30042:ed-2"}
    root = ET.parse(path).getroot()
    entry = root.find("t:text/t:body/t:conceptEntry", ns)
    assert entry.attrib["id"] == "C-000001"
    assert {s.attrib["{http://www.w3.org/XML/1998/namespace}lang"]
            for s in entry.findall("t:langSec", ns)} == {"ar"}
    conn.close()


def test_xlsx_three_sheets(tmp_path):
    conn = _seed_db(tmp_path)
    path = export_xlsx(conn, tmp_path / "a.xlsx")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Alignments", "Terms", "Blocked"]
    rows = list(wb["Alignments"].iter_rows(values_only=True))
    assert rows[0][0] == "alignment_id"
    assert any("femoral" in str(r[5]) for r in rows[1:])
    conn.close()


def test_csv_utf8_bom_for_arabic(tmp_path):
    conn = _seed_db(tmp_path)
    paths = export_csv(conn, tmp_path / "csv")
    assert all(p.exists() for p in paths)
    raw = paths[0].read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM — Excel يقرأ العربية صحيحة
    conn.close()


def test_xliff_units_state(tmp_path):
    conn = _seed_db(tmp_path)
    path = export_xliff(conn, tmp_path / "r.xliff")
    root = ET.parse(path).getroot()
    assert root.attrib["version"] == "2.0"
    unit = root.find("{urn:oasis:names:tc:xliff:document:2.0}file/"
                     "{urn:oasis:names:tc:xliff:document:2.0}unit")
    assert unit.attrib["id"] == "A-1"
    conn.close()
