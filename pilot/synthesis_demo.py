"""بيانات Demo الرسمية لوحدة التوليف — ثلاثة كتب إنجليزية وهمية لفصل واحد.

النصوص مُعايَرة عمداً لتنتج كل القرارات الثلاثة:
* ROCKWOOD: تكرار (دمج) + إضافة مستقلة + تعارض أرقام + تكرار.
* APLEY: تعارض تصنيف (Garden ≠ Pauwels) + تعارض توصية + إضافة مستقلة.
العمود الفقري: MILLER — المرجع الذي تنهار تحته التكرارات وتُدمج الإضافات.
"""

from __future__ import annotations

from orthopaedic_knowledge.ingestion import ChapterDocument, TextBlock

CHAPTER = "CH04"

SPINE = "MILLER"
OTHERS = ["ROCKWOOD", "APLEY"]

MILLER_UNITS: list[str] = [
    "The femoral head receives its blood supply primarily from the medial femoral circumflex artery.",
    "The Garden classification separates femoral neck fractures into four types according to the degree of displacement.",
    "In displaced fractures in elderly patients, arthroplasty is preferred to preserve mobility.",
    "The limb was immobilized for 6 weeks after osteosynthesis.",
    "Magnetic resonance imaging detects occult fractures within 6 hours.",
]

ROCKWOOD_UNITS: list[str] = [
    "The blood supply of the femoral head comes primarily from the medial femoral circumflex artery.",
    "Garden type I impacted valgus fractures may allow early weight bearing.",
    "The limb was protected for 12 weeks after osteosynthesis.",
    "The Garden classification separates femoral neck fractures into four types based on the degree of displacement.",
]

APLEY_UNITS: list[str] = [
    "The Pauwels classification separates femoral neck fractures into three types according to the degree of vertical shear.",
    "In displaced fractures in elderly patients, screw fixation should be avoided.",
    "Early mobilization reduces the risk of pneumonia and pressure ulcers in the elderly.",
]


def _doc(book_code: str, units: list[str], first_page: int) -> ChapterDocument:
    doc = ChapterDocument(book_code=book_code, chapter=CHAPTER, lang="en")
    for i, text in enumerate(units):
        doc.blocks.append(
            TextBlock(
                page=first_page + i, text=text, kind="body",
                bbox=(72.0, 80.0, 540.0, 95.0),
                section_path=f"{CHAPTER}/Femoral Neck Fractures",
            )
        )
    return doc


def build_demo_documents() -> tuple[tuple[str, ChapterDocument], list[tuple[str, ChapterDocument]]]:
    """المستندات الثلاثة — نفس بنية ما ينتجه ingest-pdf من PDFs حقيقية."""
    spine = _doc(SPINE, MILLER_UNITS, 110)
    others = [
        ("ROCKWOOD", _doc("ROCKWOOD", ROCKWOOD_UNITS, 210)),
        ("APLEY", _doc("APLEY", APLEY_UNITS, 310)),
    ]
    return (SPINE, spine), others
