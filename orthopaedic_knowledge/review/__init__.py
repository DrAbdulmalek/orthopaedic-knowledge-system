"""واجهة المراجعة البشرية المحلية — حسم التعارضات (CONFLICT) يدوياً.

Local-First حرفياً: FastAPI مربوط على 127.0.0.1 فقط، بلا مصادقة لأنه
غير مكشوف للشبكة أصلاً، بلا خطوات بناء (HTML/JS مضمّن في ملف واحد)،
وكل حسم يُخزَّن في synthesis.db مع اسم المراجع وزمنه — تدقيق كامل.
"""

from .app import create_app, run_server

__all__ = ["create_app", "run_server"]
