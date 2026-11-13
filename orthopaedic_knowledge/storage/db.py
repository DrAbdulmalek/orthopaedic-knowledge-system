"""طبقة الوصول للقاعدة المعرفية — مساعدات صريحة فوق المخطط."""

from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    """افتح (وأنشئ إن لزم) القاعدة وطبّق المخطط — فشل المخطط يوقف كل شيء."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(load_schema())
    conn.commit()
    return conn


def load_schema() -> str:
    return resources.files("orthopaedic_knowledge.storage").joinpath("schema.sql").read_text(encoding="utf-8")


def add_document(conn: sqlite3.Connection, book_code: str, lang: str, chapter: str) -> int:
    conn.execute(
        """INSERT INTO books (book_code) VALUES (?)
           ON CONFLICT(book_code) DO NOTHING""",
        (book_code,),
    )
    book_id = conn.execute("SELECT book_id FROM books WHERE book_code=?", (book_code,)).fetchone()["book_id"]
    cur = conn.execute(
        """INSERT INTO documents (book_id, lang, chapter) VALUES (?, ?, ?)
           ON CONFLICT(book_id, lang, chapter) DO NOTHING""",
        (book_id, lang, chapter),
    )
    conn.commit()
    row = conn.execute(
        "SELECT doc_id FROM documents WHERE book_id=? AND lang=? AND chapter=?",
        (book_id, lang, chapter),
    ).fetchone()
    return int(row["doc_id"])


def add_segment(
    conn: sqlite3.Connection,
    sentence_id: str,
    lang: str,
    doc_id: int,
    text: str,
    text_norm: str,
    page: int,
    *,
    para_index: int | None = None,
    sent_index: int | None = None,
    kind: str = "body",
    section_path: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO segments (sentence_id, lang, doc_id, text, text_norm, page,
                                 para_index, sent_index, kind, section_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sentence_id, lang, doc_id, text, text_norm, page, para_index, sent_index, kind, section_path),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_alignment(
    conn: sqlite3.Connection,
    src_refs: list[str],
    tgt_refs: list[str],
    align_type: str,
    confidence: float,
    breakdown: dict,
    book_code: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO alignments (src_refs, tgt_refs, book_code, align_type,
                                   confidence, confidence_breakdown, status)
           VALUES (?, ?, ?, ?, ?, ?, 'UNPROVEN')""",
        (
            json.dumps(src_refs, ensure_ascii=False),
            json.dumps(tgt_refs, ensure_ascii=False),
            book_code, align_type, confidence,
            json.dumps(breakdown, ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_flag(conn: sqlite3.Connection, alignment_id: int, flag_type: str, detail: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO qa_flags (alignment_id, flag_type, detail) VALUES (?, ?, ?)",
        (alignment_id, flag_type, detail),
    )
    conn.commit()
    return int(cur.lastrowid)


def set_status(
    conn: sqlite3.Connection, entity: str, entity_id: int | str, status: str,
    reviewer: str | None = None,
) -> None:
    """انتقال حالة صريح — قيم غير معروفة تُرفض (Fail-Closed)."""
    if status not in {"PROVEN", "UNPROVEN", "BLOCKED"}:
        raise ValueError(f"حالة غير قانونية: {status!r}")
    table = {"alignment": "alignments", "term": "terms", "concept": "concepts"}[entity]
    id_col = {"alignment": "alignment_id", "term": "term_id", "concept": "concept_id"}[entity]
    conn.execute(
        f"UPDATE {table} SET status=?, reviewer=COALESCE(?, reviewer),"
        f" reviewed_at=datetime('now') WHERE {id_col}=?",
        (status, reviewer, entity_id),
    )
    conn.commit()


def fetch_pairs(conn: sqlite3.Connection) -> list[dict]:
    """سجلات المحاذاة مع نصوصها — المصدر دائماً EN والهدف دائماً AR."""
    out: list[dict] = []
    for row in conn.execute("SELECT * FROM alignments ORDER BY alignment_id"):
        src_ids, tgt_ids = json.loads(row["src_refs"]), json.loads(row["tgt_refs"])

        def texts(ids: list[str], lang: str) -> list[dict]:
            res = []
            for sid in ids:
                r = conn.execute(
                    "SELECT sentence_id, text, lang, page FROM segments WHERE sentence_id=? AND lang=?",
                    (sid, lang),
                ).fetchone()
                if r:
                    res.append(dict(r))
            return res

        out.append({
            "alignment_id": row["alignment_id"], "align_type": row["align_type"],
            "confidence": row["confidence"], "status": row["status"],
            "src": texts(src_ids, "en"), "tgt": texts(tgt_ids, "ar"),
        })
    return out
