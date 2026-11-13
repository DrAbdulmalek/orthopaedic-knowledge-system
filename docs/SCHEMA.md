# مخطط قاعدة البيانات — SCHEMA

المصدر الرسمي: `orthopaedic_knowledge/storage/schema.sql` (المعرفة) و`corrections_schema.sql` (التصحيحات).

## معرفات الإثبات

| المعرّف | النمط | مثال |
|---|---|---|
| `sentence_id` | `[BOOK]_[CHAPTER]_P[###]_S[###]` | `ORTHO101_CH04_P112_S005` |
| | يُشارك بين اللغتين ويميزهما `lang` (ترقيم مستقل لكل لغة) | + `lang='ar'` |
| `alignment_id` | `A-{######}` | `A-000042` |
| `concept_id` | `C-{######}` | `C-000001` |

## knowledge.db — الجداول الأساسية الأربعة

### concepts — المفهوم (ISO 704/1087)

| العمود | النوع | الوصف |
|---|---|---|
| `concept_id` | TEXT PK | `C-000001` |
| `definition` | TEXT | تعريف المفهوم (بالعربية أو الإنجليزية) |
| `definition_lang` | TEXT | لغة التعريف |
| `specialty` | TEXT | **التخصص**: Hip Surgery, Trauma, … |
| `status` | TEXT CHECK | `PROVEN` / `UNPROVEN` / `BLOCKED` |
| `notes` | TEXT | ملاحظات المراجع |

### terms — التسميات (EN/AR Preferred + Synonyms)

| العمود | النوع | الوصف |
|---|---|---|
| `concept_id` | TEXT FK→concepts | المفهوم الأم |
| `lang` | TEXT CHECK | `en` / `ar` |
| `term_text` / `term_norm` | TEXT | السطح + المطبَّع للمطابقة |
| `role` | TEXT CHECK | `preferred` / `synonym` — **المفضل لكل لغة واحد** |
| `term_type` | TEXT CHECK | `fullForm` / `shortForm` / `abbreviation` / `variant` |
| `dialect_weight` | REAL | **الترجيح السوري**: 1.0 = سوري معتمد، 0.0 = Contextual Synonym |
| `context_note` | TEXT | سبب الترجيح / سياق الاستخدام |
| `source` | TEXT | `count=3` · `cooccur=2` · `CORRECTION:5` · `GLOSSARY:file.csv` |
| `alignment_id` | INTEGER | مرجع Provenance ناعم (A-######) |
| `confidence` | REAL | ثقة الاقتراح |
| `status` | TEXT CHECK | PROVEN / UNPROVEN / BLOCKED |
| — | UNIQUE | `(concept_id, lang, term_norm)` — لا تكرار تصميمي |

### alignments — محاذاة الجمل

| العمود | النوع | الوصف |
|---|---|---|
| `alignment_id` | INTEGER PK | `A-000001…` |
| `src_refs` / `tgt_refs` | TEXT JSON | قوائم `sentence_id` (يدعم 1:N وN:1) |
| `book_code` | TEXT | الكتاب |
| `align_type` | TEXT CHECK | `1:1` · `1:2` · `1:3` · `2:1` · `3:1` · `UNALIGNED` |
| `confidence` | REAL CHECK 0–1 | درجة الثقة المركبة |
| `confidence_breakdown` | TEXT JSON | **التفكيك**: lexical / semantic / numbers / length_ratio |
| `status` | TEXT CHECK | PROVEN / UNPROVEN / BLOCKED |
| `reviewer` / `reviewed_at` | | أثر المراجعة البشرية |

كذلك: `segments` (كل جملة بمعرف provenance + صفحة + bbox + kind)، `documents`، `books`، `qa_flags` (LOW_CONFIDENCE / SUSPECTED_OMISSION / SUSPECTED_ADDITION / TERM_CONFLICT)، `qa_blocks` (سجل الرفض الفشل-الآمن).

## corrections.db — حلقة التصحيح المستمرة (قاعدة منفصلة عمداً)

### corrections — قواعد قرارات المراجعين

```sql
corrections (
  correction_id INTEGER PK,
  entity        TEXT CHECK (alignment|term|concept|segment),
  match_rule    TEXT CHECK (exact_id|norm_term),  -- كيف يُعاد تطبيقها لاحقاً
  entity_key    TEXT,        -- 'A-000012' أو 'avascular necrosis'
  field         TEXT,        -- 'ar_preferred' | 'status' | 'definition' …
  old_value     TEXT,
  new_value     TEXT,
  reviewer      TEXT
)
```

### correction_applications — سجل التطبيق الآلي (الشفافية إلزامية)

```sql
correction_applications (
  application_id INTEGER PK,
  correction_id  INTEGER FK→corrections,
  target_entity  TEXT, target_key TEXT,
  result         TEXT CHECK (APPLIED|SKIPPED|BLOCKED),
  detail         TEXT, applied_at TEXT
)
```

**آلية Auto-apply**: قبل كتابة أي اقتراح آلي جديد لمصطلح، يُسأل `corrections.db`:
`lookup('term', en_norm, 'ar_preferred')` → إن وُجدت قاعدة فهي **تتفوق على اقتراح المحرك**:
المصطلح المصحح يُرفع `role='preferred', dialect_weight=1.0`، والاقتراح الآلي السابق ينزل
`role='synonym'` مع `context_note='demoted by correction #N'`، ويُدوَّن كل ذلك في
`correction_applications`. المصطلحات PROVEN المحمية لا تُمس.

## استعلامات المراجعة الشائعة

```sql
-- الأضعف أولاً (طابور المراجعة)
SELECT alignment_id, align_type, confidence FROM alignments
WHERE status='UNPROVEN' ORDER BY confidence ASC LIMIT 50;

-- المفاهيم المتعارضة (3+ مترادفات عربية)
SELECT c.concept_id, COUNT(DISTINCT t.term_norm) v
FROM concepts c JOIN terms t ON t.concept_id=c.concept_id AND t.lang='ar'
GROUP BY c.concept_id HAVING v >= 3;

-- المصطلحات السورية المعتمدة
SELECT term_text FROM terms WHERE lang='ar' AND dialect_weight=1.0;
```
