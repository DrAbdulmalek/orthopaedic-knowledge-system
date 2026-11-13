"""اختبار نهاية-إلى-نهاية للـ pilot الرسمي: كل المخرجات تُفحص فعلياً."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from openpyxl import load_workbook

from pilot.run_pilot import run_official_pilot


def test_full_pilot_end_to_end(tmp_path):
    summary = run_official_pilot(tmp_path / "pilot")
    s = json.dumps(summary, ensure_ascii=False)
    assert summary["pipeline"]["src_sentences"] == 12
    assert summary["pipeline"]["tgt_sentences"] == 13
    assert summary["pipeline"]["blocked_blocks"] == 1          # الكتلة التالفة رُفضت
    assert "1:2" in summary["pipeline"]["type_counts"]          # الانقسام مُلتقط
    assert summary["pipeline"]["flags"] >= 1
    assert summary["pipeline"]["concepts"] >= 5

    # حلقة التصحيح: قبل/بعد موثقة
    demo = summary["corrections_demo"]
    assert demo["applied"] is True
    assert demo["after_auto_apply"] == "النخر العظمي اللاوعائي"
    assert demo["applications_log"][-1]["result"] == "APPLIED"

    # المخرجات موجودة وصالحة فعلياً
    tmx = Path(summary["outputs"]["tmx"])
    xlsx = Path(summary["outputs"]["xlsx"])
    report = Path(summary["outputs"]["qa_report"])
    assert tmx.exists() and tmx.stat().st_size > 0
    assert xlsx.exists() and xlsx.stat().st_size > 0
    assert report.exists() and report.stat().st_size > 0

    root = ET.parse(tmx).getroot()
    tus = root.findall("body/tu")
    assert 8 <= len(tus) <= 12                                 # UNALIGNED مستبعد + فلتر ثقة
    assert any(p.text == "UNPROVEN" for tu in tus for p in tu.findall("prop"))

    wb = load_workbook(xlsx)
    assert wb.sheetnames == ["Alignments", "Terms", "Blocked"]
    blocked_rows = list(wb["Blocked"].iter_rows(values_only=True))
    assert len(blocked_rows) >= 2                              # الكتلة التالفة مسجلة في الورقة

    # قاعدة التصحيح دائمة ومكتوبة في corrections.db
    rules_file = Path(summary["outputs"]["corrections_db"])
    assert rules_file.exists() and rules_file.stat().st_size > 0
