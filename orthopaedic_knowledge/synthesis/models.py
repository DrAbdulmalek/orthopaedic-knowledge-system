"""نماذج التوليف — وحدات المحتوى وقرارات الدمج.

كل وحدة تحمل معرف إثبات مستقلاً: [BOOK]_[CHAPTER]_P###_U### — نفس فلسفة
ids.py: معرف لا يطابق المخطط يُرفض ولا يُخمَّن.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

UNIT_ID_RE = re.compile(
    r"^(?P<book>[A-Z0-9]{2,24})_(?P<chapter>CH\d{1,4})_P(?P<page>\d{1,5})_U(?P<unit>\d{1,5})$"
)

DECISIONS = ("DUPLICATE", "DELTA", "CONFLICT", "UNLINKED")


class InvalidUnitIdError(ValueError):
    """معرف وحدة لا يطابق مخطط الإثبات — العملية تُرفض."""


@dataclass(frozen=True)
class Unit:
    """وحدة محتوى موحّدة (فقرة/تعليق/خلية جدول) من كتاب إنجليزي."""

    book_code: str
    chapter: str
    seq: int                 # الترتيب داخل الكتاب
    kind: str                # body / caption / table_cell / footnote
    page_first: int
    page_last: int
    text: str
    section_path: str | None = None

    @property
    def unit_id(self) -> str:
        return f"{self.book_code}_{self.chapter}_P{self.page_first:03d}_U{self.seq:03d}"

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Z0-9]{2,24}", self.book_code or ""):
            raise InvalidUnitIdError(f"book_code غير صالح: {self.book_code!r}")
        if not re.fullmatch(r"CH\d{1,4}", self.chapter or ""):
            raise InvalidUnitIdError(f"chapter غير صالح: {self.chapter!r}")
        if not (0 < self.page_first <= self.page_last):
            raise InvalidUnitIdError(
                f"مدى صفحات غير سليم: {self.page_first!r}..{self.page_last!r}")
        if self.seq < 1:
            raise InvalidUnitIdError(f"seq غير صالح: {self.seq!r}")
        if not self.text.strip():
            raise InvalidUnitIdError("وحدة بلا نص — تُرفض")
        if self.kind not in {"body", "caption", "table_cell", "footnote"}:
            raise InvalidUnitIdError(f"kind غير قانوني: {self.kind!r}")
        if not UNIT_ID_RE.match(self.unit_id):
            raise InvalidUnitIdError(f"معرف ناتج لا يطابق المخطط: {self.unit_id!r}")

    def provenance(self) -> str:
        pages = str(self.page_first) if self.page_first == self.page_last \
            else f"{self.page_first}-{self.page_last}"
        return f"{self.book_code} {self.chapter} ص.{pages}"


@dataclass(frozen=True)
class Link:
    """قرار ربط وحدة كتاب خارجي بوحدة العمود الفقري."""

    spine_unit: str
    other_unit: str
    book_code: str
    score: float
    lexical: float
    semantic: float | None
    decision: str
    reason: str

    def validate(self) -> None:
        if self.decision not in DECISIONS:
            raise InvalidUnitIdError(f"decision غير قانوني: {self.decision!r}")
        if not (0.0 <= self.score <= 1.0):
            raise InvalidUnitIdError(f"score خارج المدى: {self.score!r}")


@dataclass
class SynthesisResult:
    """ملخص تشغيل التوليف — قابل للطباعة والتخزين."""

    spine_book: str
    other_books: list[str]
    chapter: str
    units: dict[str, int] = field(default_factory=dict)      # book → عدد الوحدات
    decisions: dict[str, int] = field(default_factory=dict)  # DUPLICATE/DELTA/...
    conflicts: list[dict] = field(default_factory=list)
    deltas: list[dict] = field(default_factory=list)
    blocked: int = 0

    def to_dict(self) -> dict:
        return {
            "spine_book": self.spine_book,
            "other_books": self.other_books,
            "chapter": self.chapter,
            "units_per_book": dict(self.units),
            "decisions": dict(self.decisions),
            "conflicts": list(self.conflicts),      # التفاصيل كاملة — التعارض لا يُختزل بعدّاد
            "deltas": len(self.deltas),
            "blocked_units": self.blocked,
        }
