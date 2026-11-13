"""نماذج الاستيعاب — Block-based document model مع تحقق صارم (Fail-Closed)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..fail_closed import BlockedItemError


class InvalidBlockError(BlockedItemError):
    """كتلة نص تالفة/ناقصة — تُرفض ولا تُخمَّن."""


@dataclass(frozen=True)
class TextBlock:
    """كتلة نص واعية للتخطيط: موقع دقيق داخل الصفحة + نوع الكتلة."""

    page: int
    text: str
    kind: str = "body"                     # body | caption | table_cell | footnote
    bbox: tuple[float, float, float, float] | None = None
    section_path: str | None = None        # مثال: "Ch04/Femoral Neck/Anatomy"

    def validate(self) -> None:
        if not isinstance(self.page, int) or self.page <= 0:
            raise InvalidBlockError(f"page غير صالح: {self.page!r}")
        if not isinstance(self.text, str) or not self.text.strip():
            raise InvalidBlockError("text فارغ أو ليس نصاً")
        if self.kind not in {"body", "caption", "table_cell", "footnote"}:
            raise InvalidBlockError(f"kind غير معروف: {self.kind!r}")
        if self.bbox is not None and len(self.bbox) != 4:
            raise InvalidBlockError(f"bbox يجب أن يكون (x0,y0,x1,y1): {self.bbox!r}")


@dataclass
class ChapterDocument:
    """مستند فصل بلغة واحدة: كود الكتاب + الفصل + الكتل المرتبة."""

    book_code: str
    chapter: str                           # CH04
    lang: str                              # en | ar
    blocks: list[TextBlock] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.book_code or not self.book_code.isupper():
            raise InvalidBlockError(f"book_code مطلوب بحروف كبيرة: {self.book_code!r}")
        if self.lang not in {"en", "ar"}:
            raise InvalidBlockError(f"lang غير مدعوم: {self.lang!r}")

    def valid_blocks(self) -> tuple[list[TextBlock], list[BlockedItemError]]:
        """افصل الصالح عن الرفض — الفشل الآمن: الرفض يُعاد للمسجل، لا تخمين."""
        ok, rejected = [], []
        for b in self.blocks:
            try:
                b.validate()
                ok.append(b)
            except InvalidBlockError as exc:
                rejected.append(exc)
        return ok, rejected
