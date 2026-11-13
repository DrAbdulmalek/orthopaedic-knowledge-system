"""اختبارات corrections.db: قاعدة دائمة + تطبيق آلي موثق (Auto-apply)."""

from orthopaedic_knowledge.storage import CorrectionsStore, connect


def test_record_and_lookup(tmp_path):
    store = CorrectionsStore(tmp_path / "c.db")
    try:
        cid = store.record("term", "avascular necrosis", "ar_preferred", "النخر العظمي اللاوعائي",
                           reviewer="DR_A")
        assert cid == 1
        rule = store.lookup("term", "avascular necrosis", "ar_preferred")
        assert rule is not None and rule["new_value"] == "النخر العظمي اللاوعائي"
        assert store.lookup("term", "unknown", "ar_preferred") is None
    finally:
        store.close()


def test_auto_apply_promotes_and_demotes(tmp_path):
    store = CorrectionsStore(tmp_path / "c.db")
    conn = connect(tmp_path / "k.db")
    try:
        # مفهوم يُنشأ آلياً باقتراح محرك
        conn.execute("INSERT INTO concepts (concept_id, specialty) VALUES ('C-000001','Ortho')")
        conn.execute(
            """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, status)
               VALUES ('C-000001','en','Avascular Necrosis','avascular necrosis','preferred','UNPROVEN')"""
        )
        conn.execute(
            """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, status)
               VALUES ('C-000001','ar','النخر اللاوعائي','النخر اللاوعائي','preferred','UNPROVEN')"""
        )
        conn.commit()

        store.record("term", "avascular necrosis", "ar_preferred", "النخر العظمي اللاوعائي",
                     reviewer="DR_A")
        applied = store.apply_ar_preferred(conn, "avascular necrosis")
        assert applied == 1

        roles = {r["term_text"]: r["role"] for r in conn.execute(
            "SELECT term_text, role FROM terms WHERE lang='ar'")}
        assert roles["النخر العظمي اللاوعائي"] == "preferred"
        assert roles["النخر اللاوعائي"] == "synonym"          # نُزل لمرادف سياقي

        log = store.applications()
        assert log and log[-1]["result"] == "APPLIED"
    finally:
        conn.close()
        store.close()


def test_auto_apply_without_concept_is_skipped(tmp_path):
    store = CorrectionsStore(tmp_path / "c.db")
    conn = connect(tmp_path / "k.db")
    try:
        store.record("term", "ghost term", "ar_preferred", "لا وجود")
        applied = store.apply_ar_preferred(conn, "ghost term")
        assert applied == 0
        assert store.applications()[-1]["result"] == "SKIPPED"
    finally:
        conn.close()
        store.close()
