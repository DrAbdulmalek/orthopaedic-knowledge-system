"""اختبارات المصطلحات: مفاهيم + ترجيح سوري + تعارضات → BLOCKED."""

import pytest

from orthopaedic_knowledge.storage import CorrectionsStore, connect
from orthopaedic_knowledge.terminology import (
    choose_preferred,
    store_all,
    syrian_weight,
)
from orthopaedic_knowledge.terminology.mwt_extractor import TermCandidate


@pytest.fixture()
def env(tmp_path):
    conn = connect(tmp_path / "k.db")
    store = CorrectionsStore(tmp_path / "c.db")
    yield conn, store
    conn.close()
    store.close()


def test_syrian_preference_cast():
    decision = choose_preferred({"الجبس": 1, "جبيرة جبسية": 1})
    assert decision.preferred == "الجبس"           # سوري معتمد يتقدم على التواتر المتساوي
    assert syrian_weight("الجبس") == 1.0
    assert decision.contextual_synonyms == ("جبيرة جبسية",)
    assert "سوري" in decision.reason


def test_frequency_breaks_tie_without_syrian():
    decision = choose_preferred({"الترقيع": 3, "الترميم": 1})
    assert decision.preferred == "الترقيع"
    assert syrian_weight("الترقيع") == 0.0


def test_store_candidate_groups_synonyms(env):
    conn, store = env
    cand = TermCandidate(
        en_term="avascular necrosis", en_norm="avascular necrosis", count=3,
        ar_variants={"النخر العظمي اللاوعائي": 2, "النخر اللاوعائي": 1, "موت العظم": 1},
        example_alignments=[1],
    )
    cid = store_all(conn, store, [cand], specialty="Hip Surgery")[0]
    terms = list(conn.execute("SELECT * FROM terms WHERE concept_id=? ORDER BY term_id", (cid,)))
    assert len([t for t in terms if t["lang"] == "en"]) == 1
    ar_terms = [t for t in terms if t["lang"] == "ar"]
    assert len(ar_terms) == 3
    assert sum(1 for t in ar_terms if t["role"] == "preferred") == 1
    assert all(t["status"] == "UNPROVEN" for t in terms)   # المحرك لا يعتمد أبداً


def test_three_variants_arabic_blocked(env):
    conn, store = env
    cand = TermCandidate(
        en_term="osteosynthesis", en_norm="osteosynthesis", count=3,
        ar_variants={"التثبيت العظمي": 1, "التثبيت الداخلي": 1, "الترقيع الجراحي": 1},
    )
    store_all(conn, store, [cand])
    from orthopaedic_knowledge.qa import detect_term_conflicts

    conflicts = detect_term_conflicts(conn)
    assert len(conflicts) == 1
    status = conn.execute("SELECT status FROM concepts LIMIT 1").fetchone()["status"]
    assert status == "BLOCKED"
    n = conn.execute("SELECT COUNT(*) c FROM qa_blocks WHERE stage='qa.conflict'").fetchone()["c"]
    assert n == 1
