"""تصدير XLIFF 2.0 — ملف المراجعة البشرية الذهاب/الإياب مع أدوات CAT."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from ..storage.db import fetch_pairs


def build_xliff(pairs: list[dict]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff xmlns="urn:oasis:names:tc:xliff:document:2.0" version="2.0"'
        ' srcLang="en" trgLang="ar">\n'
        '  <file id="f1" original="orthok-alignments">\n'
    ]
    for p in pairs:
        if p["align_type"] == "UNALIGNED":
            continue
        src = " ".join(s["text"] for s in p["src"]).strip()
        tgt = " ".join(t["text"] for t in p["tgt"]).strip()
        if not src:
            continue
        state = {"PROVEN": "final", "BLOCKED": "review"}.get(p["status"], "translated")
        parts.append(
            f'    <unit id="A-{p["alignment_id"]}">\n'
            f'      <metadata>\n'
            f'        <prop type="confidence">{p["confidence"]:.4f}</prop>\n'
            f'        <prop type="alignType">{escape(p["align_type"])}</prop>\n'
            f'        <prop type="status">{p["status"]}</prop>\n'
            f'      </metadata>\n'
            f'      <segment state="{state}">\n'
            f'        <source>{escape(src)}</source>\n'
            f'        <target>{escape(tgt)}</target>\n'
            f'      </segment>\n'
            f'    </unit>\n'
        )
    parts.append("  </file>\n</xliff>\n")
    return "".join(parts)


def export_xliff(conn: sqlite3.Connection, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_xliff(fetch_pairs(conn)), encoding="utf-8")
    return out
