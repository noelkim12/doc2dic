import pytest
from pydantic import ValidationError

from doc2dic.domain import ConceptStatus, ConceptTermType
from doc2dic.mcp.schemas import (
    CreateConceptToolInput,
    DeleteConceptToolInput,
    UpdateConceptToolInput,
)


def test_create_schema_accepts_valid_physical_name() -> None:
    model = CreateConceptToolInput(
        primary_term="체력",
        definition="플레이어 생존 수치",
        physical_name="hp",
    )

    assert model.physical_name == "hp"
    assert model.term_type is ConceptTermType.UNKNOWN
    assert model.tags == ()


def test_create_schema_rejects_invalid_physical_name_pattern() -> None:
    with pytest.raises(ValidationError):
        CreateConceptToolInput(
            primary_term="체력",
            definition="생존 수치",
            physical_name="2hp",
        )


def test_create_schema_rejects_empty_definition() -> None:
    with pytest.raises(ValidationError):
        CreateConceptToolInput(primary_term="체력", definition="")


def test_update_schema_requires_concept_id() -> None:
    with pytest.raises(ValidationError):
        UpdateConceptToolInput()  # type: ignore[call-arg]


def test_update_schema_accepts_status_patch() -> None:
    model = UpdateConceptToolInput(
        concept_id="concept_1",
        status=ConceptStatus.DEPRECATED,
    )

    assert model.status is ConceptStatus.DEPRECATED
    assert model.primary_term is None


def test_delete_schema_defaults_confirm_false() -> None:
    model = DeleteConceptToolInput(concept_id="concept_1")

    assert model.confirm is False
