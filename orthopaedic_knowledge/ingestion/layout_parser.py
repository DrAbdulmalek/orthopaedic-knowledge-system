"""محلل نصوص واعٍ للتخطيط (Layout-Aware Parsing).

* من JSONL محلي (أثر PDF مستخرج بـ PyMuPDF اختيارياً): كتل نصية + bbox + صفحة.
* من نص خام: فقرات → كتل، والجداول تُعزل ككتل kind='table_cell' (لا تُحاذى
  كجمل — تُصدَّر كما هي مع الحفاظ على بنية الصف).
* كشف التعليقات (Fig./Table/شكل/جدول) ووسمها caption — تيار منفصل عن المتن.

قاعدة Fail-Closed: كتلة بلا صفحة أو بنص فارغ → InvalidBlockError (BLOCKED).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ChapterDocument, TextBlock

_CAPTION_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?\s*\d+|table\s*\d+|شكل\s*\d+|جدول\s*\d+)", re.IGNORECASE
)
_TABLE_HINT_RE = re.compile(r"\t|\s{3,}.*\s{3,}")


def blocks_from_jsonl(path: str | Path, book_code: str, chapter: str, lang: str) -> ChapterDocument:
    """اقرأ كتلاً من ملف JSONL محلي؛ أي سطر تالف يُجمَع ليُسجَّل BLOCKED لاحقاً."""
    doc = ChapterDocument(book_code=book_code, chapter=chapter, lang=lang)
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            bbox = raw.get("bbox")
            doc.blocks.append(
                TextBlock(
                    page=int(raw["page"]),
                    text=str(raw["text"]),
                    kind=str(raw.get("kind", "body")),
                    bbox=tuple(bbox) if bbox else None,
                    section_path=raw.get("section_path"),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            # يُخزَّن سبب الرفض داخل الكتلة نفسها كنص استثناء — يُسجل لاحقاً
            doc.blocks.append(TextBlock(page=-1, text=f"__INVALID_JSONL__: {exc}", kind="body"))
    return doc


def blocks_from_text(text: str, book_code: str, chapter: str, lang: str, first_page: int = 1) -> ChapterDocument:
    """حوّل نصاً خاماً (UTF-8) إلى فقرات → كتل body/caption."""
    doc = ChapterDocument(book_code=book_code, chapter=chapter, lang=lang)
    page = first_page
    for para in re.split(r"\n\s*\n", text):
        for line in (s.strip() for s in para.splitlines()):
            if not line:
                continue
            kind = "caption" if _CAPTION_RE.match(line) else "body"
            doc.blocks.append(TextBlock(page=page, text=line, kind=kind))
        page += 1  # فقرة مميزة بفارغ سطر → افتراض صفحة جديدة في النموذج الوهمي
    return doc


def guess_table_cells(text: str) -> bool:
    """إشارة تقريبية أن السطر جزء من جدول (تبويبات/أعمدة) — للوسم فقط."""
    return bool(_TABLE_HINT_RE.search(text))
