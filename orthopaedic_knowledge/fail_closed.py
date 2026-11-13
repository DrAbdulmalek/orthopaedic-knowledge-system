"""مبدأ الفشل الآمن (Fail-Closed).

القاعدة: أي خطأ في التنسيق أو البيانات يؤدي إلى رفض العملية وتسجيلها كـ
BLOCKED — وليس تخميناً أو تجاهلاً.

* ``BlockedItemError`` — استثناء عنصر واحد: يُعلَّم العنصر BLOCKED في القاعدة
  ثم يلتقطه خط الإنتاج ويكمل بقية العناصر (فشل آمن على مستوى العنصر).
* ``fail_closed`` — مدير سياق: يحيط بأي عملية قابلة للتعطل؛ عند الاستثناء
  يسجل العنصر BLOCKED (في qa_blocks) ثم يرفع BlockedItemError.
* الأخطاء البنيوية (تلف المخطط، قاعدة مقفلة) تُرفع كما هي وتُوقف الخط بالكامل.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator


class BlockedItemError(RuntimeError):
    """عنصر رُفض وتسجَّل BLOCKED — خط الإنتاج يلتقطه ويكمل."""


def _ensure_block_log(conn: sqlite3.Connection) -> None:
    """سجل الرفض داخل القاعدة الرئيسية (إن وُجد الجدول الأصلي أم لا)."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS qa_blocks (
               block_id     INTEGER PRIMARY KEY,
               entity       TEXT NOT NULL,
               entity_key   TEXT NOT NULL,
               stage        TEXT NOT NULL,
               reason       TEXT NOT NULL,
               detail_json  TEXT,
               created_at   TEXT DEFAULT (datetime('now'))
           )"""
    )
    conn.commit()


def block_item(
    conn: sqlite3.Connection,
    entity: str,
    entity_key: str,
    stage: str,
    reason: str,
    detail: dict | None = None,
) -> int:
    """سجّل رفض عنصر بشكل صريح — هذا هو الأثر الآمن الوحيد للفشل."""
    _ensure_block_log(conn)
    cur = conn.execute(
        """INSERT INTO qa_blocks (entity, entity_key, stage, reason, detail_json)
           VALUES (?, ?, ?, ?, ?)""",
        (entity, entity_key, stage, reason, json.dumps(detail or {}, ensure_ascii=False)),
    )
    conn.commit()
    return int(cur.lastrowid)


@contextmanager
def fail_closed(
    conn: sqlite3.Connection,
    entity: str,
    entity_key: str,
    stage: str,
) -> Iterator[None]:
    """حُطّ أي عملية بشكل آمن: عند أي استثناء يُسجَّل العنصر BLOCKED
    ثم يُرفع BlockedItemError ليتولى خط الإنتاج قرار المتابعة."""
    try:
        yield
    except BlockedItemError:
        raise  # مسجل مسبقاً — لا يُسجَّل مرتين
    except Exception as exc:  # noqa: BLE001 — التعمدي: نرفض ولا نخمّن
        block_item(conn, entity, entity_key, stage, str(exc), {"exc_type": type(exc).__name__})
        raise BlockedItemError(f"{stage}: {entity_key} → BLOCKED ({exc})") from exc
