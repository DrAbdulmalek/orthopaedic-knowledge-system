"""اختبارات معرفات Provenance: [BOOK]_[CHAPTER]_[PAGE]_[SENT]."""

import pytest

from orthopaedic_knowledge.ids import (
    InvalidIdError,
    make_alignment_ref,
    make_concept_id,
    make_sentence_id,
    parse_sentence_id,
)


def test_valid_sentence_id_roundtrip():
    sid = make_sentence_id("ORTHO101", "CH04", 112, 5)
    assert sid == "ORTHO101_CH04_P112_S005"
    parsed = parse_sentence_id(sid)
    assert parsed == {"book": "ORTHO101", "chapter": "CH04", "page": 112, "sent": 5}


def test_malformed_book_rejected():
    with pytest.raises(InvalidIdError):
        make_sentence_id("ortho101", "CH04", 1, 1)  # يجب أن يكون بحروف كبيرة


def test_malformed_chapter_rejected():
    with pytest.raises(InvalidIdError):
        make_sentence_id("ORTHO101", "chapter4", 1, 1)


def test_nonpositive_page_rejected():
    with pytest.raises(InvalidIdError):
        make_sentence_id("ORTHO101", "CH04", 0, 1)


def test_parse_garbage_returns_none_not_guess():
    assert parse_sentence_id("hello world") is None
    assert parse_sentence_id("") is None
    assert parse_sentence_id("ORTHO101_CH04_P0_S005") is None  # صفحة صفر مرفوضة بالتصميم


def test_concept_and_alignment_refs():
    assert make_concept_id(1) == "C-000001"
    assert make_alignment_ref(42) == "A-000042"
    with pytest.raises(InvalidIdError):
        make_concept_id(0)
