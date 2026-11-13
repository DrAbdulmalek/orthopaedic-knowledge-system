"""تقارير التوليف — الفصل الامتحاني الموحد (Markdown) + تقرير عربي RTL (HTML).

الفصل الموحد: نص العمود الفقري أولاً، التكرارات تنهار إلى سطر توثيق،
الإضافات تلحق بمراساها بمعرف إثبات، والتعارضات تُعلَّم ⚠ بانتظار الحسم.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import SynthesisResult
from .store import fetch_conflicts, fetch_deltas, fetch_links, fetch_resolutions, fetch_units


def build_unified_markdown(conn, spine_book: str, chapter: str) -> str:
    parts = [f"# الفصل الامتحاني الموحد — {chapter}\n",
             f"**العمود الفقري:** {spine_book} — الكتب الأخرى مدموجة تحته بمعرفات إثبات.\n"]
    links = fetch_links(conn)
    dup_by_other: dict[str, list[dict]] = {}
    for ln in links:
        if ln["decision"] == "DUPLICATE":
            dup_by_other.setdefault(ln["spine_unit_id"], []).append(ln)
    deltas = fetch_deltas(conn)
    delta_by_anchor: dict[str | None, list[dict]] = {}
    for d in deltas:
        delta_by_anchor.setdefault(d["anchor_unit"], []).append(d)
    conflicts = fetch_conflicts(conn)
    resolutions = fetch_resolutions(conn)

    for u in fetch_units(conn, spine_book):
        if u["kind"] != "body":
            continue
        parts.append(f"\n## {u['unit_id']} (ص.{u['page_first']})\n")
        res = resolutions.get(u["unit_id"])
        if res is not None and res.get("choice") in {"other", "custom"}:
            # قرار المراجع المعتمد يحل محل نص العمود الفقري — الإثبات الأصلي محفوظ أعلاه
            parts.append(res["text"] + "\n")
            parts.append(
                f"> ✅ نص معتمد بشرياً [PROVEN] — قرار «{res['choice']}» "
                f"بواسطة {res['reviewer']} على التعارض #{res['conflict_id']}.\n"
            )
        else:
            parts.append(u["text"] + "\n")
        for ln in dup_by_other.get(u["unit_id"], []):
            parts.append(f"> ✚ موثّق أيضاً في: {ln['book_code']} — تكرار منهار، لا إعادة نص.\n")
        for d in delta_by_anchor.get(u["unit_id"], []):
            parts.append(f"\n**+ إضافة (DELTA) — {d['book_code']}, {d['unit_id']}:** {d['unit_text']}\n")
    for d in delta_by_anchor.get(None, []):
        parts.append(f"\n## + إضافة مستقلة (DELTA) — {d['book_code']}, {d['unit_id']}\n")
        parts.append(d["unit_text"] + "\n")

    if conflicts:
        parts.append("\n## ⚠ جدول تعارضات المراجع — الحسم بشري موثق (الحالة لكل سطر)\n")
        parts.append("| # | النوع | العمود الفقري | الكتاب الآخر | الحالة |\n|---|---|---|---|---|\n")
        for c in conflicts:
            parts.append(
                "| {i} | {t} | {sp}: {sd} | {ob}: {od} | {st} |\n".format(
                    i=c["conflict_id"], t=c["conflict_type"],
                    sp=c["spine_unit_id"], sd=html.escape(json.loads(c["spine_detail"]).__str__()),
                    ob=c["book_code"], od=html.escape(json.loads(c["other_detail"]).__str__()),
                    st=c["status"],
                )
            )
    return "\n".join(parts) + "\n"


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
.badge { padding:.1rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; }
.b-dup { background:#e3f7e8; color:#1c7c38; }
.b-delta { background:#e3efff; color:#1d4ed8; }
.b-conflict { background:#fde3e3; color:#b3261e; }
.muted { color:var(--muted); font-size:.85rem; }
"""


def build_html_report(conn, result: SynthesisResult) -> str:
    cards = "".join(
        f'<div class="card"><div class="num">{n}</div><div class="lbl">{lbl}</div></div>'
        for lbl, n in (
            ("كتب مدموجة", len(result.other_books) + 1),
            ("تكرارات منهارة", result.decisions.get("DUPLICATE", 0)),
            ("إضافات (DELTA)", result.decisions.get("DELTA", 0)),
            ("تعارضات معلّقة", result.decisions.get("CONFLICT", 0)),
        )
    )
    rows = []
    for c in fetch_conflicts(conn):
        rows.append(
            f"<tr><td>{c['conflict_id']}</td><td>{html.escape(c['conflict_type'])}</td>"
            f"<td>{html.escape(c['spine_text'], 120)}</td>"
            f"<td>{html.escape(c['other_text'], 120)}</td>"
            f"<td><span class='badge b-conflict'>{c['status']}</span></td>"
            f"<td class='muted'>{c['spine_unit_id']} ↔ {c['other_unit_id']}</td></tr>"
        )
    delta_rows = []
    for d in fetch_deltas(conn):
        anchor = d["anchor_unit"] or "— قسم مستقل —"
        delta_rows.append(
            f"<tr><td>{html.escape(d['book_code'])}</td><td>{d['unit_id']}</td>"
            f"<td class='muted'>{anchor}</td><td>{html.escape(d['unit_text'], 160)}</td></tr>"
        )
    return (
        "<!DOCTYPE html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        "<title>تقرير التوليف — دمج الكتب</title><style>" + _CSS + "</style></head><body>"
        f"<h1>تقرير التوليف — {html.escape(result.chapter)} — العمود الفقري: "
        f"{html.escape(result.spine_book)}</h1>"
        f"<div class='cards'>{cards}</div>"
        "<h2>جدول تعارضات المراجع (BLOCKED — حسم بشري إلزامي)</h2>"
        "<table><tr><th>#</th><th>النوع</th><th>نص العمود الفقري</th>"
        "<th>نص الكتاب الآخر</th><th>الحالة</th><th>الإثبات</th></tr>"
        + ("".join(rows) or "<tr><td colspan='6' class='muted'>لا تعارضات</td></tr>") + "</table>"
        "<h2>الإضافات المدموجة (DELTA)</h2>"
        "<table><tr><th>الكتاب</th><th>معرف الوحدة</th><th>المرساة</th><th>النص</th></tr>"
        + ("".join(delta_rows) or "<tr><td colspan='4' class='muted'>لا إضافات</td></tr>") + "</table>"
        "</body></html>"
    )


def write_outputs(conn, result: SynthesisResult, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / "unified_chapter.md"
    md.write_text(build_unified_markdown(conn, result.spine_book, result.chapter), encoding="utf-8")
    html_path = out / "synthesis_report.html"
    html_path.write_text(build_html_report(conn, result), encoding="utf-8")
    js = out / "synthesis_summary.json"
    js.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(md), "report": str(html_path), "summary": str(js)}
