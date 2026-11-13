"""تصدير TMX 1.4b — للذاكرة الترجمية في أدوات CAT.

قواعد ثابتة:
* وحدات UNALIGNED لا تُصدَّر أبداً (لا ذاكرة من محاذاة مشكوك فيها).
* تصدير UNPROVEN يحتاج min_confidence صريحاً؛ خصائص المشروع (الثقة/الحالة)
  تُحفظ داخل <prop> حتى لا تضيع عند التبادل.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from ..storage.db import fetch_pairs
from ..ids import parse_sentence_id

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<tmx version="1.4">\n'
    '  <header creationtool="orthopaedic-knowledge" creationtoolversion="0.1.0"'
    ' segtype="sentence" o-tmf="orthok-sqlite" adminlang="en"'
    ' srclang="en" datatype="plaintext"/>\n'
    '  <body>\n'
)


def build_tmx(pairs: list[dict], min_confidence: float = 0.0) -> str:
    parts = [_HEADER]
    for pair in pairs:
        if pair["align_type"] == "UNALIGNED":
            continue
        if float(pair["confidence"]) < min_confidence:
            continue
        src_text = " ".join(s["text"] for s in pair["src"]).strip()
        tgt_text = " ".join(t["text"] for t in pair["tgt"]).strip()
        if not src_text or not tgt_text:
            continue
        tuid = pair["src"][0]["sentence_id"] if pair["src"] else pair["tgt"][0]["sentence_id"]
        # Provenance داخل TMX: الشفرة الوتدية من معرف الجملة
        prov = parse_sentence_id(tuid)
        parts.append('    <tu tuid="%s" srclang="en">\n' % escape(tuid))
        if prov:
            prov_str = "{}/{}".format(prov["book"], prov["chapter"])
            parts.append(
                '      <prop type="x-provenance">%s</prop>\n' % escape(prov_str + "/p" + str(prov["page"]))
            )
        parts.append('      <prop type="x-alignment-id">A-%s</prop>\n' % pair["alignment_id"])
        parts.append('      <prop type="x-confidence">%.4f</prop>\n' % pair["confidence"])
        parts.append('      <prop type="x-status">%s</prop>\n' % pair["status"])
        parts.append(f'      <tuv xml:lang="en"><seg>{escape(src_text)}</seg></tuv>\n')
        parts.append(f'      <tuv xml:lang="ar"><seg>{escape(tgt_text)}</seg></tuv>\n')
        parts.append("    </tu>\n")
    parts.append("  </body>\n</tmx>\n")
    return "".join(parts)


def export_tmx(conn: sqlite3.Connection, out_path: str | Path, min_confidence: float = 0.0) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_tmx(fetch_pairs(conn), min_confidence=min_confidence), encoding="utf-8")
    return out
