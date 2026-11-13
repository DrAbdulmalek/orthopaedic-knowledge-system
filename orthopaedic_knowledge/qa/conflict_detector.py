"""كاشف التعارضات — يرفع المصطلحات المتضاربة إلى BLOCKED (لا يخمّن رابحاً)."""

from __future__ import annotations

import sqlite3

from ..fail_closed import block_item


def detect_term_conflicts(conn: sqlite3.Connection, min_variants: int = 3) -> list[dict]:
    """مفهوم بـ 3+ مترادفات عربية متمايزة → BLOCKED للمراجعة الإلزامية."""
    rows = conn.execute(
        """SELECT c.concept_id, COUNT(DISTINCT t.term_norm) v
           FROM concepts c JOIN terms t ON t.concept_id=c.concept_id
           WHERE t.lang='ar'
           GROUP BY c.concept_id HAVING v >= ?""",
        (min_variants,),
    ).fetchall()
    out = []
    for r in rows:
        conn.execute(
            "UPDATE concepts SET status='BLOCKED' WHERE concept_id=? AND status='UNPROVEN'",
            (r["concept_id"],),
        )
        block_item(conn, "concept", r["concept_id"], "qa.conflict",
                   f"{r['v']} مترادفات عربية متمايزة — يتطلب حسم المراجع")
        out.append({"concept_id": r["concept_id"], "variants": r["v"], "status": "BLOCKED"})
    conn.commit()
    return out


def bidirectional_mismatch(conn: sqlite3.Connection) -> list[dict]:
    """مصطلح EN وحيد يربطه مفهومان مختلفان (تشعّب معاني) → علم بيدirectional."""
    rows = conn.execute(
        """SELECT term_norm, COUNT(DISTINCT concept_id) c FROM terms
           WHERE lang='en' GROUP BY term_norm HAVING c > 1"""
    ).fetchall()
    out = [{"term_norm": r["term_norm"], "concepts": r["c"]} for r in rows]
    for r in out:
        conn.execute(
            """INSERT INTO qa_blocks (entity, entity_key, stage, reason)
               VALUES ('term', ?, 'qa.conflict',
                       'BIDIRECTIONAL_MISMATCH: مصطلح إنجليزي يربط مفهومين')""",
            (r["term_norm"],),
        )
    conn.commit()
    return out
