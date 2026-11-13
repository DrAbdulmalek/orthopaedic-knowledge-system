"""تخزين محلي: القاعدة المعرفية + قاعدة التصحيحات المنفصلة."""

from .corrections import CorrectionsStore
from .db import add_alignment, add_document, add_flag, add_segment, connect, fetch_pairs, set_status

__all__ = [
    "connect", "add_document", "add_segment", "add_alignment", "add_flag",
    "set_status", "fetch_pairs", "CorrectionsStore",
]
