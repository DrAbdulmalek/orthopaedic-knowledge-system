# سير العمل التشغيلي — WORKFLOW

## دورة الحياة

```
استيعاب → محاذاة → مصطلحات            (كل شيء UNPROVEN عند الولادة)
   │
   ├─ qa: أعلام + سجل رفض Fail-Closed
   ├─ تقرير HTML عربي + XLIFF للمراجع
   │       ├─ اعتماد  → PROVEN   (سجل محمي)
   │       ├─ تعارض   → BLOCKED  (يُحسم يدوياً)
   │       └─ تصحيح   → corrections.db (قاعدة دائمة → Auto-apply)
   └─ تصدير TMX/TBX/XLSX (بحد ثقة صريح، وUNALIGNED لا يصدَّر أبداً)
```

## جولة مراجعة عملية

```bash
orthok pilot --out out/pilot
orthok report --knowledge-db out/pilot/knowledge.db --out out/pilot/qa_report.html

# اعتمد محاذاة اختبرتها في التقرير
orthok set-status --knowledge-db out/pilot/knowledge.db \
    --entity alignment --id 3 --status proven --reviewer DR_YOU

# احسم مفهوماً متعارضاً (BLOCKED)
orthok set-status --knowledge-db out/pilot/knowledge.db \
    --entity concept --id C-000009 --status proven

# سجّل قرارك الترجمةي الدائم — يُطبَّق آلياً من الآن فصاعداً
orthok corrections --corrections-db out/pilot/corrections.db \
    --record term "avascular necrosis" ar_preferred "النخر العظمي اللاوعائي" \
    --reviewer DR_YOU

# صدّر ما أُقر فقط
orthok export --knowledge-db out/pilot/knowledge.db \
    --format tmx,tbx,xlsx --out out/pilot/exports --min-confidence 0.75
```

## قواعد ثابتة

1. لا اعتماد آلي للمحاذاة تحت `low_confidence` (0.45 افتراضياً) — علم `LOW_CONFIDENCE`.
2. `UNALIGNED` لا يدخل TMX أبداً — يدخل طابور تدقيق الحذف/الإضافة.
3. المصطلح PROVEN لا يُستبدل آلياً مهما بدا التشابه.
4. مفاهيم BLOCKED لا تُصدَّر نهائياً حتى الحسم.
5. كل تصحيح بشري = قاعدة في `corrections.db` تُطبَّق آلياً وتُسجَّل محاولات تطبيقها (APPLIED/SKIPPED).

## التوسع بعد الـ Pilot

قياس على المعيار الذهبي (F1 آلي في `tests/test_gold_standard.py`) → معايرة `floor` و`low_confidence` → **ثم فقط** فصل آخر. عتبة القبول الحالية F1 ≥ 0.90 على فصل الـ pilot.
