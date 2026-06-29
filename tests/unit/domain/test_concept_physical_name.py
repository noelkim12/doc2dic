import pytest
from pydantic import ValidationError

from doc2dic.domain import Concept, ConceptStatus, ConceptTermType


def _concept(**overrides: object) -> Concept:
    base = {
        "id": "concept_hp",
        "primary_term": "체력",
        "definition": "캐릭터의 생명 수치",
        "term_type": ConceptTermType.STAT,
        "status": ConceptStatus.ACTIVE,
        "created_at": "2026-06-29T00:00:00Z",
        "updated_at": "2026-06-29T00:00:00Z",
    }
    base.update(overrides)
    return Concept(**base)


def test_physical_name_defaults_to_none() -> None:
    assert _concept().physical_name is None


def test_physical_name_accepts_identifier() -> None:
    assert _concept(physical_name="hp").physical_name == "hp"
    assert _concept(physical_name="max_hp").physical_name == "max_hp"


def test_physical_name_rejects_non_identifier() -> None:
    with pytest.raises(ValidationError):
        _concept(physical_name="체력")
    with pytest.raises(ValidationError):
        _concept(physical_name="max hp")
    with pytest.raises(ValidationError):
        _concept(physical_name="1hp")
