"""تصدير TBX-Basic (ISO 30042) — تبادل المسرد المفهومي بين الأدوات.

سياسة التصدير (docs/WORKFLOW.md): المفاهيم **BLOCKED لا تُصدَّر نهائياً**
حتى حسم المراجع؛ UNPROVEN تُصدَّر مع admin conceptStatus صريح.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from .. import __version__

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<tbx type="TBX-Basic" style="dca" xml:lang="en" xmlns="urn:iso:std:iso:30042:ed-2">\n'
    '  <tbxHeader><fileDesc>\n'
    '    <titleStmt><title>Orthopaedic Concept-Oriented Terminology</title></titleStmt>\n'
    f'    <sourceDesc><p>orthopaedic-knowledge {__version__} (local)</p></sourceDesc>\n'
    '  </fileDesc></tbxHeader>\n'
    '  <text>\n    <body>\n'
)


def load_concepts(conn: sqlite3.Connection, include_blocked: bool = False) -> list[dict]:
    """اجلب المفاهيم؛ BLOCKED مستبعدة افتراضياً — سياسة التصدير لا اختياراً."""
    out = []
    sql = "SELECT * FROM concepts" + ("" if include_blocked else " WHERE status != 'BLOCKED'") + " ORDER BY concept_id"
    for crow in conn.execute(sql):
        terms = [dict(trow) for trow in conn.execute(
            "SELECT * FROM terms WHERE concept_id=? ORDER BY role DESC, term_id",
            (crow["concept_id"],),
        )]
        out.append({
            "concept_id": crow["concept_id"], "specialty": crow["specialty"],
            "status": crow["status"], "definition": crow["definition"], "terms": terms,
        })
    return out


def build_tbx(concepts: list[dict]) -> str:
    parts = [_HEADER]
    for c in concepts:
        parts.append(f'      <conceptEntry id="{escape(c["concept_id"])}">\n')
        if c.get("specialty"):
            parts.append(f'        <descrip type="subjectField">{escape(c["specialty"])}</descrip>\n')
        if c.get("definition"):
            parts.append(f'        <descrip type="definition">{escape(c["definition"])}</descrip>\n')
        parts.append(f'        <admin type="conceptStatus">{escape(c["status"])}</admin>\n')
        for lang in ("en", "ar"):
            lang_terms = [t for t in c["terms"] if t["lang"] == lang]
            if not lang_terms:
                continue
            parts.append(f'        <langSec xml:lang="{lang}">\n')
            for t in lang_terms:
                parts.append("          <termSec>\n")
                parts.append(f'            <term>{escape(t["term_text"])}</term>\n')
                parts.append(f'            <termNote type="termType">{escape(t["term_type"])}</termNote>\n')
                if t["role"] == "preferred":
                    parts.append('            <termNote type="administrativeStatus">preferredTerm-admn-sts</termNote>\n')
                if t["dialect_weight"]:
                    parts.append(f'            <termNote type="dialectWeight">{t["dialect_weight"]}</termNote>\n')
                parts.append(f'            <admin type="termStatus">{escape(t["status"])}</admin>\n')
                if t.get("source"):
                    parts.append(f'            <descrip type="source">{" ".join(escape(str(t["source"])).split())}</descrip>\n')
                parts.append("          </termSec>\n")
            parts.append("        </langSec>\n")
        parts.append("      </conceptEntry>\n")
    parts.append("    </body>\n  </text>\n</tbx>\n")
    return "".join(parts)


def export_tbx(conn: sqlite3.Connection, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_tbx(load_concepts(conn)), encoding="utf-8")
    return out
