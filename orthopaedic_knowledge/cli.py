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
    from .ingestion import blocks_from_text
    from .pipeline import run_pipeline

    src_doc = blocks_from_text(Path(args.src).read_text(encoding="utf-8"), args.book_code, args.chapter, "en")
    tgt_doc = blocks_from_text(Path(args.tgt).read_text(encoding="utf-8"), args.book_code, args.chapter, "ar")
    summary = run_pipeline(src_doc, tgt_doc, args.knowledge_db, args.corrections_db)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
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

    sp = sub.add_parser("align", help="محاذاة ملفين نصيين (فقرات مفصولة بسطر فارغ)")
    sp.add_argument("--src", required=True)
    sp.add_argument("--tgt", required=True)
    sp.add_argument("--book-code", required=True)
    sp.add_argument("--chapter", required=True, help="مثال: CH04")
    sp.add_argument("--knowledge-db", default=DEFAULTS.storage.knowledge_db)
    sp.add_argument("--corrections-db", default=DEFAULTS.storage.corrections_db)
    sp.set_defaults(func=_cmd_align)

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
