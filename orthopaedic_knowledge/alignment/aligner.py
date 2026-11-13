"""محرك المحاذاة على مستوى الجملة — DP على عمليات دمج محدودة.

الأنواع: 1:1 · 1:2 · 1:3 · 2:1 · 3:1 · UNALIGNED (حذف/إضافة مشتبهة).
الدمج الضعيف ممنوع تحت floor — يظهر UNALIGNED للتدقيق بدل تلويث الذاكرة.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

MAX_JOIN = 3
_NEG = float("-inf")


@dataclass
class Alignment:
    src_indexes: list[int]
    tgt_indexes: list[int]
    align_type: str
    confidence: float
    breakdown: dict = field(default_factory=dict)

    @property
    def is_unaligned(self) -> bool:
        return self.align_type == "UNALIGNED"


@dataclass
class AlignmentResult:
    alignments: list[Alignment]
    dp_score: float
    skipped_src: int
    skipped_tgt: int

    @property
    def type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self.alignments:
            counts[a.align_type] = counts.get(a.align_type, 0) + 1
        return counts


def align(
    src: list[str],
    tgt: list[str],
    sim_fn: Callable[[str, str], tuple[float, dict]],
    max_join: int = MAX_JOIN,
    floor: float = 0.18,
    skip_cost: float = 0.35,
    merge_discount: float = 0.95,
    min_pair_ratio: float = 0.5,
) -> AlignmentResult:
    """حاذِ قائمتين؛ ``sim_fn`` يعيد (الثقة، التفكيك) — يُستخدم متوسط الثقة.

    Ops: skips (1,0)/(0,1) بكلفة skip_cost؛ دمج حتى max_join بخصم
    merge_discount^(k-1).

    Fail-Closed ضد «مرساة قوية تبتلع جيرانها»: الدمج يُرفض إن كان متوسطه
    تحت ``floor`` أو إن كان **أي زوج** داخله تحت ``floor × min_pair_ratio``
    — لا مرساة واحدة تغطي جملة يتيمة لا صلة لها بالدمج.
    """
    min_pair = floor * min_pair_ratio
    n, m = len(src), len(tgt)
    dp = [[_NEG] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, tuple[int, int], str] | None]] = [
        [None] * (m + 1) for _ in range(n + 1)
    ]
    dp[0][0] = 0.0

    def _pair_score(a: int, b: int) -> tuple[float, dict] | None:
        try:
            score, breakdown = sim_fn(src[a], tgt[b])
        except Exception:  # noqa: BLE001 — فشل آمن: زوج لا يُقاس لا يُدمج
            return None
        if score is None or score != score:  # None / NaN
            return None
        return float(score), breakdown

    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == _NEG:
                continue
            base = dp[i][j]
            for di, dj, kind in ((1, 0, "UNALIGNED"), (0, 1, "UNALIGNED")):
                if i + di <= n and j + dj <= m:
                    if base - skip_cost > dp[i + di][j + dj]:
                        dp[i + di][j + dj] = base - skip_cost
                        back[i + di][j + dj] = (i, j, (di, dj), kind)
            for di in range(1, max_join + 1):
                if i + di > n:
                    break
                for dj in range(1, max_join + 1):
                    if j + dj > m:
                        break
                    k = di * dj
                    if k > max_join:
                        continue
                    scores = [_pair_score(i + a, j + b) for a in range(di) for b in range(dj)]
                    if any(s is None for s in scores):
                        continue
                    vals = [s[0] for s in scores]
                    mean = sum(vals) / k
                    # بوابة الربط الفعلي: المكوّن اللفظي/القاموسي (الأرقام المحايدة
                    # 0.5 لا تصنع رابطاً وهمياً) — أدنى زوج داخل الدمج يجب أن يثبت
                    # تداخلاً حقيقياً وإلا فالدمج مرفوض ويبقى العنصر UNALIGNED.
                    lexical_links = [float(s[1].get("lexical", s[0])) for s in scores]
                    if mean < floor or min(lexical_links) < min_pair:
                        continue
                    merged_breakdown = {"pairs": k, "scores": [round(v, 4) for v in vals]}
                    cand = base + mean * (merge_discount ** (k - 1))
                    if cand > dp[i + di][j + dj]:
                        dp[i + di][j + dj] = cand
                        back[i + di][j + dj] = (i, j, (di, dj), f"{di}:{dj}")

    if dp[n][m] == _NEG:
        all_unaligned = (
            [Alignment([i], [], "UNALIGNED", 0.0) for i in range(n)]
            + [Alignment([], [j], "UNALIGNED", 0.0) for j in range(m)]
        )
        return AlignmentResult(all_unaligned, 0.0, n, m)

    alignments: list[Alignment] = []
    i, j = n, m
    while i > 0 or j > 0:
        prev = back[i][j]
        if prev is None:  # شبكة أمان — لا يُفترض الوصول إليها
            if i > 0:
                alignments.append(Alignment([i - 1], [], "UNALIGNED", 0.0))
                i -= 1
                continue
            alignments.append(Alignment([], [j - 1], "UNALIGNED", 0.0))
            j -= 1
            continue
        pi, pj, (di, dj), kind = prev
        if kind == "UNALIGNED":
            alignments.append(
                Alignment([pi] if di else [], [pj] if dj else [], "UNALIGNED", 0.0,
                          {"side": "src" if di else "tgt"})
            )
        else:
            scores = [_pair_score(pi + a, pj + b) for a in range(di) for b in range(dj)]
            mean = sum(s[0] for s in scores) / (di * dj)
            alignments.append(
                Alignment(
                    list(range(pi, pi + di)), list(range(pj, pj + dj)), kind,
                    round(mean, 4), {"pairs": di * dj, "scores": [round(s[0], 4) for s in scores]},
                )
            )
        i, j = pi, pj

    alignments.reverse()
    skipped_src = sum(1 for a in alignments if a.align_type == "UNALIGNED" and a.src_indexes)
    skipped_tgt = sum(1 for a in alignments if a.align_type == "UNALIGNED" and a.tgt_indexes)
    return AlignmentResult(alignments, dp[n][m], skipped_src, skipped_tgt)


def flag_issues(result: AlignmentResult, low_confidence: float = 0.45) -> list[dict]:
    """أعلام QA: ثقة منخفضة، حذف مشتبه (مصدر بلا مقابل)، إضافة مشتبهة."""
    flags: list[dict] = []
    for idx, a in enumerate(result.alignments, start=1):
        if not a.is_unaligned and a.confidence < low_confidence:
            flags.append({"flag_type": "LOW_CONFIDENCE", "alignment_index": idx,
                          "detail": f"confidence {a.confidence:.2f} < {low_confidence}"})
        if a.is_unaligned and a.src_indexes:
            flags.append({"flag_type": "SUSPECTED_OMISSION", "alignment_index": idx,
                          "detail": "جملة مصدر بلا مقابل — حذف مشتبه"})
        if a.is_unaligned and a.tgt_indexes:
            flags.append({"flag_type": "SUSPECTED_ADDITION", "alignment_index": idx,
                          "detail": "جملة هدف بلا مقابل — إضافة مشتبهة"})
    return flags
