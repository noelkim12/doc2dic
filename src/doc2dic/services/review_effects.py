"""Glossary effect application for review actions."""

from dataclasses import dataclass

from doc2dic.domain import (
    Concept,
    ConceptRelation,
    ConceptTermType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.glossary_service import (
    CreateConceptInput,
    CreateRelationInput,
    CreateVariantInput,
    DuplicateGlossaryItemError,
    GlossaryItemNotFoundError,
    GlossaryService,
    InvalidRelationTargetError,
)
from doc2dic.services.review_models import ReviewActionInput, ReviewServiceError
from doc2dic.services.review_models import ReviewServiceErrorCode as ErrorCode
from doc2dic.services.review_state_machine import ReviewAction


@dataclass(frozen=True, slots=True)
class ReviewEffectResult:
    """Storage effect result created by one review action."""

    concept: Concept | None = None
    variant: TermVariant | None = None
    relation: ConceptRelation | None = None


def apply_review_effect(
    glossary: GlossaryService,
    command: ReviewActionInput,
) -> ReviewEffectResult:
    """Apply the glossary side effect for one planned review action."""
    concept: Concept | None = None
    variant: TermVariant | None = None
    relation: ConceptRelation | None = None
    match command.action:
        case ReviewAction.RESOLVE_AS_NEW_CONCEPT:
            concept = _create_concept(glossary, command)
        case ReviewAction.RESOLVE_AS_ALIAS:
            variant = _create_variant(glossary, command, TermVariantType.ALIAS)
        case ReviewAction.RESOLVE_AS_FORBIDDEN:
            variant = _create_variant(glossary, command, TermVariantType.FORBIDDEN)
        case ReviewAction.RESOLVE_AS_RELATION:
            relation = _create_relation(glossary, command)
        case ReviewAction.DISMISS | ReviewAction.MARK_FAILED:
            pass
        case ReviewAction.RESOLVE_AS_EXISTING_CONCEPT:
            _ensure_concept_exists(glossary, command)
        case ReviewAction.RESOLVE_AS_DEPRECATED:
            variant = _create_variant(glossary, command, TermVariantType.DEPRECATED)
    return ReviewEffectResult(concept=concept, variant=variant, relation=relation)


def _create_concept(
    glossary: GlossaryService,
    command: ReviewActionInput,
) -> Concept:
    try:
        return glossary.create_concept(
            CreateConceptInput(
                primary_term=_required(command.term, "term"),
                definition=_required(command.definition, "definition"),
                term_type=ConceptTermType.UNKNOWN,
            ),
        )
    except DuplicateGlossaryItemError as error:
        raise ReviewServiceError(ErrorCode.DUPLICATE_TERM, str(error)) from error


def _create_variant(
    glossary: GlossaryService,
    command: ReviewActionInput,
    variant_type: TermVariantType,
) -> TermVariant:
    try:
        return glossary.add_variant(
            CreateVariantInput(
                concept_id=_required(command.concept_id, "concept_id"),
                label=_required(command.variant, "variant"),
                variant_type=variant_type,
                status=_variant_status(variant_type),
                reason=command.reason,
            ),
        )
    except GlossaryItemNotFoundError as error:
        raise ReviewServiceError(ErrorCode.CONCEPT_NOT_FOUND, str(error)) from error
    except DuplicateGlossaryItemError as error:
        raise ReviewServiceError(ErrorCode.DUPLICATE_TERM, str(error)) from error


def _create_relation(
    glossary: GlossaryService,
    command: ReviewActionInput,
) -> ConceptRelation:
    try:
        return glossary.add_relation(
            CreateRelationInput(
                source_concept_id=_required(command.source_concept_id, "source"),
                target_concept_id=_required(command.target_concept_id, "target"),
                relation_type=_required(command.relation_type, "relation_type"),
            ),
        )
    except InvalidRelationTargetError as error:
        raise ReviewServiceError(ErrorCode.INVALID_RELATION, str(error)) from error


def _ensure_concept_exists(
    glossary: GlossaryService,
    command: ReviewActionInput,
) -> None:
    try:
        _ = glossary.get_concept(_required(command.concept_id, "concept_id"))
    except GlossaryItemNotFoundError as error:
        raise ReviewServiceError(ErrorCode.CONCEPT_NOT_FOUND, str(error)) from error


def _variant_status(variant_type: TermVariantType) -> TermVariantStatus:
    match variant_type:
        case TermVariantType.FORBIDDEN:
            return TermVariantStatus.FORBIDDEN
        case TermVariantType.DEPRECATED:
            return TermVariantStatus.DEPRECATED
        case (
            TermVariantType.PRIMARY
            | TermVariantType.ALIAS
            | TermVariantType.ABBREVIATION
        ):
            return TermVariantStatus.ACTIVE


def _required(value: str | None, field_name: str) -> str:
    if value is None:
        raise ReviewServiceError(
            ErrorCode.INVALID_PAYLOAD,
            f"Action payload is missing required fields: {field_name}.",
        )
    return value
