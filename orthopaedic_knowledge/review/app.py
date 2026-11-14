"""تطبيق المراجعة المحلي — FastAPI + صفحة واحدة RTL مكتفية بذاتها.

المسارات:
* GET  /                              → صفحة المراجعة (HTML/JS مضمّن، بلا بناء)
* GET  /api/summary                   → بطاقات العدّادات
* GET  /api/conflicts?status=BLOCKED  → التعارضات بتفاصيلها ودرجاتها
* POST /api/conflicts/{id}/resolve    → الحسم البشري (spine/other/custom)
* GET  /api/terms?status=UNPROVEN     → مصطلحات بانتظار التثبيت (knowledge.db)
* POST /api/terms/{id}/approve        → تثبيت المصطلح PROVEN
* POST /api/terms/{id}/reject         → رفض الاقتراح (يبقى مرادفاً — موثّق)
* GET  /api/audit                     → سجل القرارات (rules + applications)
* GET  /api/export/unified.md         → الفصل الموحد معتمداً القرارات

مبدأ v0.3.1 (مستلهم من مراجعة DeepSeek): كل قرار بشري — تعارض أو مصطلح —
يمر عبر corrections.db (CorrectionsStore.record) لا يوجد مسار كتابة آخر،
فالسجل القانوني واحد وقابل لإعادة التطبيق والتتبع عكسياً.
"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..storage import CorrectionsStore, connect as knowledge_connect, set_status
from ..synthesis import store as sstore
from ..synthesis.report import build_unified_markdown


class ResolveBody(BaseModel):
    status: str = "PROVEN"
    choice: str
    text: str | None = None
    reviewer: str | None = Field(default=None, max_length=80)


class ReviewerBody(BaseModel):
    reviewer: str | None = Field(default=None, max_length=80)


_PAGE = """<!DOCTYPE html>
<html lang='ar' dir='rtl'><head><meta charset='utf-8'>
<title>orthok review — حسم التعارضات والمصطلحات</title>
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
.box { background:#fff; border:1px solid var(--line); border-radius:10px;
       padding:1rem 1.2rem; margin-bottom:1rem; }
.box table { width:100%; border-collapse:collapse; margin:.6rem 0; }
.box td, .box th { padding:.5rem .6rem; border-bottom:1px solid var(--line);
          vertical-align:top; font-size:.9rem; text-align:right; }
.badge { padding:.1rem .55rem; border-radius:999px; font-size:.72rem; font-weight:600; }
.b-numbers { background:#fff3d6; color:#946800; }
.b-classification { background:#e3efff; color:#1d4ed8; }
.b-recommendation { background:#fde3e3; color:#b3261e; }
.muted { color:var(--muted); font-size:.8rem; }
button { background:#1d4ed8; color:#fff; border:0; border-radius:8px;
         padding:.5rem 1.2rem; font-family:inherit; font-size:.9rem; cursor:pointer; }
button.gray { background:#5a6a7e; }
button:hover { filter:brightness(.9); }
textarea, input { font-family:inherit; width:100%; border:1px solid var(--line);
                  border-radius:8px; padding:.45rem; margin-top:.3rem; font-size:.9rem; }
label { font-size:.85rem; }
.row { display:flex; gap:1.4rem; flex-wrap:wrap; margin-top:.6rem; align-items:center; }
table.audit td, table.audit th { font-size:.8rem; }
</style></head><body>
<h1>⚖️ مركز المراجعة البشرية — <span id="chapter" class="muted"></span></h1>
<div class="cards" id="summary"></div>
<h2>التعارضات المعلّقة (BLOCKED)</h2>
<div id="conflicts">… جارٍ التحميل …</div>
<h2>المصطلحات بانتظار التثبيت (UNPROVEN → PROVEN)</h2>
<div id="terms">… جارٍ التحميل …</div>
<h2>سجل القرارات (corrections.db)</h2>
<div id="audit">… جارٍ التحميل …</div>
<p class="muted">كل قرار يُسجَّل باسمك وزمنه: الحسم في synthesis.db والقاعدة القانونية في corrections.db — لا حسم آلي أبداً.</p>
<script>
async function j(url, opt) { const r = await fetch(url, opt); if (!r.ok) throw new Error(await r.text()); return r.json(); }
function esc(t) { const d = document.createElement('div'); d.textContent = t ?? ''; return d.innerHTML; }
async function load() {
  const s = await j('/api/summary');
  document.getElementById('summary').innerHTML =
    Object.entries(s.conflicts).map(([k,v]) =>
      `<div class="card"><div class="num">${v}</div><div class="lbl">تعارضات ${k}</div></div>`).join('') +
    `<div class="card"><div class="num">${s.deltas}</div><div class="lbl">إضافات مدموجة</div></div>` +
    (s.unproven_terms != null ? `<div class="card"><div class="num">${s.unproven_terms}</div><div class="lbl">مصطلحات معلّقة</div></div>` : '');
  const items = await j('/api/conflicts?status=BLOCKED');
  document.getElementById('conflicts').innerHTML = items.length ? items.map(c => `
    <div class="box" id="c${c.conflict_id}">
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
    </div>`).join('') : '<p>✅ لا تعارضات معلّقة — كل شيء محسوم.</p>';
  const termsBox = document.getElementById('terms');
  try {
    const terms = await j('/api/terms?status=UNPROVEN');
    termsBox.innerHTML = terms.length ? terms.map(t => `
      <div class="box"><b>${esc(t.term_text)}</b>
        <span class="muted">${esc(t.term_norm)} · ${esc(t.concept_id)} · وزن سوري ${t.dialect_weight}</span>
        <div class="row">
          <input id="trv${t.term_id}" placeholder="اسم المراجع" style="max-width:14rem">
          <button onclick="term(${t.term_id}, 'approve')">تثبيت [PROVEN]</button>
          <button class="gray" onclick="term(${t.term_id}, 'reject')">رفض (يبقى مرادفاً)</button>
        </div></div>`).join('') : '<p>✅ لا مصطلحات معلّقة.</p>';
  } catch (e) { termsBox.innerHTML = '<p class="muted">لا قاعدة معرفية مرفقة — شغّل orthok review مع --knowledge-db.</p>'; }
  const audit = await j('/api/audit');
  document.getElementById('audit').innerHTML = audit.rules.length ? `
    <div class="box"><table class="audit">
      <tr><th>#</th><th>الكيان</th><th>المفتاح</th><th>الحقل</th><th>القيمة الجديدة</th><th>المراجع</th><th>الزمن</th></tr>
      ${audit.rules.slice(-15).reverse().map(r => `<tr><td>${r.correction_id}</td><td>${esc(r.entity)}</td>
        <td>${esc(r.entity_key)}</td><td>${esc(r.field)}</td><td>${esc((r.new_value||'').slice(0,80))}</td>
        <td>${esc(r.reviewer||'')}</td><td class="muted">${esc(r.created_at||'')}</td></tr>`).join('')}
    </table><p class="muted">التطبيقات الآلية المسجلة: ${audit.applications.length}</p></div>`
    : '<p class="muted">لا قرارات مسجلة بعد.</p>';
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
async function term(tid, action) {
  const body = { reviewer: document.getElementById('trv' + tid).value || null };
  try { await j(`/api/terms/${tid}/${action}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)});
    load(); } catch (e) { alert('فشل القرار: ' + e.message); }
}
load();
</script></body></html>"""


def _default_sibling(db_path: Path, name: str) -> Path:
    return db_path.parent / name


def create_app(
    db_path: str | Path,
    knowledge_db: str | Path | None = None,
    corrections_db: str | Path | None = None,
) -> FastAPI:
    """ابنِ التطبيق فوق قاعدة موجودة — قاعدة مفقودة رفض فوري (Fail-Closed).

    knowledge_db اختيارية: غيابها يعطّل شاشة المصطلحات برسالة واضحة (لا
    إنشاء صامت). corrections_db هو السجل القانوني — يُفتح دائماً.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"قاعدة التوليف غير موجودة: {path}")
    kpath = Path(knowledge_db) if knowledge_db else _default_sibling(path, "knowledge.db")
    kpath = kpath if kpath.exists() else None
    cpath = Path(corrections_db) if corrections_db else _default_sibling(path, "corrections.db")

    def legal_record():
        # السجل القانوني باتصال لكل طلب — نفس سبب اتصالات SQLite لكل
        # طلب أعلاه: مشاركة كائن عبر خيوط ASGI مختلفة خطأ بنيوي.
        return CorrectionsStore(cpath)

    app = FastAPI(title="orthok review", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _PAGE

    @app.get("/api/summary")
    def summary() -> dict:
        with closing(sstore.connect(path)) as conn:
            conflicts = {"BLOCKED": 0, "UNPROVEN": 0, "PROVEN": 0}
            for r in conn.execute("SELECT status, COUNT(*) n FROM conflicts GROUP BY status"):
                conflicts[r["status"]] = r["n"]
            deltas = conn.execute("SELECT COUNT(*) n FROM deltas").fetchone()["n"]
            spine = sstore.fetch_spine_source(conn)
        unproven = None
        if kpath is not None:
            with closing(knowledge_connect(kpath)) as kconn:
                unproven = kconn.execute(
                    "SELECT COUNT(*) n FROM terms WHERE lang='ar' AND role='preferred'"
                    " AND status='UNPROVEN'").fetchone()["n"]
        return {
            "conflicts": conflicts, "deltas": deltas,
            "spine_book": spine[0] if spine else None,
            "chapter": spine[1] if spine else None,
            "unproven_terms": unproven,
        }

    @app.get("/api/conflicts")
    def conflicts(status: str | None = Query(default=None)) -> list[dict]:
        if status is not None and status not in sstore.RESOLVE_STATUSES:
            raise HTTPException(400, f"status غير قانوني: {status!r}")
        with closing(sstore.connect(path)) as conn:
            return sstore.fetch_conflicts(conn, status)

    @app.post("/api/conflicts/{conflict_id}/resolve")
    def resolve(conflict_id: int, body: ResolveBody) -> dict:
        try:
            with closing(sstore.connect(path)) as conn:
                result = sstore.resolve_conflict(
                    conn, conflict_id,
                    status=body.status, choice=body.choice,
                    text=body.text, reviewer=body.reviewer,
                )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        # القاعدة القانونية: كل قرار بشري يسلك corrections.db — لا مسار آخر
        with closing(legal_record()) as corrections:
            corrections.record(
                "conflict", f"conflict:{conflict_id}", "resolution",
                json.dumps({k: result[k] for k in ("status", "choice", "text")},
                           ensure_ascii=False),
                match_rule="exact_id", reviewer=body.reviewer,
            )
        return result

    @app.get("/api/terms")
    def terms(status: str = Query(default="UNPROVEN")) -> list[dict]:
        if kpath is None:
            raise HTTPException(404, "لا قاعدة معرفية مرفقة (--knowledge-db)")
        if status not in {"PROVEN", "UNPROVEN", "BLOCKED"}:
            raise HTTPException(400, f"status غير قانوني: {status!r}")
        with closing(knowledge_connect(kpath)) as kconn:
            return [dict(r) for r in kconn.execute(
                """SELECT term_id, concept_id, term_text, term_norm, role,
                          dialect_weight, status
                   FROM terms WHERE lang='ar' AND role='preferred' AND status=?
                   ORDER BY term_id""", (status,))]

    @app.post("/api/terms/{term_id}/approve")
    def approve_term(term_id: int, body: ReviewerBody) -> dict:
        if kpath is None:
            raise HTTPException(404, "لا قاعدة معرفية مرفقة (--knowledge-db)")
        with closing(knowledge_connect(kpath)) as kconn:
            if kconn.execute("SELECT 1 FROM terms WHERE term_id=?",
                             (term_id,)).fetchone() is None:
                raise HTTPException(404, f"لا مصطلح برقم {term_id}")
            set_status(kconn, "term", term_id, "PROVEN", reviewer=body.reviewer)
            updated = dict(kconn.execute(
                "SELECT term_id, term_text, status, reviewer, reviewed_at FROM terms"
                " WHERE term_id=?", (term_id,)).fetchone())
        with closing(legal_record()) as corrections:
            corrections.record("term", f"term:{term_id}", "status", "PROVEN",
                               match_rule="exact_id", old_value="UNPROVEN",
                               reviewer=body.reviewer)
        return updated

    @app.post("/api/terms/{term_id}/reject")
    def reject_term(term_id: int, body: ReviewerBody) -> dict:
        if kpath is None:
            raise HTTPException(404, "لا قاعدة معرفية مرفقة (--knowledge-db)")
        with closing(knowledge_connect(kpath)) as kconn:
            if kconn.execute("SELECT 1 FROM terms WHERE term_id=?",
                             (term_id,)).fetchone() is None:
                raise HTTPException(404, f"لا مصطلح برقم {term_id}")
        # الرفض قرار بشري موثق أيضاً: المصطلح يبقى UNPROVEN (مرادفاً سياقياً)
        with closing(legal_record()) as corrections:
            corrections.record("term", f"term:{term_id}", "review_decision",
                               "keep_unproven", match_rule="exact_id",
                               reviewer=body.reviewer)
        return {"term_id": term_id, "status": "UNPROVEN", "decision": "keep_unproven"}

    @app.get("/api/audit")
    def audit() -> dict:
        with closing(legal_record()) as corrections:
            return {
                "rules": corrections.all_rules(),
                "applications": corrections.applications(),
            }

    @app.get("/api/deltas")
    def deltas() -> list[dict]:
        with closing(sstore.connect(path)) as conn:
            return sstore.fetch_deltas(conn)

    @app.get("/api/export/unified.md", response_class=PlainTextResponse)
    def export_unified() -> str:
        with closing(sstore.connect(path)) as conn:
            spine = sstore.fetch_spine_source(conn)
            if spine is None:
                raise HTTPException(404, "لا عمود فقري في هذه القاعدة")
            return build_unified_markdown(conn, spine[0], spine[1])

    return app


def run_server(
    db_path: str | Path,
    port: int = 8000,
    knowledge_db: str | Path | None = None,
    corrections_db: str | Path | None = None,
) -> None:
    """شغّل الخادم — 127.0.0.1 حصرياً، لا واجهة شبكة أبداً."""
    import uvicorn

    uvicorn.run(create_app(db_path, knowledge_db, corrections_db),
                host="127.0.0.1", port=port, log_level="warning")
