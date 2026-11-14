"""اختبارات واجهة المراجعة البشرية (المرحلة 3) — orthok review.

التدفق كامل: دمج ثلاثي → واجهة → حسم بشري لتعارض → القاعدة تتحدث
→ إعادة توليد الفصل الموحد تعتمد النص المحسوم بشارة PROVEN.
"""

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from orthopaedic_knowledge.review.app import create_app  # noqa: E402
from pilot.run_synthesis_demo import run_official_synthesis_demo  # noqa: E402


@pytest.fixture()
def demo(tmp_path):
    run_official_synthesis_demo(tmp_path)
    db = tmp_path / "synthesis.db"
    return db, TestClient(create_app(db))


def test_missing_db_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(tmp_path / "nope.db")


def test_home_page_is_rtl_self_contained(demo):
    _, client = demo
    html = client.get("/").text
    assert "dir='rtl'" in html and "<script>" in html
    assert "حسم" in html


def test_summary_counts(demo):
    _, client = demo
    s = client.get("/api/summary").json()
    assert s["conflicts"] == {"BLOCKED": 3, "UNPROVEN": 0, "PROVEN": 0}
    assert s["deltas"] == 2
    assert s["spine_book"] == "MILLER" and s["chapter"] == "CH04"


def test_conflicts_listed_with_provenance_and_score(demo):
    _, client = demo
    items = client.get("/api/conflicts").json()
    assert len(items) == 3
    for key in ("conflict_id", "conflict_type", "spine_text", "other_text",
                "spine_unit_id", "other_unit_id", "book_code", "status", "score"):
        assert key in items[0]
    blocked = client.get("/api/conflicts", params={"status": "BLOCKED"}).json()
    assert len(blocked) == 3


def test_resolve_with_other_text_updates_db_and_export(demo):
    db, client = demo
    items = client.get("/api/conflicts", params={"status": "BLOCKED"}).json()
    numbers = next(c for c in items if c["conflict_type"] == "numbers")
    r = client.post(f"/api/conflicts/{numbers['conflict_id']}/resolve",
                    json={"status": "PROVEN", "choice": "other", "reviewer": "DR_A"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PROVEN" and body["choice"] == "other"
    assert body["reviewer"] == "DR_A"
    assert body["text"] == "The limb was protected for 12 weeks after osteosynthesis."
    assert body["resolved_at"]
    # القاعدة: الحالة PROVEN والقرار JSON موثق بالزمن
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT status, resolution FROM conflicts WHERE conflict_id=?",
                           (numbers["conflict_id"],)).fetchone()
        assert row["status"] == "PROVEN"
        payload = json.loads(row["resolution"])
        assert payload["choice"] == "other" and payload["reviewer"] == "DR_A"
        assert payload["resolved_at"]
    finally:
        conn.close()
    # المعلّقة صارت اثنتين، والفصل الموحد يستبدل النص بشارة الاعتماد
    assert len(client.get("/api/conflicts", params={"status": "BLOCKED"}).json()) == 2
    md = client.get("/api/export/unified.md").text
    assert "نص معتمد بشرياً [PROVEN]" in md and "DR_A" in md
    assert "The limb was protected for 12 weeks after osteosynthesis." in md
    # استبدال في الجسم: نص العمود الفقري لم يعد نص الوحدة، لكنه يبقى سطر تدقيق واحد في الجدول
    assert md.count("immobilized for 6 weeks") == 1
    assert "The limb was protected for 12 weeks after osteosynthesis. (في MILLER ذُكر الرقم 6)" in md


def test_spine_choice_keeps_spine_text(demo):
    _, client = demo
    items = client.get("/api/conflicts", params={"status": "BLOCKED"}).json()
    numbers = next(c for c in items if c["conflict_type"] == "numbers")
    r = client.post(f"/api/conflicts/{numbers['conflict_id']}/resolve",
                    json={"choice": "spine", "reviewer": "DR_B"})
    assert r.status_code == 200
    md = client.get("/api/export/unified.md").text
    assert "immobilized for 6 weeks" in md              # العمود الفقري بقي
    assert "نص معتمد بشرياً [PROVEN]" not in md          # اختيار spine = بلا استبدال


def test_custom_choice_requires_text(demo):
    _, client = demo
    cid = client.get("/api/conflicts").json()[0]["conflict_id"]
    assert client.post(f"/api/conflicts/{cid}/resolve",
                       json={"choice": "custom", "text": "   "}).status_code == 400
    assert client.post(f"/api/conflicts/{cid}/resolve",
                       json={"choice": "custom"}).status_code == 400
    assert client.post(f"/api/conflicts/{cid}/resolve",
                       json={"choice": "nonsense"}).status_code == 400
    bad_status = client.post(f"/api/conflicts/{cid}/resolve",
                             json={"choice": "spine", "status": "WEIRD"})
    assert bad_status.status_code == 400


def test_unknown_conflict_is_404(demo):
    _, client = demo
    assert client.post("/api/conflicts/999/resolve",
                       json={"choice": "spine"}).status_code == 404


def test_invalid_status_filter_is_400(demo):
    _, client = demo
    assert client.get("/api/conflicts", params={"status": "WEIRD"}).status_code == 400


def test_cli_review_export(tmp_path, capsys, monkeypatch):
    from orthopaedic_knowledge.cli import main

    run_official_synthesis_demo(tmp_path)
    out = tmp_path / "unified.md"
    assert main(["review-export", "--db", str(tmp_path / "synthesis.db"),
                 "--out", str(out)]) == 0
    assert out.exists() and "الفصل الامتحاني الموحد" in out.read_text(encoding="utf-8")
    # قاعدة مفقودة → رمز خروج 1 (Fail-Closed)
    assert main(["review-export", "--db", str(tmp_path / "nope.db"),
                 "--out", str(tmp_path / "x.md")]) == 1
