"""خط الإنتاج المركزي: استيعاب → تقطيع → محاذاة → مصطلحات → QA.

هذا هو التنظيم الوحيد لخط الإنتاج؛ الـ CLI والـ pilot كلاهما يستدعيه.
كل مرحلة Fail-Closed على مستوى العنصر: الرفض يُسجَّل BLOCKED والبقية تكمل.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import __version__
from .alignment import align, flag_issues, make_sim_fn, normalize_arabic
from .alignment.segmenter import segment_block
from .alignment.similarity import tokenize
from .config import Settings, DEFAULTS
from .fail_closed import BlockedItemError, block_item, fail_closed
from .ids import make_sentence_id, parse_sentence_id
from .ingestion import ChapterDocument
from .storage import CorrectionsStore, add_alignment, add_document, add_flag, add_segment, connect
from .terminology import extract_terms, store_all
from .qa import detect_term_conflicts


def _store_doc_sentences(
    conn: sqlite3.Connection, doc: ChapterDocument, doc_id: int
) -> tuple[list[str], list[str], list[str]]:
    """خزّن جمل المستند بمعرفات provenance؛ الكتل التالفة → BLOCKED (فشل آمن)."""
    ids: list[str] = []
    texts: list[str] = []
    blocked: list[str] = []
    sent_no = 0
    valid_blocks, rejected = doc.valid_blocks()
    for exc in rejected:
        block_item(conn, "block", f"{doc.book_code}_{doc.chapter}", "ingestion", str(exc))
        blocked.append(str(exc))
    for block in valid_blocks:
        with fail_closed(conn, "block", f"{doc.book_code}_{doc.chapter}_p{block.page}", "segmentation"):
            for s in segment_block(block.text, doc.lang):
                sent_no += 1
                sid = make_sentence_id(doc.book_code, doc.chapter, block.page, sent_no)
                parsed = parse_sentence_id(sid)
                if parsed is None:  # دفاعية — make_sentence_id لا ينتج معرفاً تالفاً
                    raise ValueError(f"معرف ناتج غير صالح: {sid}")
                norm = normalize_arabic(s) if doc.lang == "ar" else " ".join(tokenize(s))
                add_segment(
                    conn, sid, doc.lang, doc_id, s, norm, block.page,
                    para_index=block.page, sent_index=sent_no,
                    kind=block.kind, section_path=block.section_path,
                )
                ids.append(sid)
                texts.append(s)
    return ids, texts, blocked


def run_pipeline(
    src_doc: ChapterDocument,
    tgt_doc: ChapterDocument,
    knowledge_db: str | Path,
    corrections_db: str | Path,
    settings: Settings = DEFAULTS,
) -> dict:
    """شغّل الخط كاملاً وأعد ملخصاً قابلاً للطباعة."""
    if src_doc.lang != "en" or tgt_doc.lang != "ar":
        raise ValueError("المصدر يجب أن يكون en والهدف ar — الرفض قبل أي معالجة")
    corrections = CorrectionsStore(corrections_db)
    conn = connect(knowledge_db)
    try:
        doc_src = add_document(conn, src_doc.book_code, "en", src_doc.chapter)
        doc_tgt = add_document(conn, tgt_doc.book_code, "ar", tgt_doc.chapter)
        src_ids, src_texts, blocked_src = _store_doc_sentences(conn, src_doc, doc_src)
        tgt_ids, tgt_texts, blocked_tgt = _store_doc_sentences(conn, tgt_doc, doc_tgt)

        sim_fn = make_sim_fn(None, settings)
        result = align(
            src_texts, tgt_texts, sim_fn,
            max_join=settings.alignment.max_join,
            floor=settings.alignment.floor,
            skip_cost=settings.alignment.skip_cost,
            merge_discount=settings.alignment.merge_discount,
        )
        flags = flag_issues(result, low_confidence=settings.alignment.low_confidence)
        flags_by_index: dict[int, list[dict]] = {}
        for f in flags:
            flags_by_index.setdefault(f["alignment_index"], []).append(f)

        alignment_ids: list[int] = []
        for idx, a in enumerate(result.alignments, start=1):
            alignment_id = add_alignment(
                conn,
                [src_ids[i] for i in a.src_indexes],
                [tgt_ids[i] for i in a.tgt_indexes],
                a.align_type, a.confidence, a.breakdown,
                book_code=src_doc.book_code,
            )
            alignment_ids.append(alignment_id)
            for f in flags_by_index.get(idx, []):
                add_flag(conn, alignment_id, f["flag_type"], f["detail"])

        pairs = _pairs_from(conn)
        candidates = extract_terms(
            pairs,
            min_count=settings.terminology.min_term_count,
            top_k=settings.terminology.top_k,
        )
        concept_ids = store_all(
            conn, corrections, candidates,
            specialty="Orthopaedics", syrian_lexicon=None,
        )
        conflicts = detect_term_conflicts(conn)

        summary = {
            "version": __version__,
            "src_sentences": len(src_texts),
            "tgt_sentences": len(tgt_texts),
            "blocked_blocks": len(blocked_src) + len(blocked_tgt),
            "alignments": len(result.alignments),
            "type_counts": result.type_counts,
            "flags": len(flags),
            "term_candidates": len(candidates),
            "concepts": len(concept_ids),
            "conflicts_blocked": len(conflicts),
        }
        conn.commit()
        return summary
    finally:
        conn.close()
        corrections.close()


def _pairs_from(conn: sqlite3.Connection) -> list[dict]:
    import json

    pairs = []
    for row in conn.execute("SELECT * FROM alignments ORDER BY alignment_id"):
        def grab(ids: str, lang: str) -> list[dict]:
            res = []
            for sid in json.loads(ids):
                r = conn.execute(
                    "SELECT sentence_id, text FROM segments WHERE sentence_id=? AND lang=?",
                    (sid, lang),
                ).fetchone()
                if r:
                    res.append({"sentence_id": r["sentence_id"], "text": r["text"]})
            return res

        pairs.append({
            "alignment_id": row["alignment_id"], "align_type": row["align_type"],
            "confidence": row["confidence"], "status": row["status"],
            "src": grab(row["src_refs"], "en"), "tgt": grab(row["tgt_refs"], "ar"),
        })
    return pairs
