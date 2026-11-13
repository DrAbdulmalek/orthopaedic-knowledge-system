"""بيانات وهمية تمثل فصلاً طبياً حقيقياً الشكل: كسور عنق الفخذ (CH04).

* 12 جملة إنجليزية / 13 عربية — تتضمن حالة 1:2 (المترجم قسّم جملة).
* جملتان للجبس لإثبات الترجيح السوري (جبس ← مفضّل، جبيرة جبسية ← مرادف سياقي).
* كتلة تالفة واحدة (صفحة 0) لإثبات الفشل الآمن: تُرفض وتُسجَّل BLOCKED.
* لا ملفات PDF مطلوبة — النص كتلاً جاهزة، والتوقيع البنيوي مطابق لمخرج PyMuPDF.
"""

from __future__ import annotations

from orthopaedic_knowledge.ingestion import ChapterDocument, TextBlock

BOOK_CODE = "ORTHO101"
CHAPTER = "CH04"

# --------------------------------------------------------------------------- EN
EN_SENTENCES: list[tuple[int, str]] = [
    (110, "The femoral head receives its blood supply primarily from the medial femoral circumflex artery."),
    (110, "Disruption of the retinacular vessels may result in avascular necrosis of the femoral head."),
    (110, "The risk of avascular necrosis depends on fracture displacement and vascular injury."),
    (111, "Garden classification separates femoral neck fractures into four types according to displacement."),
    (111, "Type I fractures are incomplete or impacted, while type IV fractures are completely displaced."),
    (111, "In displaced fractures in elderly patients, arthroplasty is often preferred to preserve mobility."),
    (111, "Osteosynthesis with cannulated screws preserves the native femoral head in younger patients."),
    (112, "Avascular necrosis and nonunion are the two most feared complications of femoral neck fractures."),
    (112, "Early mobilization reduces the risk of pneumonia, pressure ulcers, and deep vein thrombosis."),
    (112, "Magnetic resonance imaging detects occult fractures within hours of injury."),
    (112, "The limb was immobilized in a plaster cast for six weeks."),
    (112, "The cast was removed after six weeks."),
]

# --------------------------------------------------------------------------- AR
# الجملة السادسة الإنكليزية قُسمت عند الترجمة إلى جملتين عربيتين (حالة 1:2).
AR_SENTENCES: list[tuple[int, str]] = [
    (110, "يتلقى رأس عظم الفخذ ترويته الدموية بصورة رئيسية من الشريان الفخذي المنعطف الإنسي."),
    (110, "قد يؤدي تضرر الأوعية الشبكية إلى النخر العظمي اللاوعائي لرأس الفخذ."),
    (110, "يعتمد خطر النخر اللاوعائي على مقدار انزياح الكسر والأذية الوعائية."),
    (111, "يفصل تصنيف غاردن كسور عنق الفخذ إلى أربعة أنواع وفق درجة الانزياح."),
    (111, "الكسور من النوع الأول ناقصة أو مثبتة، أما النوع الرابع فهي منزاحة تماماً."),
    (111, "في الكسور المنزاحة عند المرضى المسنين، يُفضَّل غالباً استخدام المفصل الصناعي."),
    (111, "والهدف من ذلك الحفاظ على القدرة على الحركة لأطول فترة ممكنة."),
    (111, "يحافظ التثبيت العظمي بالبراغي الأنبوبية على رأس الفخذ الأصلي عند المرضى الأصغر سناً."),
    (112, "يُعد النخر اللاوعائي وعدم التحالف أخطر مضاعفات كسور عنق الفخذ."),
    (112, "يقلل التحريك المبكر من خطر الالتهاب الرئوي والقرصات وانصتاب الوريد العميق."),
    (112, "يكتشف التصوير بالرنين المغناطيسي الكسور الخفية خلال ساعات من الإصابة."),
    (112, "جر تثبيت الطرف بجبيرة جبسية لمدة ستة أسابيع."),
    (112, "أزيل الجبس بعد ستة أسابيع."),
]


def build_mock_documents() -> tuple[ChapterDocument, ChapterDocument]:
    """ابنِ المستندين وهمياً — بنية الكتل مطابقة لما ينتجه محلل PDF حقيقي."""
    src = ChapterDocument(book_code=BOOK_CODE, chapter=CHAPTER, lang="en")
    for page, sent in EN_SENTENCES:
        src.blocks.append(
            TextBlock(
                page=page, text=sent, kind="body",
                bbox=(72.0, 80.0, 540.0, 95.0),   # إحداثيات واقعية الشكل (نقطة)
                section_path=f"{CHAPTER}/Femoral Neck Fractures",
            )
        )
    tgt = ChapterDocument(book_code=BOOK_CODE, chapter=CHAPTER, lang="ar")
    for page, sent in AR_SENTENCES:
        tgt.blocks.append(
            TextBlock(
                page=page, text=sent, kind="body",
                bbox=(72.0, 80.0, 540.0, 95.0),
                section_path=f"{CHAPTER}/كسور عنق الفخذ",
            )
        )
    # كتلة تالفة عمداً (صفحة 0) — الفشل الآمن يرفضها ويسجلها BLOCKED
    tgt.blocks.append(TextBlock(page=0, text="كتلة تالفة للتجربة", kind="body"))
    return src, tgt


# المعيار الذهبي المصغر — حقيقة يدوية لفصل الـ pilot (يستخدمه tests/test_gold_standard.py)
GOLD_PAIRS: list[dict] = [
    {"src": 0, "tgt": 0, "type": "1:1"},
    {"src": 1, "tgt": 1, "type": "1:1"},
    {"src": 2, "tgt": 2, "type": "1:1"},
    {"src": 3, "tgt": 3, "type": "1:1"},
    {"src": 4, "tgt": 4, "type": "1:1"},
    {"src": 5, "tgt": [5, 6], "type": "1:2"},
    {"src": 6, "tgt": 7, "type": "1:1"},
    {"src": 7, "tgt": 8, "type": "1:1"},
    {"src": 8, "tgt": 9, "type": "1:1"},
    {"src": 9, "tgt": 10, "type": "1:1"},
    {"src": 10, "tgt": 11, "type": "1:1"},
    {"src": 11, "tgt": 12, "type": "1:1"},
]
