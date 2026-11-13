"""التوليف: دمج كتب عظمية إنجليزية (Spine + Deltas + جدول تعارضات).

واجهة الحزمة:
* ``run_synthesis`` — خط الدمج الكامل (وحدات → ربط → تصنيف → تخزين → تقارير).
* ``build_units`` — كتل المستندات → وحدات إثبات.
* ``classify`` / ``detect_conflicts`` — قرارات DUPLICATE/DELTA/CONFLICT.
* ``store`` — مخزن synthesis.db المنفصل.
"""

from . import store
from .classifier import classify, detect_conflicts
from .engine import run_synthesis
from .models import InvalidUnitIdError, Link, SynthesisResult, Unit
from .units import build_units

__all__ = [
    "run_synthesis", "build_units", "classify", "detect_conflicts",
    "store", "Unit", "Link", "SynthesisResult", "InvalidUnitIdError",
]
