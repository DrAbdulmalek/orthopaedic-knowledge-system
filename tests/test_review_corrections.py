"""اختبارات دمج corrections.db في حلقة المراجعة (v0.3.1 — دمج أفكار DeepSeek).

المبادئ المُختبرة: كل قرار بشري (تعارض أو مصطلح) يسلك corrections.db
لا مسار كتابة آخر؛ هجرة قيد entity للقواعد القديمة تحفظ الصفوف؛
شاشة المصطلحات تُعطّل برسالة عند غياب knowledge.db (لا إنشاء صامت).
"""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from orthopaedic_knowledge.storage import CorrectionsStore, connect as knowledge_connect  # noqa: E402
from orthopaedic_knowledge.review.app import create_app  # noqa: E402
from pilot.run_synthesis_demo import run_official_synthesis_demo  # noqa: E402

_LEGACY_DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE corrections (
    correction_id INTEGER PRIMARY KEY,
    entity        TEXT NOT NULL CHECK (entity IN ('alignment','term','concept','segment')),
    match_rule    TEXT NOT NULL DEFAULT 'exact_id'
                  CHECK (match_rule IN ('exact_id','norm_term')),
    entity_key    TEXT NOT NULL,
    field         TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT NOT NULL,
    reviewer      TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE TABLE correction_applications (
    application_id INTEGER PRIMARY KEY,
    correction_id  INTEGER NOT NULL REFERENCES corrections(correction_id),
    target_entity  TEXT NOT NULL,
    target_key     TEXT NOT NULL,
    result         TEXT NOT NULL CHECK (result IN ('APPLIED','SKIPPED','BLOCKED')),
    detail         TEXT,
    applied_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_corr_lookup ON corrections(entity, match_rule, entity_key);
"""


def _make_knowledge_db(path: Path) -> Path:
    kconn = knowledge_connect(path)
    kconn.execute(
        "INSERT INTO concepts (concept_id, definition, specialty)"
        " VALUES ('C-000001', 'osteonecrosis of the femoral head', 'Hip Surgery')"
    )
    kconn.execute(
        """INSERT INTO terms (concept_id, lang, term_text, term_norm, role,
                              dialect_weight, source, status)
           VALUES ('C-000001', 'ar', 'النخر اللاوعائي', 'نخر لاعوعائي',
                   'preferred', 1.0, 'demo', 'UNPROVEN')"""
    )
    kconn.execute(
        """INSERT INTO terms (concept_id, lang, term_text, term_norm, role,
                              dialect_weight, source, status)
           VALUES ('C-000001', 'ar', 'سوء التروية', 'سوء تروية',
                   'preferred', 0.5, 'demo', 'UNPROVEN')"""
    )
    kconn.commit()
    kconn.close()
    return path


@pytest.fixture()
def demo(tmp_path):
    run_official_synthesis_demo(tmp_path)
    kdb = _make_knowledge_db(tmp_path / "knowledge.db")
    db = tmp_path / "synthesis.db"
    return db, kdb, tmp_path / "corrections.db", TestClient(create_app(db))


def test_legacy_corrections_db_migrates_and_keeps_rows(tmp_path):
    """قاعدة قديمة (بلا conflict/delta) تُهاجَر آلياً مع حفظ الصفوف وFK."""
    legacy = tmp_path / "legacy_corrections.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(_LEGACY_DDL)
    conn.execute(
        "INSERT INTO corrections (entity, match_rule, entity_key, field, new_value, reviewer)"
        " VALUES ('term', 'norm_term', 'avascular necrosis', 'ar_preferred', 'النخر اللاوعائي', 'DR_OLD')"
    )
    conn.execute(
        "INSERT INTO correction_applications (correction_id, target_entity, target_key,"
        " result, detail) VALUES (1, 'term', 'C-000001', 'APPLIED', 'قاعدة قديمة')"
    )
    conn.commit()
    conn.close()

    store = CorrectionsStore(legacy)  # المهاجرة هنا
    try:
        # الصفوف القديمة محفوظة، والقيد الجديد يقبل كيانات المراجعة
        assert store.record("conflict", "conflict:1", "resolution", "PROVEN:other",
                            match_rule="exact_id", reviewer="DR_A") > 0
        assert store.record("delta", "delta:2", "verification", "verified",
                            match_rule="exact_id", reviewer="DR_A") > 0
        rules = store.all_rules()
        assert rules[0]["entity_key"] == "avascular necrosis"     # القديمة أولاً
        assert {r["entity"] for r in rules[1:]} == {"conflict", "delta"}
        apps = store.applications()
        assert len(apps) == 1 and apps[0]["detail"] == "قاعدة قديمة"  # FK سليم
        # المهاجرة idempotent — إعادة الفتح لا تعيد البناء ولا تفقد شيئاً
        store.close()
        store = CorrectionsStore(legacy)
        assert len(store.all_rules()) == 3
    finally:
        store.close()


def test_conflict_resolve_writes_legal_record(demo):
    """الحسم يسلك corrections.db — لا مسار كتابة آخر."""
    db, kdb, cdb, client = demo
    r = client.post("/api/conflicts/1/resolve",
                    json={"status": "PROVEN", "choice": "other", "reviewer": "DR_A"})
    assert r.status_code == 200
    store = CorrectionsStore(cdb)
    try:
        rules = store.all_rules()
        assert len(rules) == 1
        rule = rules[0]
        assert rule["entity"] == "conflict" and rule["match_rule"] == "exact_id"
        assert rule["entity_key"] == "conflict:1" and rule["reviewer"] == "DR_A"
        assert '"choice": "other"' in rule["new_value"].replace(" ", " ") or \
               '"choice":"other"' in rule["new_value"]
    finally:
        store.close()


def test_terms_approve_and_reject(demo):
    db, kdb, cdb, client = demo
    # القائمة تعرض المصطلحين المعلّقين
    items = client.get("/api/terms").json()
    assert {t["term_norm"] for t in items} == {"نخر لاعوعائي", "سوء تروية"}
    approve = client.post("/api/terms/1/approve", json={"reviewer": "DR_A"}).json()
    assert approve["status"] == "PROVEN" and approve["reviewer"] == "DR_A"
    assert approve["reviewed_at"] is not None
    reject = client.post("/api/terms/2/reject", json={"reviewer": "DR_A"}).json()
    assert reject["status"] == "UNPROVEN" and reject["decision"] == "keep_unproven"
    # القاعدة المعرفية: المُعتمد PROVEN والمرفض بقي معلقاً
    kconn = knowledge_connect(kdb)
    statuses = {r["term_id"]: r["status"] for r in
                kconn.execute("SELECT term_id, status FROM terms")}
    kconn.close()
    assert statuses == {1: "PROVEN", 2: "UNPROVEN"}
    # وكلا القرارين في السجل القانوني
    store = CorrectionsStore(cdb)
    try:
        fields = {(r["entity"], r["field"]) for r in store.all_rules()}
        assert ("term", "status") in fields and ("term", "review_decision") in fields
    finally:
        store.close()


def test_terms_unknown_id_is_404(demo):
    _, _, _, client = demo
    assert client.post("/api/terms/999/approve", json={}).status_code == 404
    assert client.post("/api/terms/999/reject", json={}).status_code == 404


def test_audit_endpoint_lists_rules_and_applications(demo):
    _, _, _, client = demo
    client.post("/api/conflicts/1/resolve",
                json={"status": "PROVEN", "choice": "spine", "reviewer": "DR_B"})
    audit = client.get("/api/audit").json()
    assert len(audit["rules"]) == 1
    assert audit["rules"][0]["entity"] == "conflict"
    assert audit["applications"] == []


def test_missing_knowledge_db_disables_terms_screen(tmp_path):
    """غياب knowledge.db = شاشة معطلة برسالة، لا إنشاء صامت (Fail-Closed)."""
    run_official_synthesis_demo(tmp_path)
    db = tmp_path / "synthesis.db"
    client = TestClient(create_app(db))  # لا knowledge.db في المجلد
    assert client.get("/api/terms").status_code == 404
    assert client.get("/api/summary").json()["unproven_terms"] is None
    # القاعدة القانونية تعمل بجوار --db افتراضياً
    r = client.post("/api/conflicts/1/resolve",
                    json={"status": "PROVEN", "choice": "spine", "reviewer": "DR_A"})
    assert r.status_code == 200
    assert (tmp_path / "corrections.db").exists()


def test_cli_review_rejects_missing_knowledge_db(tmp_path, capsys):
    from orthopaedic_knowledge.cli import main

    run_official_synthesis_demo(tmp_path)
    assert main(["review", "--db", str(tmp_path / "synthesis.db"),
                 "--knowledge-db", str(tmp_path / "nope.db")]) == 1
    assert "غير موجودة" in capsys.readouterr().err
