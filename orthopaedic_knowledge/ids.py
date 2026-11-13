"""معرفات الإثبات (Provenance IDs).

التنسيق الإلزامي لكل جملة: [BOOK_CODE]_[CHAPTER]_[PAGE]_[SENTENCE_ID]
مثال: CAMPBELL_CH04_P112_S005

أي معرف لا يطابق النمط يُرفض (Fail-Closed) ولا يُخمَّن إطلاقاً.
"""

from __future__ import annotations

import re

SENTENCE_ID_RE = re.compile(
    r"^(?P<book>[A-Z0-9]{2,24})_(?P<chapter>CH\d{1,4})_P(?P<page>\d{1,5})_S(?P<sent>\d{1,5})$"
)


class InvalidIdError(ValueError):
    """معرف لا يطابق مخطط الإثبات — العملية تُرفض."""


def make_sentence_id(book_code: str, chapter: str, page: int, sent_no: int) -> str:
    """ابنِ معرف جملة متوافقاً مع المخطط، مع رفض المدخلات المشوهة."""
    if not re.fullmatch(r"[A-Z0-9]{2,24}", book_code or ""):
        raise InvalidIdError(f"book_code غير صالح: {book_code!r}")
    if not re.fullmatch(r"CH\d{1,4}", chapter or ""):
        raise InvalidIdError(f"chapter غير صالح: {chapter!r} (النمط CH##)")
    if not (isinstance(page, int) and page > 0):
        raise InvalidIdError(f"page يجب أن يكون عدداً موجباً: {page!r}")
    if not (isinstance(sent_no, int) and sent_no > 0):
        raise InvalidIdError(f"sent_no يجب أن يكون عدداً موجباً: {sent_no!r}")
    return f"{book_code}_{chapter}_P{page:03d}_S{sent_no:03d}"


def parse_sentence_id(sentence_id: str) -> dict | None:
    """فكك معرف جملة؛ يعيد None إن كان مشوهاً أو صفحة/جملة صفرية (لا تخمين)."""
    m = SENTENCE_ID_RE.match(sentence_id or "")
    if not m:
        return None
    page, sent = int(m.group("page")), int(m.group("sent"))
    if page <= 0 or sent <= 0:
        return None
    return {
        "book": m.group("book"),
        "chapter": m.group("chapter"),
        "page": page,
        "sent": sent,
    }


def make_concept_id(sequence: int) -> str:
    """C-000001 …"""
    if sequence < 1:
        raise InvalidIdError(f"sequence غير صالح: {sequence!r}")
    return f"C-{sequence:06d}"


def make_alignment_ref(alignment_id: int) -> str:
    """A-000012 — يستخدم في source/terms وprovenance."""
    if alignment_id < 1:
        raise InvalidIdError(f"alignment_id غير صالح: {alignment_id!r}")
    return f"A-{alignment_id:06d}"


def parse_alignment_ref(ref: str) -> int | None:
    m = re.fullmatch(r"A-(\d{6,})", ref or "")
    return int(m.group(1)) if m else None
