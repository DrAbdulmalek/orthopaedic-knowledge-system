"""كاشف الحذف/الإضافة — أختام UNALIGNED بقراءة دلالية صريحة."""

from __future__ import annotations

import sqlite3

from ..storage.db import add_flag


def detect_omissions(conn: sqlite3.Connection, alignments: list[tuple[int, list[int], list[int], list[int], list[int]]]) -> list[dict]:
    """افحص نتائج المحاذاة وأضف أعلام الحذف/الإضافة.

    كل عنصر: (alignment_id, src_ids_present, tgt_ids_present, skipped_src_idx, skipped_tgt_idx)
    يُستخدم عادة مع نتائج ``flag_issues`` داخل خط الإنتاج — هنا نسخة موجهة
    بالسجلات لاختبارات الوحدة.
    """
    out = []
    for alignment_id, src, tgt, skip_src, skip_tgt in alignments:
        if skip_src:
            add_flag(conn, alignment_id, "SUSPECTED_OMISSION", f"skipped source: {skip_src}")
            out.append({"alignment_id": alignment_id, "type": "SUSPECTED_OMISSION", "detail": skip_src})
        if skip_tgt:
            add_flag(conn, alignment_id, "SUSPECTED_ADDITION", f"skipped target: {skip_tgt}")
            out.append({"alignment_id": alignment_id, "type": "SUSPECTED_ADDITION", "detail": skip_tgt})
        if not src and tgt:
            add_flag(conn, alignment_id, "SUSPECTED_ADDITION", "target-only alignment")
            out.append({"alignment_id": alignment_id, "type": "SUSPECTED_ADDITION", "detail": "target-only"})
        if src and not tgt:
            add_flag(conn, alignment_id, "SUSPECTED_OMISSION", "source-only alignment")
            out.append({"alignment_id": alignment_id, "type": "SUSPECTED_OMISSION", "detail": "source-only"})
    return out


def open_flags(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT f.flag_type, COUNT(*) n FROM qa_flags f
           WHERE f.resolved=0 GROUP BY f.flag_type"""
    )]
