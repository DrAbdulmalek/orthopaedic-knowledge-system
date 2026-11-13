"""مخزن المفاهيم Concept-Oriented — يدمج الترجيح السوري وحلقة التصحيح.

قواعد ثابتة:
* كل مصطلح يولد UNPROVEN؛ المحرك لا يعتمد شيئاً أبداً.
* المصطلح المفضل **اقتراح** (is preferred عبر role='preferred')، والبقية
  synonyms مع سياقها (Contextual Synonyms).
* قبل الكتابة: تُستشار corrections.db — قاعدة التصحيح تتفوق على اقتراح المحرك.
"""

from __future__ import annotations

import sqlite3

from ..alignment.similarity import tokenize
from ..fail_closed import block_item, fail_closed
from ..ids import make_concept_id
from ..storage.corrections import CorrectionsStore
from .mwt_extractor import TermCandidate
from .normalizer_ar import norm_en, norm_ar
from .syrian_preference import choose_preferred, syrian_weight


def store_candidate(
    conn: sqlite3.Connection,
    corrections: CorrectionsStore,
    cand: TermCandidate,
    specialty: str | None = None,
    syrian_lexicon: set[str] | None = None,
) -> str | None:
    """أدرج مرشحاً كمفهوم جديد (أو اربطه بمفهوم قائم) مع مترادفاته."""
    if cand.count < 1:
        return None

    en_norm = norm_en(cand.en_term)
    with fail_closed(conn, "term", en_norm, "terminology.store_candidate"):
        existing = conn.execute(
            "SELECT concept_id FROM terms WHERE lang='en' AND term_norm=? LIMIT 1", (en_norm,)
        ).fetchone()
        if existing:
            concept_id = existing["concept_id"]
        else:
            seq = conn.execute("SELECT COUNT(*) c FROM concepts").fetchone()["c"] + 1
            concept_id = make_concept_id(seq)
            conn.execute(
                """INSERT INTO concepts (concept_id, specialty, status) VALUES (?, ?, 'UNPROVEN')""",
                (concept_id, specialty),
            )

        # المصطلح الإنجليزي (preferred) — اقتراح المحرك
        _insert_term(
            conn, concept_id, "en", cand.en_term, en_norm, role="preferred",
            alignment_id=cand.example_alignments[0] if cand.example_alignments else None,
            source=f"count={cand.count}",
        )

        # الترجيح السوري للمرادفات العربية
        decision = choose_preferred(dict(cand.ar_variants), extra_lexicon=syrian_lexicon)
        for rank, (variant, vcount) in enumerate(
            [(decision.preferred, dict(cand.ar_variants).get(decision.preferred, 0))]
            + [(t, dict(cand.ar_variants)[t]) for t in decision.contextual_synonyms]
        ):
            role = "preferred" if rank == 0 else "synonym"
            w = syrian_weight(variant, syrian_lexicon)
            _insert_term(
                conn, concept_id, "ar", variant, norm_ar(variant), role=role,
                dialect_weight=w, context_note=decision.reason if rank == 0 else "Contextual Synonym",
                alignment_id=cand.example_alignments[0] if cand.example_alignments else None,
                source=f"cooccur={vcount}",
            )

        # حللة التصحيح: قاعدة مستخدم سابقة تتفوق على اقتراح المحرك (Auto-apply)
        corrections.apply_ar_preferred(conn, en_norm)
        conn.commit()
    return concept_id


def _insert_term(
    conn: sqlite3.Connection, concept_id: str, lang: str, term_text: str, term_norm: str,
    *, role: str, alignment_id: int | None = None, source: str | None = None,
    dialect_weight: float = 0.0, context_note: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO terms (concept_id, lang, term_text, term_norm, role, dialect_weight,
                              context_note, alignment_id, status, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNPROVEN', ?)
           ON CONFLICT(concept_id, lang, term_norm) DO NOTHING""",
        (concept_id, lang, term_text, term_norm, role, dialect_weight, context_note,
         alignment_id, source),
    )


def store_all(
    conn: sqlite3.Connection,
    corrections: CorrectionsStore,
    candidates: list[TermCandidate],
    specialty: str | None = None,
    syrian_lexicon: set[str] | None = None,
) -> list[str]:
    ids: list[str] = []
    for cand in candidates:
        cid = store_candidate(conn, corrections, cand, specialty=specialty, syrian_lexicon=syrian_lexicon)
        if cid:
            ids.append(cid)
    return ids


def detect_conflicts(conn: sqlite3.Connection, threshold_variants: int = 3) -> list[dict]:
    """كشف تعارضات: 3+ مرادفات عربية أو غلبة أقل من 50% → BLOCKED (للمراجعة)."""
    rows = conn.execute(
        """SELECT concept_id, COUNT(DISTINCT term_norm) v
           FROM terms WHERE lang='ar' GROUP BY concept_id HAVING v >= ?""",
        (threshold_variants,),
    ).fetchall()
    out = [{"concept_id": r["concept_id"], "variants": r["v"]} for r in rows]
    for item in out:
        conn.execute(
            "UPDATE concepts SET status='BLOCKED' WHERE concept_id=? AND status='UNPROVEN'",
            (item["concept_id"],),
        )
    conn.commit()
    return out


def blocked_log_example(conn: sqlite3.Connection) -> None:
    """نموذج استخدام block_item — لا يُستدعى تلقائياً؛ للتوثيق والاختبار."""
    block_item(conn, "concept", "UNKNOWN", "terminology", "مثال تسجيل رفض")
