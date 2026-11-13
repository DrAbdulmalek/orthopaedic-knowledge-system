"""محرك التوليف — هدف المرحلة الثانية: دمج كتب عظمية إنجليزية للامتحان.

المنهج (كما تقرر في مراجعة 2026-11):
* كتاب واحد «عمود فقري» (Spine) — المرجع الأساسي الذي يدور حوله الدمج.
* كل وحدة من الكتب الأخرى تُربط بأقرب وحدة مناظرة في العمود الفقري
  (تشابه معجمي + متجهات ONNX محلية اختيارية، مشفَّرة دفعة واحدة).
* القرار الثلاثي: DUPLICATE (يُربط بالمرجع مع حفظ أرقام الصفحات فقط)،
  DELTA (معلومة جديدة تدخل المرجع الموحد بمعرف إثبات)،
  CONFLICT (توصية/رقم/تصنيف متعارض → جدول التعارضات لحسم بشري).

Fail-Closed: عمود فقري بلا وحدات = رفض بنيوي؛ وحدة تالفة = BLOCKED والبقية تكمل.
"""

from __future__ import annotations

from pathlib import Path

from ..ingestion import ChapterDocument
from ..alignment.embedder import build_embedder
from . import store
from .classifier import classify, detect_conflicts
from .en_similarity import SemanticScorer, lexical_similarity
from .models import Link, SynthesisResult, Unit
from .report import write_outputs
from .units import build_units


def run_synthesis(
    spine: tuple[str, ChapterDocument],
    others: list[tuple[str, ChapterDocument]],
    db_path: str | Path,
    *,
    model_dir: str | None = None,
    dup_threshold: float = 0.8,
    link_floor: float = 0.55,
    out_dir: str | Path | None = None,
) -> tuple[SynthesisResult, dict]:
    """شغّل الدمج كاملاً: وحدات → ربط → تصنيف → تخزين → تقارير."""
    spine_code, spine_doc = spine
    if spine_doc.lang != "en":
        raise ValueError("التوليف للمصادر الإنجليزية فقط — lang يجب أن يكون en")
    codes = [c for c, _ in others]
    if spine_code in codes or len(set(codes)) != len(codes):
        raise ValueError("رموز الكتب يجب أن تكون فريدة والعمود الفقري غير مكرر")

    conn = store.connect(db_path)
    result = SynthesisResult(
        spine_book=spine_code, other_books=codes, chapter=spine_doc.chapter
    )
    try:
        spine_id = store.add_source(conn, spine_code, "spine", spine_doc.chapter, origin="inline")
        spine_units, blocked = build_units(spine_doc, spine_code, spine_doc.chapter)
        for detail in blocked:
            store.block(conn, "units", spine_code, detail)
        result.blocked += len(blocked)
        if not any(u.kind == "body" for u in spine_units):
            raise ValueError(f"العمود الفقري {spine_code} بلا وحدات متن — لا توليف بلا عمود فقري")
        result.units[spine_code] = len(spine_units)
        for u in spine_units:
            store.add_unit(conn, spine_id, u)

        # تشفير دلالي دفعي واحد (إن توفر نموذج محلي) — لا إعادة تشفير لكل زوج
        scorer = SemanticScorer(model_dir) if model_dir else None
        spine_vecs = scorer.encode([u.text for u in spine_units]) if scorer else None

        for code, doc in others:
            if doc.lang != "en":
                raise ValueError(f"{code}: التوليف للمصادر الإنجليزية فقط")
            source_id = store.add_source(conn, code, "other", doc.chapter, origin="inline")
            units, blocked = build_units(doc, code, doc.chapter)
            for detail in blocked:
                store.block(conn, "units", code, detail)
            result.blocked += len(blocked)
            result.units[code] = len(units)
            for u in units:
                store.add_unit(conn, source_id, u)
            other_vecs = scorer.encode([u.text for u in units]) if scorer else None

            for idx, ou in enumerate(units):
                # المرشحون: نفس النوع فقط — الجداول مع الجداول والتعليقات مع التعليقات
                cands = [su for su in spine_units if su.kind == ou.kind]
                best: tuple[float, float, float | None, Unit | None] = (0.0, 0.0, None, None)
                for j, su in enumerate(cands):
                    lex = lexical_similarity(su.text, ou.text)
                    sem = None
                    if scorer:
                        sem = float(spine_vecs[j] @ other_vecs[idx])
                    comb = lex if sem is None else 0.45 * lex + 0.55 * sem
                    if comb > best[0]:
                        best = (comb, lex, sem, su)
                score, lex, sem, anchor = best

                if anchor is None:
                    facts = {"numbers": [], "systems": [], "missing_terms": []}
                    result.decisions["DELTA"] = result.decisions.get("DELTA", 0) + 1
                    result.deltas.append({"book": code, "unit_id": ou.unit_id, "anchor": None})
                    store.add_delta(conn, ou, None, facts,
                                    "لا وحدة مناظرة من نفس النوع في العمود الفقري")
                    continue

                decision, reason, facts = classify(
                    score, lex, sem, anchor.text, ou.text,
                    dup_threshold=dup_threshold, link_floor=link_floor,
                )
                store.add_link(conn, Link(
                    spine_unit=anchor.unit_id, other_unit=ou.unit_id, book_code=code,
                    score=round(score, 4), lexical=round(lex, 4),
                    semantic=round(sem, 4) if sem is not None else None,
                    decision=decision, reason=reason,
                ))
                if decision == "CONFLICT":
                    result.decisions["CONFLICT"] = result.decisions.get("CONFLICT", 0) + 1
                    for c in detect_conflicts(anchor.text, ou.text):
                        store.add_conflict(
                            conn, c["conflict_type"], anchor.unit_id, ou.unit_id,
                            code, c["spine_detail"], c["other_detail"],
                        )
                        result.conflicts.append({
                            "type": c["conflict_type"],
                            "spine": anchor.unit_id, "other": ou.unit_id, "book": code,
                        })
                elif decision == "DELTA":
                    result.decisions["DELTA"] = result.decisions.get("DELTA", 0) + 1
                    # دلتا تحت عتبة الربط = إثبات بلا مرساة (المرشح الأقرب موثّق
                    # في links بدرجته — لا نعلّق معلومة مستقلة على مرساة وهمية)
                    anchor_id = anchor.unit_id if score >= link_floor else None
                    result.deltas.append({"book": code, "unit_id": ou.unit_id, "anchor": anchor_id})
                    store.add_delta(conn, ou, anchor_id, facts, reason)
                else:
                    result.decisions["DUPLICATE"] = result.decisions.get("DUPLICATE", 0) + 1

        outputs: dict = {}
        if out_dir is not None:
            outputs = write_outputs(conn, result, out_dir)
        return result, outputs
    finally:
        conn.close()
