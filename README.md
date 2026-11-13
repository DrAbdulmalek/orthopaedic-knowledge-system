# orthopaedic-knowledge — منظومة المعرفة والترجمة العظمية

**Orthopaedic Knowledge & Translation System** — منظومة Local-First تعمل محلياً بالكامل على Manjaro Linux، تربط الكتب العظمية الإنجليزية بنسخها العربية المترجمة **على مستوى الجملة**، وتستخرج المصطلحات لبناء **مسرد مفاهيمي احترافي** (Concept-Oriented Terminology)، مع دمج موارد الترجمة الحالية (TMX / Glossaries) **دون رفع أي بيانات إلى السحابة**.

## الرؤية

المترجم الطبي لا يحتاج خدمة سحابية؛ يحتاج **ذاكرة ترجمة يثق بها** و**مسرداً محمياً** و**قابلاً للتتبع إلى الصفحة والجملة**. هذه المنظومة تحول ثنائية (كتاب إنجليزي + ترجمته العربية) إلى أصل معرفي دائم:

```
كتاب EN + ترجمته AR
   │  استيعاب واعٍ للتخطيط (Layout-Aware)
   ▼
محاذاة جمل 1:1 · 1:2 · 2:1 · UNALIGNED  ── درجة ثقة مفككة
   │
   ▼
مسرد مفاهيمي  (Concept → EN/AR Preferred + Contextual Synonyms)
   │  ترجيح سوري + حلقة تصحيح مستمرة
   ▼
TMX 1.4b · TBX-Basic · XLIFF 2.0 · CSV/XLSX  + تقرير QA عربي
```

## المبادئ المعمارية (غير قابلة للتفاوض)

| # | المبدأ | التطبيق في الكود |
|---|---|---|
| 1 | **Local-First بالكامل** | صفر استدعاءات شبكة في النواة؛ نماذج ONNX تُوضع على القرص يدوياً ولا تُنزَّل أبداً |
| 2 | **Fail-Closed** | أي بيانات تالفة → رفض + تسجيل BLOCKED (`fail_closed.py`)، لا تخمين ولا صمت |
| 3 | **Provenance** | كل جملة: `[BOOK]_[CHAPTER]_[PAGE]_[SENTENCE_ID]` مثل `ORTHO101_CH04_P112_S005` |
| 4 | **تصنيف إلزامي** | كل محاذاة/مصطلح/مفهوم: `PROVEN` (بشري) / `UNPROVEN` (آلي) / `BLOCKED` (تعارض) |
| 5 | **ترجيح سوري** | المصطلح السوري المعتمد يتقدم تلقائياً؛ البقية Contextual Synonyms محفوظة لا محذوفة |
| 6 | **حلقة تصحيح مستمرة** | قاعدة منفصلة `corrections.db`؛ كل قرار بشري = قاعدة تُطبَّق آلياً (Auto-apply) على المعالجات القادمة |

## الهيكلية

```
orthopaedic_knowledge/        الحزمة الأساسية
├── ingestion/                استخراج واعٍ للتخطيط + هيكلة الفقرات/الجداول + مدقق Fail-Closed
├── alignment/                المحاذاة الدلالية للجمل + التطبيع + القاموس الثنائي + الثقة المفككة
├── terminology/              استخراج MWT + مخزن المفاهيم + الترجيح السوري
├── integration/              TMX · TBX-Basic · XLIFF 2.0 · CSV/XLSX
├── qa/                       كاشف الحذف/الإضافة + كاشف التعارضات + تقرير HTML عربي RTL
├── storage/                  knowledge.db (المخطط الموحد) + corrections.db (حلقة التصحيح)
├── cli.py                    واجهة الأوامر orthok
├── ids.py                    معرفات الإثبات + مدققها الصارم
└── fail_closed.py            آلية الرفض الآمن المسجل
tests/                        37 اختباراً، بينها معيار ذهبي يقيس F1 فعلياً
pilot/                        فصل تجريبي كامل ببيانات وهمية (كسور عنق الفخذ)
docs/                         SCHEMA · SECURITY · STYLE_GUIDE_AR · WORKFLOW
```

## التثبيت (Manjaro / Python 3.11–3.13)

```bash
git clone https://github.com/DrAbdulmalek/orthopaedic-knowledge-system
cd orthopaedic-knowledge-system
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # النواة + الاختبارات (openpyxl وحيدة إلزامياً)

# إضافات اختيارية — كلها محلية:
pip install -e ".[pdf]"        # PyMuPDF: استخراج PDF واعٍ للتخطيط
pip install -e ".[semantic]"   # ONNX Runtime: تضمينات محلية (ضع model.onnx + tokenizer.json محلياً)
pip install -e ".[analytics]"  # DuckDB: تحليلات قرائية فوق القاعدة
```

## تشغيل الـ Pilot التجريبي (دقيقة واحدة)

```bash
orthok pilot --out out/pilot
# أو: python -m pilot.run_pilot
```

يُنتج على بيانات وهمية نظيفة (12 جملة EN ↔ 13 جملة AR تشمل انقسام مترجم وكتلة تالفة):

| المخرج | المحتوى |
|---|---|
| `knowledge.db` | 25 جملة بمعرفات provenance، 12 محاذاة (11× `1:1` + 1× `1:2`)، مفاهيم ومصطلحات UNPROVEN/BLOCKED |
| `corrections.db` | قرار مراجع تجريبي + **إثبات تطبيق آلي** (before → after) |
| `memory.tmx` | TMX 1.4b بخصائص x-confidence / x-status / x-provenance |
| `alignments.xlsx` | أوراق: Alignments / Terms / **Blocked** |
| `qa_report.html` | تقرير عربي RTL: أعلام، سجل الرفض، المحاذات الأضعف أولاً |

ثم استكشف:

```bash
orthok stats --knowledge-db out/pilot/knowledge.db
orthok report --knowledge-db out/pilot/knowledge.db --out report.html
orthok export --knowledge-db out/pilot/knowledge.db --format tmx,csv,xlsx --out out/exports
orthok set-status --knowledge-db out/pilot/knowledge.db --entity alignment --id 3 --status proven --reviewer DR_YOU
orthok corrections --corrections-db out/pilot/corrections.db   # اعرض قواعد التصحيح الدائمة
```

## التشغيل على كتاب حقيقي (PDF → محاذاة → تصدير)

```bash
# 1) استخراج كتل واعية للتخطيط (يتطلب: pip install -e ".[pdf]")
orthok ingest-pdf --pdf ch04_en.pdf --book-code ORTHO101 --chapter CH04 --lang en --out en_blocks.jsonl
orthok ingest-pdf --pdf ch04_ar.pdf --book-code ORTHO101 --chapter CH04 --lang ar --out ar_blocks.jsonl

# 2) محاذاة بمسردك الخاص + مسرد سوري معتمد + نموذج ONNX محلي (كلها اختيارية)
orthok align --src en_blocks.jsonl --tgt ar_blocks.jsonl --book-code ORTHO101 --chapter CH04 \
    --format jsonl --lexicon my_glossary.csv --syrian-lexicon syrian_terms.csv \
    --model-dir models/bge-m3-onnx --knowledge-db out/book.db --corrections-db out/corrections.db
```

قواعد التصدير الصارمة: سجلات `BLOCKED` لا تخرج إلى TMX/TBX نهائياً، و`UNALIGNED` لا يدخل الذاكرة الترجمية أبداً، والجداول/التعليقات تيارات منفصلة عن المتن، ومصطلح `PROVEN` لا تنزّله قاعدة تصحيح آلية.

## المرحلة 2: دمج الكتب الإنجليزية للامتحان — `orthok synthesize`

وحدة التوليف تدمج كتباً عظمية إنجليزية حول مرجع أساسي («العمود الفقري») وتنتج فصلاً امتحانياً موحداً بلا تكرار:

| القرار | المعنى | المعالجة |
|---|---|---|
| `DUPLICATE` | نفس معلومة العمود الفقري بصياغة أخرى | تنهار إلى سطر توثيق (الكتاب + الصفحة فقط) |
| `DELTA` | معلومة جديدة غير موجودة في العمود الفقري | تدخل الفصل الموحد بمعرف إثبات `[BOOK]_CH_P###_U###` |
| `CONFLICT` | رقم/تصنيف/توصية متعارض بين كتابين | جدول تعارضات `BLOCKED` — الحسم بشري إلزامي |

```bash
# بعد استخراج الكتب بـ ingest-pdf (مرة واحدة لكل فصل):
orthok synthesize \
  --spine miller_ch04.jsonl --spine-code MILLER \
  --other rockwood_ch04.jsonl ROCKWOOD --other apley_ch04.jsonl APLEY \
  --chapter CH04 --format jsonl \
  --model-dir models/bge-m3-onnx \
  --db out/synthesis/synthesis.db --out out/synthesis

# أو جرّب الدمج الثلاثي الوهمي الرسمي فوراً:
orthok synthesize-demo --out out/synth_demo
```

المخرجات: `unified_chapter.md` (الفصل الموحد: عمود فقري + إضافات موسومة + جدول تعارضات)، `synthesis_report.html` (تقرير عربي RTL: بطاقات القرارات + جدول التعارضات بدرجاتها وأسبابها)، `synthesis_summary.json`، وقاعدة `synthesis.db` منفصلة (sources/units/links/deltas/conflicts/blocked_log). قواعد التعارض الثلاث الموثقة: أرقام متباينة على نفس الموضوع (6 ≠ 12 أسبوعاً)، نظاما تصنيف مختلفان (Garden ≠ Pauwels)، توصية سالبة مقابل موجبة (يُفضَّل ≠ يُجنَّب) — تظهر بدرجة التطابق وسبب القرار ولا تُحسم آلياً أبداً. التشابه الدلالي عبر ONNX اختياري ومشفَّر دفعة واحدة؛ الوضع الافتراضي معجمي (Containment) يعمل بلا أي نموذج.

## سجل الإصلاحات (v0.1.1 — مراجعة خارجية سطراً بسطر)

منع تصدير BLOCKED (TMX/TBX) · حماية مصطلحات PROVEN من قواعد التصحيح · ذاكرة أزواج للمحاذاة + استخراج مصطلحات بلا O(N²) · عزل caption/table_cell عن تيار المحاذاة · إلغاء أرقام الصفحات المزيفة في النص الخام · ربط ONNX بـ pipeline (تشفير دفعي، pooling تلقائي 2D/3D، فشل صريح عند مجلد نموذج معطوب) · أمر `ingest-pdf` بخيارات `--lexicon/--syrian-lexicon/--model-dir/--format jsonl` · تصحيح لغوي للبذرة (قرحات، الالتحام، خثار، جبيرة) وتجريد اللواحق الضميرية (ترويته ↔ ترويه).

## ربط مساردك الحالية

```python
from orthopaedic_knowledge.alignment.lexicon import BilingualLexicon, set_default_lexicon

lex = BilingualLexicon.from_csv("my_glossary.csv")   # عمودا en,ar — UTF-8
set_default_lexicon(lex)                             # تصبح أساس المطابقة الثنائية
```

القاموس يقود المحاذاة المعجمية (وضع لا-نموذج) **و** ترشيح مرشحات المصطلحات — لا يُقبل مرشح عربي لمصطلح إنجليزي بلا دليل معجمي.

## حالة التطوير (v0.1.0)

- ✅ النواة كاملة ومختبَرة: تطبيع، تقطيع طبي، محاذاة DP بثقة مفككة، مفاهيم + ترجيح سوري، تصحيحات آلية، تصدير القياسي، تقارير، CI على 3.11/3.12/3.13.
- ✅ المعيار الذهبي المصغر: **F1 ≥ 0.90** على فصل الـ pilot (اختبار آلي يفشل عند الانحدار).
- ⏳ الطريق القادم: استيراد XLIFF المصحح (ذهاب/إياب كامل)، محلل PDF عميق للصفحات المعقدة، تحسين الاستخراج بـ CAMeL Tools/spaCy، واجهة مراجعة محلية، الربط القرائي بـ DuckDB للتحليلات.

## الأمان والخصوصية

انظر `docs/SECURITY.md`: لا شبكة، لا تلميتري، بياناتك لا تترك القرص — والتقارير نفسها محلية.

## الترخيص

MIT للكود. البيانات المشتقة من كتب محمية تبقى خاضعة لحقوق أصحابها (انظر LICENSE).

---

*المصطلحات الإنجليزية في الكود، والشرح بالعربية — كما يليق بمنظومة عربية تخدم ترجمة المعرفة الطبية.*
