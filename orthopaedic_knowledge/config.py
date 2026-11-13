"""إعدادات محلية صريحة — لا قيم سحابية ولا endpoints.

الافتراضات كلها محلية؛ أي إعداد إضافي يُمرر من CLI أو JSON محلي.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlignmentSettings:
    max_join: int = 3          # أقصى دمج: 1:3 / 3:1
    floor: float = 0.18        # أدنى متوسط تشابه يُقبل للدمج (تحته UNALIGNED)
    skip_cost: float = 0.35    # كلفة جملة بلا مقابل
    merge_discount: float = 0.95
    low_confidence: float = 0.45  # تحت هذا الحد → علم LOW_CONFIDENCE


@dataclass(frozen=True)
class TerminologySettings:
    min_term_count: int = 1
    top_k: int = 40
    syrian_weight: float = 1.0    # ترجيح المصطلح السوري المعتمد
    frequency_weight: float = 0.5
    # مسرد سوري معتمد إضافي (CSV محلي بعمود واحد) — يوسع SYRIAN_SEED
    syrian_lexicon_csv: str | None = None


@dataclass(frozen=True)
class StorageSettings:
    knowledge_db: str = "out/knowledge.db"
    corrections_db: str = "out/corrections.db"
    # DuckDB اختياري للتحليلات القرائية فقط — لا يُستخدم مخزناً أساسياً
    duckdb_mirror: str | None = None


@dataclass(frozen=True)
class Settings:
    alignment: AlignmentSettings = field(default_factory=AlignmentSettings)
    terminology: TerminologySettings = field(default_factory=TerminologySettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    # نماذج التضمين المحلية (ONNX) — مسار مجلد على القرص فقط، ولا تنزيل أبداً
    local_onnx_model_dir: str | None = None


DEFAULTS = Settings()
