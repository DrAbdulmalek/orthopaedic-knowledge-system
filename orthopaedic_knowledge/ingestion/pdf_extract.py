"""استخراج كتل نصية من PDF محلي عبر PyMuPDF (fitz) — بلا شبكة إطلاقاً.

هذه هي الوحدة التي يفترضها extra ``[pdf]`` في pyproject.toml:
``pip install -e ".[pdf]"`` ثم:

    orthok ingest-pdf --pdf chapter04.pdf --book-code ORTHO101 --chapter CH04 --lang en --out blocks.jsonl

قواعد Fail-Closed:
* غياب حزمة PyMuPDF → استثناء صريح بإرشاد التثبيت (لا تخمين ولا سقوط صامت).
* ملف PDF تالف → استثناء fitz يمر كما هو (رفض العملية، لا محاولة إنقاذ جزئية).
* كتل الصور (b[6]==1) تُتجاهل؛ التعليقات (Fig./Table/شكل/جدول) تُوسم caption.
"""

from __future__ import annotations

import json
from pathlib import Path

from .layout_parser import _CAPTION_RE
from .models import ChapterDocument, TextBlock


def parse_pages(spec: str | None) -> frozenset[int] | None:
    """حلّ نطاق الصفحات «110-140» أو «110,112,115-118» (عدّاد يبدأ من 1).

    None يعني كل الصفحات. أي نطاق تالف رفض صريح — لا تخمين.
    """
    if spec is None or not spec.strip():
        return None
    pages: set[int] = set()
    for token in spec.replace("،", ",").split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_s, _, end_s = token.partition("-")
            try:
                start, end = int(start_s), int(end_s)
            except ValueError as exc:
                raise ValueError(f"نطاق صفحات تالف: {token!r}") from exc
            if start < 1 or end < start:
                raise ValueError(f"نطاق صفحات غير منطقي: {token!r} (العدّاد يبدأ من 1)")
            pages.update(range(start, end + 1))
        else:
            try:
                n = int(token)
            except ValueError as exc:
                raise ValueError(f"رقم صفحة تالف: {token!r}") from exc
            if n < 1:
                raise ValueError(f"رقم صفحة غير منطقي: {token!r} (العدّاد يبدأ من 1)")
            pages.add(n)
    if not pages:
        raise ValueError(f"نطاق صفحات فارغ: {spec!r}")
    return frozenset(pages)


def extract_pdf_blocks(
    pdf_path: str | Path,
    book_code: str,
    chapter: str,
    lang: str,
    pages: str | None = None,
) -> ChapterDocument:
    """افتح PDF محلياً واستخرج كتلاً واعيةاة للتخطيط (صفحة + bbox + نوع).

    pages: نطاق اختياري «110-140» لقصّ فصل من كتاب كامل — أرقام الصفحات في
    الإثبات تبقى أرقام الملف الأصلي (لا إعادة ترقيم).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF غير مثبت — ثبّته محلياً أولاً: pip install -e '.[pdf]' "
            "(الوضع Local-First يمنع أي تنزيل وقت التشغيل)"
        ) from exc

    wanted = parse_pages(pages)
    doc = ChapterDocument(book_code=book_code, chapter=chapter, lang=lang)
    with fitz.open(str(pdf_path)) as pdf:  # ملف تالف → استثناء صريح (رفض، لا تخمين)
        for page in pdf:
            if wanted is not None and (page.number + 1) not in wanted:
                continue
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
                if len(block) > 6 and block[6] == 1:  # كتلة صورة بلا نص
                    continue
                text = (text or "").strip()
                if not text:
                    continue
                doc.blocks.append(
                    TextBlock(
                        page=page.number + 1,
                        text=text,
                        kind="caption" if _CAPTION_RE.match(text) else "body",
                        bbox=(float(x0), float(y0), float(x1), float(y1)),
                    )
                )
    return doc


def export_blocks_jsonl(doc: ChapterDocument, out_path: str | Path) -> int:
    """اكتب الكتل JSONL (UTF-8)؛ أي كتلة تالفة توقف التصدير — لا ملف نصفي متسخ."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as fh:
        for block in doc.blocks:
            block.validate()  # Fail-Closed — الرفض قبل الكتابة
            fh.write(json.dumps({
                "page": block.page,
                "text": block.text,
                "kind": block.kind,
                "bbox": list(block.bbox) if block.bbox else None,
                "section_path": block.section_path,
            }, ensure_ascii=False) + "\n")
            count += 1
    return count
