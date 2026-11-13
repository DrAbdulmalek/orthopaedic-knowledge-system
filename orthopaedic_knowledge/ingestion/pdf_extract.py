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


def extract_pdf_blocks(pdf_path: str | Path, book_code: str, chapter: str, lang: str) -> ChapterDocument:
    """افتح PDF محلياً واستخرج كتلاً واعيةاة للتخطيط (صفحة + bbox + نوع)."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF غير مثبت — ثبّته محلياً أولاً: pip install -e '.[pdf]' "
            "(الوضع Local-First يمنع أي تنزيل وقت التشغيل)"
        ) from exc

    doc = ChapterDocument(book_code=book_code, chapter=chapter, lang=lang)
    with fitz.open(str(pdf_path)) as pdf:  # ملف تالف → استثناء صريح (رفض، لا تخمين)
        for page in pdf:
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
