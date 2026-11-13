"""مخزن التوليف synthesis.db — منفصلة عمداً عن knowledge.db وcorrections.db.

نفس انضباط storage: مخطط إلزامي عند الفتح، كل إدراج يتحقق من قيوده،
وأي إخلال بالمخطط يوقف العملية (Fail-Closed بنيوي).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from .models import Link, Unit


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        resources.files("orthopaedic_knowledge.synthesis").joinpath("schema.sql").read_text(encoding="utf-8")
    )
    conn.commit()
    return conn


def add_source(conn: sqlite3.Connection, book_code: str, role: str, chapter: str, origin: str) -> int:
    cur = conn.execute(
        """INSERT INTO sources (book_code, role, chapter, origin)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(book_code) DO UPDATE SET role=excluded.role,
               chapter=excluded.chapter, origin=excluded.origin""",
        (book_code, role, chapter, str(origin)),
    )
    conn.commit()
    row = conn.execute("SELECT source_id FROM sources WHERE book_code=?", (book_code,)).fetchone()
    return int(row["source_id"])


def add_unit(conn: sqlite3.Connection, source_id: int, unit: Unit) -> None:
    conn.execute(
        """INSERT INTO units (unit_id, source_id, kind, page_first, page_last,
                              section_path, text, text_norm, seq)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            unit.unit_id, source_id, unit.kind, unit.page_first, unit.page_last,
            unit.section_path, unit.text, " ".join(unit.text.lower().split()), unit.seq,
        ),
    )
    conn.commit()


def add_link(conn: sqlite3.Connection, link: Link) -> int:
    link.validate()
    cur = conn.execute(
        """INSERT INTO links (spine_unit_id, other_unit_id, book_code, score,
                              lexical, semantic, decision, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (link.spine_unit, link.other_unit, link.book_code, link.score,
         link.lexical, link.semantic, link.decision, link.reason),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_delta(
    conn: sqlite3.Connection,
    unit: Unit,
    anchor_unit_id: str | None,
    facts: dict,
    reason: str = "",
) -> int:
    cur = conn.execute(
        """INSERT INTO deltas (unit_id, anchor_unit, new_facts, reason, book_code)
           VALUES (?, ?, ?, ?, ?)""",
        (unit.unit_id, anchor_unit_id, json.dumps(facts, ensure_ascii=False), reason, unit.book_code),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_conflict(
    conn: sqlite3.Connection,
    conflict_type: str,
    spine_unit_id: str,
    other_unit_id: str,
    book_code: str,
    spine_detail: dict,
    other_detail: dict,
) -> int:
    cur = conn.execute(
        """INSERT INTO conflicts (conflict_type, spine_unit_id, other_unit_id, book_code,
                                  spine_detail, other_detail, status)
           VALUES (?, ?, ?, ?, ?, ?, 'BLOCKED')""",
        (conflict_type, spine_unit_id, other_unit_id, book_code,
         json.dumps(spine_detail, ensure_ascii=False), json.dumps(other_detail, ensure_ascii=False)),
    )
    conn.commit()
    return int(cur.lastrowid)


def block(conn: sqlite3.Connection, stage: str, ref: str, detail: str) -> None:
    conn.execute("INSERT INTO blocked_log (stage, ref, detail) VALUES (?, ?, ?)",
                 (stage, ref, detail))
    conn.commit()


def fetch_units(conn: sqlite3.Connection, book_code: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT u.* FROM units u JOIN sources s ON s.source_id = u.source_id
           WHERE s.book_code=? ORDER BY u.seq""", (book_code,)
    )]


def fetch_links(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM links ORDER BY link_id")]


def fetch_deltas(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT d.*, u.text AS unit_text FROM deltas d JOIN units u ON u.unit_id = d.unit_id
           ORDER BY d.delta_id"""
    )]


def fetch_conflicts(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    """التعارضات بتفاصيلها؛ فلترة اختيارية بالحالة + درجة الربط من links."""
    sql = """SELECT c.*, a.text AS spine_text, b.text AS other_text, l.score
             FROM conflicts c
             JOIN units a ON a.unit_id = c.spine_unit_id
             JOIN units b ON b.unit_id = c.other_unit_id
             LEFT JOIN links l ON l.other_unit_id = c.other_unit_id"""
    params: tuple = ()
    if status is not None:
        sql += " WHERE c.status=?"
        params = (status,)
    sql += " ORDER BY c.conflict_id"
    return [dict(r) for r in conn.execute(sql, params)]


RESOLVE_CHOICES = ("spine", "other", "custom")
RESOLVE_STATUSES = ("PROVEN", "UNPROVEN", "BLOCKED")


def resolve_conflict(
    conn: sqlite3.Connection,
    conflict_id: int,
    *,
    status: str,
    choice: str,
    text: str | None = None,
    reviewer: str | None = None,
) -> dict:
    """حسم بشري لتعارض — القرار كله يُخزَّن JSON في resolution للتدقيق.

    choice: spine (اعتماد نص العمود الفقري) / other (اعتماد نص الكتاب الآخر)
    / custom (نص معدّل — requires text غير فارغ، لا تخمين).
    """
    if status not in RESOLVE_STATUSES:
        raise ValueError(f"status غير قانوني: {status!r}")
    if choice not in RESOLVE_CHOICES:
        raise ValueError(f"choice غير قانوني: {choice!r} (المسموح: {RESOLVE_CHOICES})")
    row = conn.execute("SELECT spine_unit_id, other_unit_id FROM conflicts WHERE conflict_id=?",
                       (conflict_id,)).fetchone()
    if row is None:
        raise LookupError(f"لا تعارض برقم {conflict_id}")
    if choice == "custom":
        final = (text or "").strip()
        if not final:
            raise ValueError("قرار custom يتطلب نصاً غير فارغ — الحسم لا يُخمَّن")
    else:
        col = "spine_unit_id" if choice == "spine" else "other_unit_id"
        final = conn.execute("SELECT text FROM units WHERE unit_id=?",
                             (row[col],)).fetchone()["text"]
    payload = json.dumps(
        {
            "choice": choice, "text": final,
            "reviewer": reviewer or "reviewer",
            "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        ensure_ascii=False,
    )
    conn.execute("UPDATE conflicts SET status=?, resolution=? WHERE conflict_id=?",
                 (status, payload, conflict_id))
    conn.commit()
    return {**json.loads(payload), "status": status}


def fetch_resolutions(conn: sqlite3.Connection) -> dict[str, dict]:
    """قرارات المراجعين مفهرسة بوحدة العمود الفقري — مدخل إعادة توليد الفصل."""
    out: dict[str, dict] = {}
    for r in conn.execute(
        """SELECT conflict_id, spine_unit_id, status, resolution FROM conflicts
           WHERE resolution IS NOT NULL ORDER BY conflict_id"""
    ):
        try:
            payload = json.loads(r["resolution"])
        except json.JSONDecodeError:
            continue  # قرار تالف يُتجاهل هنا — إصلاحه قرار بشري أيضاً
        out[r["spine_unit_id"]] = {
            **payload, "conflict_id": r["conflict_id"], "status": r["status"],
        }
    return out


def fetch_spine_source(conn: sqlite3.Connection) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT book_code, chapter FROM sources WHERE role='spine' LIMIT 1"
    ).fetchone()
    return (row["book_code"], row["chapter"]) if row else None


def _row_to_unit(row: sqlite3.Row) -> Unit:
    return Unit(
        book_code=row["unit_id"].split("_")[0],
        chapter="",  # يُستخرج من المعرف عند الحاجة — الصف هنا كافٍ للعرض
        seq=row["seq"], kind=row["kind"], page_first=row["page_first"],
        page_last=row["page_last"], text=row["text"], section_path=row["section_path"],
    )
