"""الاستيعاب: نماذج كتل واعية للتخطيط + محلل + مدقق Fail-Closed."""

from .layout_parser import blocks_from_jsonl, blocks_from_text, guess_table_cells
from .models import ChapterDocument, InvalidBlockError, TextBlock

__all__ = [
    "ChapterDocument",
    "TextBlock",
    "InvalidBlockError",
    "blocks_from_jsonl",
    "blocks_from_text",
    "guess_table_cells",
]
