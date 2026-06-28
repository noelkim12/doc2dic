"""Glossary concept domain models."""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ConceptTermType(StrEnum):
    """Concept term categories from the public contract."""

    MECHANIC = "mechanic"
    RESOURCE = "resource"
    STATE = "state"
    ACTION = "action"
    STAT = "stat"
    ENTITY = "entity"
    RULE = "rule"
    UI_LABEL = "ui-label"
    LORE = "lore"
    UNKNOWN = "unknown"


class ConceptStatus(StrEnum):
    """Persisted concept lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FORBIDDEN = "forbidden"


class TermVariantType(StrEnum):
    """Stored term variant categories."""

    PRIMARY = "primary"
    ALIAS = "alias"
    FORBIDDEN = "forbidden"
    DEPRECATED = "deprecated"
    ABBREVIATION = "abbreviation"


class TermVariantStatus(StrEnum):
    """Persisted term variant lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FORBIDDEN = "forbidden"


class ConceptRelationStatus(StrEnum):
    """Review status for proposed or approved relations."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class Concept(BaseModel):
    """A glossary concept with canonical tag and variant identifiers."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    primary_term: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=2000)
    term_type: ConceptTermType
    status: ConceptStatus
    tags: tuple[str, ...] = Field(default_factory=tuple)
    variant_ids: tuple[str, ...] = Field(default_factory=tuple)
    created_at: str
    updated_at: str
    scope_note: str | None = None
    non_goals: tuple[str, ...] = Field(default_factory=tuple)
    examples: tuple[str, ...] = Field(default_factory=tuple)
    owner: str | None = None
    source_document: str | None = Field(default=None, max_length=512)


class TermVariant(BaseModel):
    """A surface form attached to a concept."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^variant_[A-Za-z0-9_-]+$")
    concept_id: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=160)
    normalized_label: str = Field(min_length=1, max_length=160)
    variant_type: TermVariantType
    status: TermVariantStatus
    created_at: str
    language: str = "unknown"
    reason: str | None = None


class Tag(BaseModel):
    """A reusable concept tag."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: str
    label: str = Field(min_length=1, max_length=64)


class ConceptRelation(BaseModel):
    """A typed graph relation between two concepts."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str
    source_concept_id: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    target_concept_id: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    relation_type: str = Field(min_length=1, max_length=64)
    confidence: float = Field(ge=0, le=1)
    status: ConceptRelationStatus
    source_document_id: str | None = None
