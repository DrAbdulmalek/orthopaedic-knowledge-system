"""واجهة سطر الأوامر — orthok <command>.

كل الأوامر محلية بالكامل؛ لا يوجد أي أمر يلمس الشبكة أصلاً.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULTS


def _cmd_pilot(args) -> int:
    """شغّل الـ pilot الرسمي (فصل كسور عنق الفخذ ببيانات وهمية)."""
    from pilot.run_pilot import run_official_pilot

    summary = run_official_pilot(Path(args.out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_init_db(args) -> int:
    from .storage import connect

    connect(args.knowledge_db).close()
    from .storage.corrections import CorrectionsStore

    CorrectionsStore(args.corrections_db).close()
    print(f"knowledge: {args.knowledge_db}\ncorrections: {args.corrections_db}")
    return 0


def _cmd_align(args) -> int:
    from dataclasses import replace

    from .alignment.lexicon import BilingualLexicon, set_default_lexicon
    from .config import DEFAULTS
    from .ingestion import blocks_from_jsonl, blocks_from_text
    from .pipeline import run_pipeline

    if args.lexicon:
        # مسرد المستخدم يصبح أساس المطابقة الثنائية في هذه الجلسة
        set_default_lexicon(BilingualLexicon.from_csv(args.lexicon))

    settings = replace(
        DEFAULTS,
        terminology=replace(DEFAULTS.terminology, syrian_lexicon_csv=args.syrian_lexicon),
        local_onnx_model_dir=args.model_dir,
    )
    loader = blocks_from_jsonl if args.format == "jsonl" else blocks_from_text
    src_doc = loader(Path(args.src).read_text(encoding="utf-8"), args.book_code, args.chapter, "en")
    tgt_doc = loader(Path(args.tgt).read_text(encoding="utf-8"), args.book_code, args.chapter, "ar")
    summary = run_pipeline(src_doc, tgt_doc, args.knowledge_db, args.corrections_db, settings)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_ingest_pdf(args) -> int:
    from .ingestion.pdf_extract import export_blocks_jsonl, extract_pdf_blocks

    doc = extract_pdf_blocks(args.pdf, args.book_code, args.chapter, args.lang)
    count = export_blocks_jsonl(doc, args.out)
    print(f"{count} كتلة → {args.out}")
    return 0


def _load_en_doc(path: str, book_code: str, chapter: str, fmt: str):
    from .ingestion import blocks_from_jsonl, blocks_from_text

    # jsonl: المحمّل يقرأ الملف بنفسه (سطور تالفة تُجمع لاحقاً كـ BLOCKED)؛
    # text: المحتوى نص خام مفصول بأسطر فارغة — تمرير النص للمحمّل خطأ
    # كان يجعل --format jsonl عبر الـ CLI يفشل بـ FileNotFoundError.
    if fmt == "jsonl":
        return blocks_from_jsonl(path, book_code, chapter, "en")
    return blocks_from_text(Path(path).read_text(encoding="utf-8"), book_code, chapter, "en")


def _cmd_synthesize(args) -> int:
    from .synthesis import run_synthesis

    spine = (args.spine_code, _load_en_doc(args.spine, args.spine_code, args.chapter, args.format))
    others = [
        (code, _load_en_doc(path, code, args.chapter, args.format))
        for path, code in args.other
    ]
    result, outputs = run_synthesis(
        spine, others, args.db,
        model_dir=args.model_dir,
        dup_threshold=args.dup_threshold,
        link_floor=args.link_floor,
        out_dir=args.out,
    )
    print(json.dumps({"pipeline": result.to_dict(), "outputs": outputs},
                     ensure_ascii=False, indent=2))
    return 0


def _cmd_synthesize_demo(args) -> int:
    from pilot.run_synthesis_demo import run_official_synthesis_demo

    summary = run_official_synthesis_demo(Path(args.out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_review(args) -> int:
    from .review.app import run_server

    if not Path(args.db).exists():
        print(f"قاعدة التوليف غير موجودة: {args.db} — شغّل synthesize أولاً", file=sys.stderr)
        return 1
    if args.knowledge_db and not Path(args.knowledge_db).exists():
        print(f"القاعدة المعرفية غير موجودة: {args.knowledge_db}", file=sys.stderr)
        return 1
    print(f"واجهة المراجعة المحلية: http://127.0.0.1:{args.port} (Ctrl+C للإيقاف)")
    run_server(args.db, args.port, args.knowledge_db, args.corrections_db)
    return 0


def _cmd_review_export(args) -> int:
    from .synthesis import store as sstore
    from .synthesis.report import build_unified_markdown

    if not Path(args.db).exists():
        print(f"قاعدة التوليف غير موجودة: {args.db}", file=sys.stderr)
        return 1
    conn = sstore.connect(args.db)
    try:
        spine = sstore.fetch_spine_source(conn)
        if spine is None:
            print("لا عمود فقري في هذه القاعدة", file=sys.stderr)
            return 1
        md = build_unified_markdown(conn, spine[0], spine[1])
    finally:
        conn.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"الفصل الموحد (معتمداً قرارات المراجعين) → {out}")
    return 0


def _cmd_export(args) -> int:
    from .storage import connect
    from .integration import export_csv, export_tbx, export_tmx, export_xliff, export_xlsx

    conn = connect(args.knowledge_db)
    out = Path(args.out)
    made: list[str] = []
    for fmt in [f.strip().lower() for f in args.format.split(",")]:
        if fmt == "tmx":
            made.append(str(export_tmx(conn, out / "memory.tmx", min_confidence=args.min_confidence)))
        elif fmt == "tbx":
            made.append(str(export_tbx(conn, out / "terminology.tbx")))
        elif fmt == "xliff":
            made.append(str(export_xliff(conn, out / "review.xliff")))
        elif fmt == "csv":
            made += [str(p) for p in export_csv(conn, out)]
        elif fmt == "xlsx":
            made.append(str(export_xlsx(conn, out / "alignments.xlsx")))
        else:
            print(f"صيغة غير معروفة: {fmt}", file=sys.stderr)
    conn.close()
    print("\n".join(made))
    return 0


def _cmd_report(args) -> int:
    from .storage import connect
    from .qa import export_report

    conn = connect(args.knowledge_db)
    print(export_report(conn, args.out))
    conn.close()
    return 0


def _cmd_stats(args) -> int:
    from .storage import connect

    conn = connect(args.knowledge_db)
    stats = {
        t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        for t in ("segments", "alignments", "concepts", "terms", "qa_flags", "qa_blocks")
    }
    stats["status"] = {
        s: conn.execute(f"SELECT COUNT(*) c FROM alignments WHERE status='{s}'").fetchone()["c"]
        for s in ("PROVEN", "UNPROVEN", "BLOCKED")
    }
    conn.close()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _cmd_set_status(args) -> int:
    from .storage import connect, set_status

    conn = connect(args.knowledge_db)
    set_status(conn, args.entity, args.id, args.status.upper(), reviewer=args.reviewer)
    conn.close()
    print(f"{args.entity} {args.id} → {args.status.upper()}")
    return 0


def _cmd_corrections(args) -> int:
    from .storage.corrections import CorrectionsStore

    store = CorrectionsStore(args.corrections_db)
    if args.record:
        entity, key, field, new_value = args.record
        cid = store.record(entity, key, field, new_value, reviewer=args.reviewer)
        print(f"correction #{cid} recorded")
    else:
        for rule in store.all_rules():
            print(rule)
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="orthok",
        description="منظومة المعرفة والترجمة العظمية — Local-First، بلا سحابة",
    )
    p.add_argument("--version", action="version", version=f"orthok {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("pilot", help="خط الإنتاج الكامل على فصل وهمي (كسور عنق الفخذ)")
    sp.add_argument("--out", default="out/pilot")
    sp.set_defaults(func=_cmd_pilot)

    sp = sub.add_parser("init-db", help="إنشاء القاعدتين بالمخططات")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--corrections-db", default=DEFAULTS.storage.corrections_db)
    sp.set_defaults(func=_cmd_init_db)

    sp = sub.add_parser("align", help="محاذاة ملفين (نص خام أو JSONL من ingest-pdf)")
    sp.add_argument("--src", required=True)
    sp.add_argument("--tgt", required=True)
    sp.add_argument("--book-code", required=True)
    sp.add_argument("--chapter", required=True, help="مثال: CH04")
    sp.add_argument("--format", choices=["text", "jsonl"], default="text",
                    help="text: فقرات مفصولة بسطر فارغ | jsonl: كتل من ingest-pdf")
    sp.add_argument("--lexicon", default=None, help="مسرد ثنائي CSV (en,ar) يصبح أساس المطابقة")
    sp.add_argument("--syrian-lexicon", default=None, help="CSV بعمود واحد: مصطلحات سورية معتمدة إضافية")
    sp.add_argument("--model-dir", default=None, help="مجلد نموذج ONNX محلي (model.onnx + tokenizer.json)")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--corrections-db", default=DEFAULTS.storage.corrections_db)
    sp.set_defaults(func=_cmd_align)

    sp = sub.add_parser("ingest-pdf", help="استخرج كتلاً JSONL من PDF محلي (يتطلب PyMuPDF: pip install -e '.[pdf]')")
    sp.add_argument("--pdf", required=True)
    sp.add_argument("--book-code", required=True)
    sp.add_argument("--chapter", required=True, help="مثال: CH04")
    sp.add_argument("--lang", choices=["en", "ar"], required=True)
    sp.add_argument("--out", required=True, help="ملف JSONL الناتج (لأمر align --format jsonl)")
    sp.set_defaults(func=_cmd_ingest_pdf)

    sp = sub.add_parser("synthesize",
                        help="دمج كتب إنجليزية: عمود فقري + إضافات + جدول تعارضات (المرحلة 2)")
    sp.add_argument("--spine", required=True, help="ملف العمود الفقري (JSONL من ingest-pdf أو نص خام)")
    sp.add_argument("--spine-code", required=True, help="رمز كتاب العمود الفقري، مثال: MILLER")
    sp.add_argument("--other", action="append", nargs=2, metavar=("PATH", "CODE"), required=True,
                    help="كتاب آخر: مسار + رمز — كرر الخيار لكل كتاب (حتى 4 كتب أخرى)")
    sp.add_argument("--chapter", required=True, help="مثال: CH04")
    sp.add_argument("--format", choices=["jsonl", "text"], default="jsonl")
    sp.add_argument("--model-dir", default=None, help="نموذج ONNX محلي للتشابه الدلالي (اختياري)")
    sp.add_argument("--dup-threshold", type=float, default=0.8)
    sp.add_argument("--link-floor", type=float, default=0.55)
    sp.add_argument("--db", default="out/synthesis/synthesis.db")
    sp.add_argument("--out", default="out/synthesis", help="مجلد المخرجات: unified_chapter.md + synthesis_report.html")
    sp.set_defaults(func=_cmd_synthesize)

    sp = sub.add_parser("synthesize-demo", help="دمج ثلاثي وهمي رسمي (MILLER+ROCKWOOD+APLEY)")
    sp.add_argument("--out", default="out/synth_demo")
    sp.set_defaults(func=_cmd_synthesize_demo)

    sp = sub.add_parser("review",
                        help="واجهة المراجعة البشرية المحلية لحسم التعارضات (127.0.0.1 فقط)")
    sp.add_argument("--db", default="out/synthesis/synthesis.db")
    sp.add_argument("--knowledge-db", default=None,
                    help="قاعدة المصطلحات (افتراضياً knowledge.db بجوار --db)")
    sp.add_argument("--corrections-db", default=None,
                    help="سجل القرارات القانوني (افتراضياً corrections.db بجوار --db)")
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=_cmd_review)

    sp = sub.add_parser("review-export",
                        help="أعد توليد الفصل الموحد معتمداً قرارات المراجعين المحسومة")
    sp.add_argument("--db", default="out/synthesis/synthesis.db")
    sp.add_argument("--out", default="out/synthesis/unified_chapter.md")
    sp.set_defaults(func=_cmd_review_export)

    sp = sub.add_parser("export", help="تصدير: tmx,tbx,xliff,csv,xlsx")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--format", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--min-confidence", type=float, default=0.3)
    sp.set_defaults(func=_cmd_export)

    sp = sub.add_parser("report", help="تقرير QA بواجهة عربية RTL")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=_cmd_report)

    sp = sub.add_parser("stats", help="عدادات القاعدة وحالاتها")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.set_defaults(func=_cmd_stats)

    sp = sub.add_parser("set-status", help="قرار المراجع: PROVEN/UNPROVEN/BLOCKED")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--entity", choices=["alignment", "term", "concept"], required=True)
    sp.add_argument("--id", required=True)
    sp.add_argument("--status", choices=["proven", "unproven", "blocked"], required=True)
    sp.add_argument("--reviewer", default=None)
    sp.set_defaults(func=_cmd_set_status)

    sp = sub.add_parser("corrections", help="قواعد التصحيح: عرض أو تسجيل (--record entity key field value)")
    sp.add_argument("--corrections-db", default=DEFAULTS.storage.corrections_db)
    sp.add_argument("--record", nargs=4, metavar=("ENTITY", "KEY", "FIELD", "VALUE"), default=None)
    sp.add_argument("--reviewer", default=None)
    sp.set_defaults(func=_cmd_corrections)

    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
