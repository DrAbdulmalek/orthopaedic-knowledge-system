"""حلقة التصحيح المستمرة — corrections.db منفصلة + تطبيق آلي (Auto-apply).

القاعدة: كل تعديل بشري = قاعدة قابلة لإعادة التطبيق. قبل كتابة أي اقتراح
آلي جديد تُستشار هذه القاعدة؛ إن وُجدت قاعدة مطابقة فهي **تتفوق** على
اقتراح المحرك (المحرك يقترح، المستخدم يقرر، والقرار يُعاد تطبيقه دائماً).
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path


class CorrectionsStore:
    """غلاف corrections.db — قاعدة منفصلة عمداً عن القاعدة المعرفية."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            resources.files("orthopaedic_knowledge.storage")
            .joinpath("corrections_schema.sql").read_text(encoding="utf-8")
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ كتابة
    def record(
        self,
        entity: str,
        entity_key: str,
        field: str,
        new_value: str,
        *,
        match_rule: str = "norm_term",
        old_value: str | None = None,
        reviewer: str | None = None,
    ) -> int:
        """سجّل قرار مراجع بشري كقاعدة دائمة."""
        if match_rule not in {"exact_id", "norm_term"}:
            raise ValueError(f"match_rule غير قانوني: {match_rule!r}")
        cur = self.conn.execute(
            """INSERT INTO corrections (entity, match_rule, entity_key, field,
                                        old_value, new_value, reviewer)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity, match_rule, entity_key, field, old_value, new_value, reviewer),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------------------ قراءة
    def lookup(self, entity: str, entity_key: str, field: str) -> sqlite3.Row | None:
        """أحدث قاعدة مطابقة (exact_id أولاً ثم norm_term)."""
        row = self.conn.execute(
            """SELECT * FROM corrections
               WHERE entity=? AND entity_key=? AND field=?
               ORDER BY (match_rule='exact_id') DESC, correction_id DESC LIMIT 1""",
            (entity, entity_key, field),
        ).fetchone()
        return row

    # ------------------------------------------------------- التطبيق الآلي
    def apply_ar_preferred(self, knowledge_conn: sqlite3.Connection, en_norm: str) -> int:
        """طبّق قواعد ar_preferred على مفهوم مصطلحه الإنجليزي en_norm.

        يعيد عدد القواعد المطبقة فعلياً؛ كل محاولة تُدوَّن في
        correction_applications (APPLIED / SKIPPED) — الشفافية إلزامية.
        """
        rule = self.lookup("term", en_norm, "ar_preferred")
        if rule is None:
            return 0
        rows = knowledge_conn.execute(
            """SELECT t.term_id, t.concept_id FROM terms t
               WHERE t.lang='en' AND t.term_norm=? LIMIT 1""",
            (en_norm,),
        ).fetchall()
        if not rows:
            self._log(rule["correction_id"], "term", en_norm, "SKIPPED", "لا مفهوم بعد")
            return 0
        concept_id = rows[0]["concept_id"]
        new_norm = _norm(rule["new_value"])
        # حماية PROVEN الصارمة (مرحلة 1): وجود مصطلح عربي PROVEN بمرتبة preferred
        # في المفهوم يمنع أي تصحيح آلي مختلف — يُدوَّن BLOCKED ولا يُنَفَّذ؛
        # حتى القيمة الجديدة نفسها لا تُرقّى فوق مصطلح PROVEN قائم.
        proven = knowledge_conn.execute(
            """SELECT term_text, term_norm FROM terms
               WHERE concept_id=? AND lang='ar' AND status='PROVEN' AND role='preferred'
               LIMIT 1""",
            (concept_id,),
        ).fetchone()
        if proven is not None and proven["term_norm"] != new_norm:
            self._log(
                rule["correction_id"],
                "term",
                f"{concept_id}/{en_norm}",
                "BLOCKED",
                f"مصطلح PROVEN محمي ({proven['term_text']}) — لا يُستبدل آلياً",
            )
            return 0
        # ترقية المصطلح المصحح (أو إدراجه إن غاب) وتنزيل البقية إلى synonyms.
        # الطبقة الثانية من الحماية: حتى لو شُطب شرط أعلاه فلا يُنزَّل PROVEN،
        # ولا تُستبدل قيمة PROVEN قائمة في الـ upsert.
        knowledge_conn.execute(
            """UPDATE terms SET role='synonym', dialect_weight=0.0,
                   context_note='demoted by correction #' || ?
               WHERE concept_id=? AND lang='ar' AND status != 'PROVEN'""",
            (rule["correction_id"], concept_id),
        )
        knowledge_conn.execute(
            """INSERT INTO terms (concept_id, lang, term_text, term_norm, role,
                                  dialect_weight, context_note, source, status)
               VALUES (?, 'ar', ?, ?, 'preferred', 1.0, ?, ?, 'UNPROVEN')
               ON CONFLICT(concept_id, lang, term_norm) DO UPDATE SET
                   role='preferred', dialect_weight=1.0,
                   context_note=excluded.context_note, source=excluded.source
               WHERE terms.status != 'PROVEN'""",
            (
                concept_id, rule["new_value"], new_norm,
                f"correction #{rule['correction_id']} by {rule['reviewer'] or 'reviewer'}",
                f"CORRECTION:{rule['correction_id']}",
            ),
        )
        knowledge_conn.commit()
        self._log(rule["correction_id"], "term", f"{concept_id}/{en_norm}", "APPLIED", rule["new_value"])
        return 1

    def _log(self, correction_id: int, target_entity: str, target_key: str, result: str, detail: str) -> None:
        self.conn.execute(
            """INSERT INTO correction_applications (correction_id, target_entity, target_key, result, detail)
               VALUES (?, ?, ?, ?, ?)""",
            (correction_id, target_entity, target_key, result, detail),
        )
        self.conn.commit()

    def applications(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM correction_applications ORDER BY application_id"
        )]

    def all_rules(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM corrections ORDER BY correction_id"
        )]


def _norm(value: str) -> str:
    from ..terminology.normalizer_ar import norm_ar

    return norm_ar(value)
