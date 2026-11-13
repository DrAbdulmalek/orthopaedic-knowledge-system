"""ضمان الجودة: كاشف الحذف/الإضافة + كاشف التعارضات + تقرير HTML."""

from .conflict_detector import bidirectional_mismatch, detect_term_conflicts
from .omission_detector import detect_omissions, open_flags
from .report import build_report, export_report

__all__ = [
    "detect_omissions", "open_flags", "detect_term_conflicts",
    "bidirectional_mismatch", "build_report", "export_report",
]
