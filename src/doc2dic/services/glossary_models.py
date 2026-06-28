"""Glossary service input models and typed errors."""

from dataclasses import dataclass

from doc2dic.domain import (
    ConceptStatus,
    ConceptTermType,
    TermVariantStatus,
    TermVariantType,
)


class GlossaryError(RuntimeError):
    """Base class for glossary service failures."""


class DuplicateGlossaryItemError(GlossaryError):
    """Raised when a concept or variant would duplicate normalized glossary text."""


class GlossaryItemNotFoundError(GlossaryError):
    """Raised when a requested glossary item does not exist."""


class InvalidRelationTargetError(GlossaryError):
    """Raised when a relation target is missing or invalid."""


@dataclass(frozen=True, slots=True)
class CreateConceptInput:
    """Parsed concept creation command."""

    primary_term: str
    definition: str
    term_type: ConceptTermType
    tags: tuple[str, ...] = ()
    source_document: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateConceptInput:
    """Parsed concept update command."""

    primary_term: str | None = None
    definition: str | None = None
    term_type: ConceptTermType | None = None
    status: ConceptStatus | None = None
    tags: tuple[str, ...] | None = None
    source_document: str | None = None


@dataclass(frozen=True, slots=True)
class CreateVariantInput:
    """Parsed term variant creation command."""

    concept_id: str
    label: str
    variant_type: TermVariantType
    status: TermVariantStatus = TermVariantStatus.ACTIVE
    language: str = "unknown"
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CreateRelationInput:
    """Parsed concept relation creation command."""

    source_concept_id: str
    target_concept_id: str
    relation_type: str
    confidence: float = 1.0
    source_document_id: str | None = None
