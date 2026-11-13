"""تطبيق المراجعة المحلي — FastAPI + صفحة واحدة RTL مكتفية بذاتها.

المسارات:
* GET  /                              → صفحة المراجعة (HTML/JS مضمّن، بلا بناء)
* GET  /api/summary                   → بطاقات العدّادات
* GET  /api/conflicts?status=BLOCKED  → التعارضات بتفاصيلها ودرجاتها
* POST /api/conflicts/{id}/resolve    → الحسم البشري (spine/other/custom)
* GET  /api/deltas                    → الإضافات المدموجة
* GET  /api/export/unified.md         → الفصل الموحد معتمداً القرارات
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..synthesis import store as sstore
from ..synthesis.report import build_unified_markdown


class ResolveBody(BaseModel):
    status: str = "PROVEN"
    choice: str
    text: str | None = None
    reviewer: str | None = Field(default=None, max_length=80)


_PAGE = """<!DOCTYPE html>
<html lang='ar' dir='rtl'><head><meta charset='utf-8'>
<title>orthok review — حسم التعارضات</title>
<style>
:root { --ink:#1a2332; --muted:#5a6a7e; --line:#dde4ec; --bg:#f6f8fb; }
* { box-sizing: border-box; }
body { font-family:"Noto Naskh Arabic","Noto Sans Arabic",Tahoma,sans-serif;
       color:var(--ink); background:var(--bg); margin:0; padding:2rem; }
h1 { font-size:1.35rem; } h2 { font-size:1.05rem; margin-top:1.6rem; }
.cards { display:flex; gap:1rem; flex-wrap:wrap; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px;
        padding:.8rem 1.2rem; min-width:8rem; }
.card .num { font-size:1.5rem; font-weight:700; }
.card .lbl { color:var(--muted); font-size:.8rem; }
.conflict { background:#fff; border:1px solid var(--line); border-radius:10px;
            padding:1rem 1.2rem; margin-bottom:1rem; }
.conflict table { width:100%; border-collapse:collapse; margin:.6rem 0; }
.conflict td { padding:.5rem .6rem; border-bottom:1px solid var(--line);
               vertical-align:top; font-size:.9rem; text-align:right; }
.badge { padding:.1rem .55rem; border-radius:999px; font-size:.72rem; font-weight:600; }
.b-numbers { background:#fff3d6; color:#946800; }
.b-classification { background:#e3efff; color:#1d4ed8; }
.b-recommendation { background:#fde3e3; color:#b3261e; }
.muted { color:var(--muted); font-size:.8rem; }
button { background:#1d4ed8; color:#fff; border:0; border-radius:8px;
         padding:.5rem 1.2rem; font-family:inherit; font-size:.9rem; cursor:pointer; }
button:hover { background:#1e40af; }
textarea, input { font-family:inherit; width:100%; border:1px solid var(--line);
                  border-radius:8px; padding:.45rem; margin-top:.3rem; font-size:.9rem; }
label { font-size:.85rem; }
.row { display:flex; gap:1.4rem; flex-wrap:wrap; margin-top:.6rem; }
</style></head><body>
<h1>⚖️ حسم تعارضات المراجع — <span id="chapter" class="muted"></span></h1>
<div class="cards" id="summary"></div>
<h2>التعارضات المعلّقة (BLOCKED)</h2>
<div id="conflicts">… جارٍ التحميل …</div>
<p class="muted">القرار يُسجَّل باسمك وزمنه في synthesis.db — لا حسم آلي أبداً.</p>
<script>
async function j(url, opt) { const r = await fetch(url, opt); if (!r.ok) throw new Error(await r.text()); return r.json(); }
function esc(t) { const d = document.createElement('div'); d.textContent = t ?? ''; return d.innerHTML; }
async function load() {
  const s = await j('/api/summary');
  document.getElementById('summary').innerHTML =
    Object.entries(s.conflicts).map(([k,v]) =>
      `<div class="card"><div class="num">${v}</div><div class="lbl">تعارضات ${k}</div></div>`).join('') +
    `<div class="card"><div class="num">${s.deltas}</div><div class="lbl">إضافات مدموجة</div></div>`;
  const items = await j('/api/conflicts?status=BLOCKED');
  const box = document.getElementById('conflicts');
  if (!items.length) { box.innerHTML = '<p>✅ لا تعارضات معلّقة — كل شيء محسوم.</p>'; return; }
  box.innerHTML = items.map(c => `
    <div class="conflict" id="c${c.conflict_id}">
      <b>#${c.conflict_id}</b>
      <span class="badge b-${esc(c.conflict_type)}">${esc(c.conflict_type)}</span>
      <span class="muted">تطابق ${(c.score ?? 0).toFixed(2)} · ${esc(c.book_code)}</span>
      <table><tr><td><b>العمود الفقري</b><br>${esc(c.spine_text)}
        <div class="muted">${esc(c.spine_unit_id)}</div></td>
        <td><b>الكتاب الآخر</b><br>${esc(c.other_text)}
        <div class="muted">${esc(c.other_unit_id)}</div></td></tr></table>
      <div class="row">
        <label><input type="radio" name="ch${c.conflict_id}" value="spine" checked> اعتماد نص العمود الفقري</label>
        <label><input type="radio" name="ch${c.conflict_id}" value="other"> اعتماد نص الكتاب الآخر</label>
        <label><input type="radio" name="ch${c.conflict_id}" value="custom"> نص معدّل:</label>
      </div>
      <textarea id="tx${c.conflict_id}" rows="2" placeholder="اكتب النص المعتمد هنا عند اختيار «نص معدّل»"></textarea>
      <input id="rv${c.conflict_id}" placeholder="اسم المراجع (مثال: DR_A)">
      <button onclick="resolve(${c.conflict_id})">تسجيل الحسم [PROVEN]</button>
    </div>`).join('');
}
async function resolve(cid) {
  const choice = document.querySelector(`input[name="ch${cid}"]:checked`).value;
  const body = {
    status: 'PROVEN', choice,
    text: document.getElementById('tx' + cid).value || null,
    reviewer: document.getElementById('rv' + cid).value || null,
  };
  try { await j(`/api/conflicts/${cid}/resolve`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)});
    load(); } catch (e) { alert('فشل الحسم: ' + e.message); }
}
load();
</script></body></html>"""


def create_app(db_path: str | Path) -> FastAPI:
    """ابنِ التطبيق فوق قاعدة موجودة — قاعدة مفقودة رفض فوري (Fail-Closed)."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"قاعدة التوليف غير موجودة: {path}")
    app = FastAPI(title="orthok review", docs_url=None, redoc_url=None)
    holder: dict = {}

    def get_conn():
        if "conn" not in holder:
            holder["conn"] = sstore.connect(path)
        return holder["conn"]

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _PAGE

    @app.get("/api/summary")
    def summary() -> dict:
        conn = get_conn()
        conflicts = {"BLOCKED": 0, "UNPROVEN": 0, "PROVEN": 0}
        for r in conn.execute("SELECT status, COUNT(*) n FROM conflicts GROUP BY status"):
            conflicts[r["status"]] = r["n"]
        deltas = conn.execute("SELECT COUNT(*) n FROM deltas").fetchone()["n"]
        spine = sstore.fetch_spine_source(conn)
        return {
            "conflicts": conflicts, "deltas": deltas,
            "spine_book": spine[0] if spine else None,
            "chapter": spine[1] if spine else None,
        }

    @app.get("/api/conflicts")
    def conflicts(status: str | None = Query(default=None)) -> list[dict]:
        if status is not None and status not in sstore.RESOLVE_STATUSES:
            raise HTTPException(400, f"status غير قانوني: {status!r}")
        return sstore.fetch_conflicts(get_conn(), status)

    @app.post("/api/conflicts/{conflict_id}/resolve")
    def resolve(conflict_id: int, body: ResolveBody) -> dict:
        try:
            return sstore.resolve_conflict(
                get_conn(), conflict_id,
                status=body.status, choice=body.choice,
                text=body.text, reviewer=body.reviewer,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/deltas")
    def deltas() -> list[dict]:
        return sstore.fetch_deltas(get_conn())

    @app.get("/api/export/unified.md", response_class=PlainTextResponse)
    def export_unified() -> str:
        conn = get_conn()
        spine = sstore.fetch_spine_source(conn)
        if spine is None:
            raise HTTPException(404, "لا عمود فقري في هذه القاعدة")
        return build_unified_markdown(conn, spine[0], spine[1])

    return app


def run_server(db_path: str | Path, port: int = 8000) -> None:
    """شغّل الخادم — 127.0.0.1 حصرياً، لا واجهة شبكة أبداً."""
    import uvicorn

    uvicorn.run(create_app(db_path), host="127.0.0.1", port=port, log_level="warning")
