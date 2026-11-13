import pytest

from orthopaedic_knowledge.alignment import normalize_arabic, split_sentences
from orthopaedic_knowledge.ingestion import TextBlock
from orthopaedic_knowledge.ingestion.models import InvalidBlockError


def test_arabic_normalization_basics():
    assert normalize_arabic("النَّخْرُ العَظْمِيّ") == "النخر العظمي"
    assert normalize_arabic("أدوية إسلام آيات") == "ادويه اسلام ايات"
    assert normalize_arabic("مضاعفة", unify_taa_marbuta=False) == "مضاعفة"


def test_sentence_split_medical():
    sents = split_sentences("Dr. Smith saw Fig. 3. The angle was 128.5 degrees. Done.", "en")
    assert len(sents) == 3 and "128.5" in sents[1]


def test_arabic_sentence_split():
    sents = split_sentences("يُعد النخر اللاوعائي مضاعفة خطيرة. وقد يسبب انهياراً تحت الغضروف.", "ar")
    assert len(sents) == 2


def test_invalid_block_fail_closed():
    with pytest.raises(InvalidBlockError):
        TextBlock(page=0, text="كتلة").validate()
    with pytest.raises(InvalidBlockError):
        TextBlock(page=1, text="   ").validate()
    with pytest.raises(InvalidBlockError):
        TextBlock(page=1, text="سليم", kind="alien").validate()


def test_block_bbox_must_be_quadruple():
    with pytest.raises(InvalidBlockError):
        TextBlock(page=1, text="سليم", bbox=(1.0, 2.0)).validate()
