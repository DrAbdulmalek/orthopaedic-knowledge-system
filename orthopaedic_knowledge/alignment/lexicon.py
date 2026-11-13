"""قاموس ثنائي اللغة — نقطة ربط مواردك الحالية (مسارد CSV/TMX-derived).

* ``BilingualLexicon()`` — بذرة عظمية مدمجة.
* ``BilingualLexicon.from_csv(path)`` — حمّل مسردك الخاص (عمودا en,ar).
* ``set_default_lexicon`` — اجعله افتراضي المحرك.

مطابقة محافظة: جذر إنجليزي خفيف (جمع -s/-es)، وتجريد سطوح عربية
(الـ، و) قبل المطابقة؛ قيمة البذرة قد تحوي بدائل بـ ``|`` وكل بديل قد يكون
مركباً من كلمات يجب أن تتوفر جميعاً (مثل: ``مفصل صناعي``).
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..ingestion.models import InvalidBlockError
from .normalizer import is_arabic, normalize_arabic
from .similarity import content_tokens

BUILTIN_SEED: dict[str, str] = {
    "femoral": "فخذ", "head": "رأس", "neck": "عنق", "fracture": "كسر|كسور",
    "blood": "دموي", "supply": "ترويه", "artery": "شريان", "medial": "انسي",
    "circumflex": "منعطف", "displacement": "انزياح", "vascular": "وعائيه",
    "injury": "اذيه|اصابه", "garden": "غاردن", "classification": "تصنيف",
    "type": "نوع", "types": "انواع", "four": "اربعه", "incomplete": "ناقصه",
    "impacted": "مثبته", "displaced": "منزاحه", "completely": "تماما",
    "elderly": "مسنين", "patients": "مرضى", "arthroplasty": "مفصل صناعي|مفصل",
    "preferred": "يفضل|مفضل", "preserve": "يحافظ|حفاظ", "mobility": "حركه",
    "osteosynthesis": "تثبيت", "cannulated": "انبوبيه", "screws": "براغي",
    "native": "اصلي", "younger": "اصغر", "avascular": "لاوعائي",
    "necrosis": "نخر", "nonunion": "عدم تحالف|تحالف", "feared": "اخطر",
    "complications": "مضاعفات", "early": "مبكر", "mobilization": "تحريك",
    "reduces": "يقلل", "risk": "خطر", "pneumonia": "التهاب رئوي|رئوي",
    "pressure": "قرصات", "ulcers": "قرصات|قرحه", "deep": "عميق",
    "vein": "وريد", "thrombosis": "انصتاب", "magnetic": "مغناطيسي",
    "resonance": "رنين", "imaging": "تصوير", "detects": "يكتشف",
    "occult": "خفيه", "hours": "ساعات", "disruption": "تضرر",
    "retinacular": "شبكيه", "vessels": "اوعيه", "receives": "يتلقى",
    "depends": "يعتمد", "amount": "مقدار", "result": "يؤدي",
    "primarily": "رئيسيه", "limb": "طرف", "immobilized": "تثبيت",
    "plaster": "جبس", "cast": "جبس|جبيره", "removed": "ازيل|ازاله",
    "six": "سته", "weeks": "اسابيع|اسبوع", "bone": "عظم",
}


def _ar_variants(tok: str) -> set[str]:
    """سطوح رمز عربي مطبَّع: تجريد السوابق الشائعة (ال، و، ب، ل)."""
    out = {tok}
    if len(tok) > 4 and tok.startswith("ال"):
        out.add(tok[2:])
    for prefix in ("و", "ب", "ل"):
        if len(tok) > 3 and tok.startswith(prefix):
            out.add(tok[1:])
    if len(tok) > 5 and tok.startswith("وال"):
        out.add(tok[3:])
    return out


def _en_stems(tok: str) -> tuple[str, ...]:
    if len(tok) > 4 and tok.endswith("es"):
        return (tok, tok[:-2])
    if len(tok) > 3 and tok.endswith("s"):
        return (tok, tok[:-1])
    return (tok,)


class BilingualLexicon:
    """رمز إنجليزي → مجموعات رموز عربية بديلة (تكفي مجموعة واحدة)."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.groups: dict[str, list[tuple[str, ...]]] = {}
        for en, ar in (mapping if mapping is not None else BUILTIN_SEED).items():
            self.add(en, ar)

    def add(self, en_token: str, ar_value: str) -> None:
        groups: list[tuple[str, ...]] = []
        for alt in ar_value.split("|"):
            toks = tuple(t for t in (normalize_arabic(w) for w in alt.split()) if t)
            if toks:
                groups.append(toks)
        for stem in _en_stems(en_token.lower()):
            self.groups.setdefault(stem, []).extend(groups)

    @classmethod
    def from_csv(cls, path: str | Path, en_col: int = 0, ar_col: int = 1) -> "BilingualLexicon":
        """حمّل مسرد CSV محلي (UTF-8، صف ترويسة اختياري) — Fail-Closed."""
        mapping: dict[str, str] = {}
        with Path(path).open(encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            start = 0
            if header and not any(is_arabic(c) for c in header):
                if len(header) <= max(en_col, ar_col):
                    raise InvalidBlockError(f"ترويسة المسرد أقصر من الأعمدة المطلوبة: {header!r}")
                start = 1
            else:
                if header and len(header) > max(en_col, ar_col):
                    mapping[header[en_col].strip().lower()] = header[ar_col].strip()
            for row in reader:
                if len(row) <= max(en_col, ar_col):
                    continue
                en, ar = row[en_col].strip(), row[ar_col].strip()
                if en and ar:
                    mapping.setdefault(en.lower(), ar)
        return cls(mapping)

    def overlap(self, en_text: str, ar_text: str) -> float:
        """نسبة الرموز الإنجليزية المعنوية التي لها مقابل بالبذرة."""
        en_toks = set(content_tokens(en_text))
        if not en_toks:
            return 0.0
        ar_set: set[str] = set()
        for tok in content_tokens(ar_text):
            ar_set |= _ar_variants(tok)
        hits = sum(1 for t in en_toks if self._matches(t, ar_set))
        return hits / len(en_toks)

    def _matches(self, en_tok: str, ar_set: set[str]) -> bool:
        for stem in _en_stems(en_tok):
            for group in self.groups.get(stem, ()):
                if all(g in ar_set for g in group):
                    return True
        return False


_default_lexicon = BilingualLexicon()


def get_default_lexicon() -> BilingualLexicon:
    return _default_lexicon


def set_default_lexicon(lexicon: BilingualLexicon) -> None:
    global _default_lexicon
    _default_lexicon = lexicon
