"""تصدير الجداول: CSV (قياسي) وXLSX (openpyxl — تبعية أساسية هنا)."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from ..storage.db import fetch_pairs

ALIGN_COLUMNS = ["alignment_id", "align_type", "confidence", "status",
                 "src_sentence_ids", "src_text", "tgt_sentence_ids", "tgt_text"]
TERM_COLUMNS = ["concept_id", "lang", "term_text", "role", "dialect_weight",
                "context_note", "status", "source"]
BLOCK_COLUMNS = ["block_id", "entity", "entity_key", "stage", "reason", "created_at"]


def _iter_align_rows(conn: sqlite3.Connection):
    for p in fetch_pairs(conn):
        yield [
            p["alignment_id"], p["align_type"], round(p["confidence"], 4), p["status"],
            " | ".join(s["sentence_id"] for s in p["src"]),
            " ".join(s["text"] for s in p["src"]),
            " | ".join(t["sentence_id"] for t in p["tgt"]),
            " ".join(t["text"] for t in p["tgt"]),
        ]


def _iter_term_rows(conn: sqlite3.Connection):
    for r in conn.execute(
        """SELECT concept_id, lang, term_text, role, dialect_weight, context_note,
                  status, source FROM terms
           ORDER BY concept_id, lang, role DESC, term_id"""
    ):
        yield [r[c] for c in TERM_COLUMNS]


def export_csv(conn: sqlite3.Connection, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, columns, rows in (
        ("alignments.csv", ALIGN_COLUMNS, _iter_align_rows(conn)),
        ("terms.csv", TERM_COLUMNS, _iter_term_rows(conn)),
    ):
        p = out / name
        with p.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM → Excel آمن للعربية
            w = csv.writer(fh)
            w.writerow(columns)
            w.writerows(rows)
        paths.append(p)
    return paths


def export_xlsx(conn: sqlite3.Connection, out_path: str | Path) -> Path:
    """مصنف XLSX بأوراق: Alignments + Terms + Blocked (سجل الرفض الفشل-الآمن)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Alignments"
    ws1.append(ALIGN_COLUMNS)
    for row in _iter_align_rows(conn):
        ws1.append(row)

    ws2 = wb.create_sheet("Terms")
    ws2.append(TERM_COLUMNS)
    for row in _iter_term_rows(conn):
        ws2.append(row)

    ws3 = wb.create_sheet("Blocked")
    ws3.append(BLOCK_COLUMNS)
    for r in conn.execute(
        """SELECT block_id, entity, entity_key, stage, reason, created_at
           FROM qa_blocks ORDER BY block_id"""
    ):
        ws3.append([r[c] for c in BLOCK_COLUMNS])

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return out
