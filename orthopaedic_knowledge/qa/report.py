"""تقرير ضمان الجودة — HTML عربي RTL مكتفٍ بذاته (CSS مضمّن)."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path

from ..storage.db import fetch_pairs

_CSS = """
:root { --ink:#1a2332; --muted:#5a6a7e; --line:#dde4ec; --bg:#f6f8fb; }
* { box-sizing: border-box; }
body { font-family:"Noto Naskh Arabic","Noto Sans Arabic",Tahoma,sans-serif;
       color:var(--ink); background:var(--bg); margin:0; padding:2rem; }
h1 { font-size:1.4rem; } h2 { font-size:1.1rem; margin-top:2rem; }
.cards { display:flex; gap:1rem; flex-wrap:wrap; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px;
        padding:1rem 1.4rem; min-width:9rem; }
.card .num { font-size:1.6rem; font-weight:700; }
.card .lbl { color:var(--muted); font-size:.85rem; }
table { border-collapse:collapse; width:100%; background:#fff;
        border:1px solid var(--line); border-radius:10px; overflow:hidden; }
th,td { padding:.5rem .7rem; border-bottom:1px solid var(--line);
        text-align:right; font-size:.9rem; vertical-align:top; }
th { background:#eef2f8; }
tr.unaligned td { background:#fff4f4; }
.badge { padding:.1rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
.b-proven { background:#e3f7e8; color:#1c7c38; }
.b-unproven { background:#fff3d6; color:#946800; }
.b-blocked { background:#fde3e3; color:#b3261e; }
.muted { color:var(--muted); font-size:.85rem; }
"""


def _esc(t: str, limit: int = 200) -> str:
    t = html.escape((t or "").replace("\n", " "))
    return t if len(t) <= limit else t[: limit - 1] + "…"


def build_report(conn: sqlite3.Connection, title: str = "منظومة المعرفة والترجمة العظمية — تقرير ضمان الجودة") -> str:
    pairs = fetch_pairs(conn)
    status_counts = {"PROVEN": 0, "UNPROVEN": 0, "BLOCKED": 0}
    for p in pairs:
        status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1
    blocks = list(conn.execute(
        "SELECT entity, entity_key, stage, reason FROM qa_blocks ORDER BY block_id DESC LIMIT 50"
    ))
    syrian = conn.execute(
        "SELECT COUNT(*) c FROM terms WHERE lang='ar' AND dialect_weight=1.0"
    ).fetchone()["c"]

    out = [
        "<!DOCTYPE html>\n<html lang=\"ar\" dir=\"rtl\">\n<head><meta charset=\"utf-8\">",
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>\n<body>",
        f"<h1>{_esc(title)}</h1>",
        '<p class="muted">تقرير محلي 100% — لا شيء غادر جهازك. راجع الأضعف أولاً وقرر: PROVEN أو BLOCKED.</p>',
        "<div class=\"cards\">",
        f'<div class="card"><div class="num">{len(pairs)}</div><div class="lbl">المحاذات</div></div>',
        f'<div class="card"><div class="num">{status_counts["UNPROVEN"]}</div><div class="lbl">UNPROVEN</div></div>',
        f'<div class="card"><div class="num">{status_counts["PROVEN"]}</div><div class="lbl">PROVEN</div></div>',
        f'<div class="card"><div class="num">{status_counts["BLOCKED"]}</div><div class="lbl">BLOCKED</div></div>',
        f'<div class="card"><div class="num">{syrian}</div><div class="lbl">مصطلحات سورية مفضلة</div></div>',
        "</div>",
        "<h2>أعلام التدقيق المفتوحة</h2>",
    ]
    flags = list(conn.execute(
        "SELECT flag_type, COUNT(*) n FROM qa_flags WHERE resolved=0 GROUP BY flag_type"
    ))
    if flags:
        out.append("<table><tr><th>النوع</th><th>العدد</th></tr>")
        out += [f"<tr><td>{_esc(f['flag_type'])}</td><td>{f['n']}</td></tr>" for f in flags]
        out.append("</table>")
    else:
        out.append('<p class="muted">لا أعلام مفتوحة.</p>')

    out.append("<h2>سجل الرفض (Fail-Closed) — آخر 50</h2>")
    if blocks:
        out.append("<table><tr><th>الكيان</th><th>المفتاح</th><th>المرحلة</th><th>السبب</th></tr>")
        out += [
            f"<tr><td>{_esc(b['entity'])}</td><td dir='ltr'>{_esc(b['entity_key'])}</td>"
            f"<td>{_esc(b['stage'])}</td><td>{_esc(b['reason'])}</td></tr>"
            for b in blocks
        ]
        out.append("</table>")
    else:
        out.append('<p class="muted">لا عناصر مرفوضة.</p>')

    out.append("<h2>المحاذات (تصاعدياً بالثقة)</h2>")
    out.append("<table><tr><th>#</th><th>النوع</th><th>الثقة</th><th>الحالة</th><th>EN</th><th>AR</th></tr>")
    for p in sorted(pairs, key=lambda x: x["confidence"]):
        cls = ' class="unaligned"' if p["align_type"] == "UNALIGNED" else ""
        badge = {"PROVEN": "b-proven", "BLOCKED": "b-blocked"}.get(p["status"], "b-unproven")
        out.append(
            f"<tr{cls}><td>A-{p['alignment_id']}</td><td>{_esc(p['align_type'])}</td>"
            f"<td>{p['confidence']:.2f}</td><td><span class='badge {badge}'>{p['status']}</span></td>"
            f"<td dir='ltr'>{_esc(' '.join(s['text'] for s in p['src']))}</td>"
            f"<td>{_esc(' '.join(t['text'] for t in p['tgt']))}</td></tr>"
        )
    out.append("</table></body></html>")
    return "\n".join(out)


def export_report(conn: sqlite3.Connection, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(conn), encoding="utf-8")
    return out
