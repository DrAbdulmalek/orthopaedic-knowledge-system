"""تجميع كتل المستندات في وحدات محتوى (Unit) بمعرفات إثبات.

الكتلة الواعية للتخطيط من ingest-pdf هي وحدة واحدة (فقرة/تعليق/خلية)؛
الكتل التالفة تُرفض وتُسجَّل BLOCKED — فشل آمن على مستوى العنصر.
"""

from __future__ import annotations

from ..ingestion import ChapterDocument
from .models import Unit


def build_units(doc: ChapterDocument, book_code: str, chapter: str) -> tuple[list[Unit], list[str]]:
    """حوّل مستند فصل إلى وحدات مرقمة + قائمة أسباب الرفض (BLOCKED)."""
    units: list[Unit] = []
    blocked: list[str] = []
    valid_blocks, rejected = doc.valid_blocks()
    for exc in rejected:
        blocked.append(f"ingestion: {exc}")
    seq = 0
    for block in valid_blocks:
        seq += 1
        try:
            unit = Unit(
                book_code=book_code,
                chapter=chapter,
                seq=seq,
                kind=block.kind,
                page_first=block.page,
                page_last=block.page,
                text=block.text.strip(),
                section_path=block.section_path,
            )
            unit.validate()
        except ValueError as exc:
            blocked.append(f"unit {seq}: {exc}")
            seq -= 1  # الرقم يعاد استعماله — لا فجوات في التسلسل
            continue
        units.append(unit)
    return units, blocked
