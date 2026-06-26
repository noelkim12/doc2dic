"""Concept routes for the local API contract."""

from typing import Annotated, ClassVar

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette import status

from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    TermVariant,
    TermVariantType,
)
from doc2dic.server.dependencies import DatabaseDep
from doc2dic.services.glossary_service import (
    CreateConceptInput,
    CreateVariantInput,
    DuplicateGlossaryItemError,
    GlossaryItemNotFoundError,
    GlossaryService,
    UpdateConceptInput,
)

router = APIRouter(prefix="/api", tags=["concepts"])


class ConceptCreateBody(BaseModel):
    """Accepted concept creation request body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    primary_term: str = Field(alias="primaryTerm", min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=2000)
    term_type: ConceptTermType = Field(
        default=ConceptTermType.UNKNOWN,
        alias="termType",
    )
    tags: tuple[str, ...] = ()


class ConceptPatchBody(BaseModel):
    """Accepted concept patch request body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    primary_term: str | None = Field(
        default=None,
        alias="primaryTerm",
        min_length=1,
        max_length=160,
    )
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    term_type: ConceptTermType | None = Field(default=None, alias="termType")
    status: ConceptStatus | None = None
    tags: tuple[str, ...] | None = None


class VariantCreateBody(BaseModel):
    """Accepted variant creation request body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=160)
    variant_type: TermVariantType = Field(
        default=TermVariantType.ALIAS,
        alias="variantType",
    )
    language: str = "unknown"
    reason: str | None = None


class ConceptPayload(BaseModel):
    """Concept response payload matching the frozen public contract."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    primary_term: str = Field(alias="primaryTerm")
    definition: str
    term_type: str = Field(alias="termType")
    status: str
    tags: tuple[str, ...]
    variants: tuple[str, ...]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class TermVariantPayload(BaseModel):
    """Term variant response payload matching the frozen public contract."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    concept_id: str = Field(alias="conceptId")
    label: str
    variant_type: str = Field(alias="variantType")
    status: str
    created_at: str = Field(alias="createdAt")


@router.get("/concepts")
def list_concepts(
    database: DatabaseDep,
    concept_status: Annotated[ConceptStatus | None, Query(alias="status")] = None,
    tag: Annotated[str | None, Query()] = None,
) -> tuple[ConceptPayload, ...]:
    """Return concepts from the project glossary."""
    service = GlossaryService(database)
    return tuple(
        _concept_payload(concept)
        for concept in service.list_concepts(status=concept_status, tag=tag)
    )


@router.post(
    "/concepts",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_concept(
    database: DatabaseDep,
    body: ConceptCreateBody,
) -> ConceptPayload | JSONResponse:
    """Create a glossary concept."""
    service = GlossaryService(database)
    try:
        concept = service.create_concept(
            CreateConceptInput(
                primary_term=body.primary_term,
                definition=body.definition,
                term_type=body.term_type,
                tags=body.tags,
            ),
        )
    except DuplicateGlossaryItemError as error:
        return _error(status.HTTP_409_CONFLICT, "duplicate_term", str(error))
    return _concept_payload(concept)


@router.get("/concepts/{concept_id}", response_model=None)
def get_concept(
    database: DatabaseDep,
    concept_id: str,
) -> ConceptPayload | JSONResponse:
    """Return one concept by id."""
    service = GlossaryService(database)
    try:
        return _concept_payload(service.get_concept(concept_id))
    except GlossaryItemNotFoundError as error:
        return _error(status.HTTP_404_NOT_FOUND, "concept_not_found", str(error))


@router.patch("/concepts/{concept_id}", response_model=None)
def patch_concept(
    database: DatabaseDep,
    concept_id: str,
    body: ConceptPatchBody,
) -> ConceptPayload | JSONResponse:
    """Patch one concept."""
    service = GlossaryService(database)
    try:
        concept = service.update_concept(
            concept_id,
            UpdateConceptInput(
                primary_term=body.primary_term,
                definition=body.definition,
                term_type=body.term_type,
                status=body.status,
                tags=body.tags,
            ),
        )
    except GlossaryItemNotFoundError as error:
        return _error(status.HTTP_404_NOT_FOUND, "concept_not_found", str(error))
    except DuplicateGlossaryItemError as error:
        return _error(status.HTTP_409_CONFLICT, "duplicate_term", str(error))
    return _concept_payload(concept)


@router.delete(
    "/concepts/{concept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_concept(database: DatabaseDep, concept_id: str) -> Response | JSONResponse:
    """Delete one concept."""
    service = GlossaryService(database)
    try:
        service.delete_concept(concept_id)
    except GlossaryItemNotFoundError as error:
        return _error(status.HTTP_404_NOT_FOUND, "concept_not_found", str(error))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/concepts/{concept_id}/variants",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_term_variant(
    database: DatabaseDep,
    concept_id: str,
    body: VariantCreateBody,
) -> TermVariantPayload | JSONResponse:
    """Create a term variant for a concept."""
    service = GlossaryService(database)
    try:
        variant = service.add_variant(
            CreateVariantInput(
                concept_id=concept_id,
                label=body.label,
                variant_type=body.variant_type,
                language=body.language,
                reason=body.reason,
            ),
        )
    except GlossaryItemNotFoundError as error:
        return _error(status.HTTP_404_NOT_FOUND, "concept_not_found", str(error))
    except DuplicateGlossaryItemError as error:
        return _error(status.HTTP_409_CONFLICT, "duplicate_term", str(error))
    return _variant_payload(variant)


@router.patch("/variants/{variant_id}")
def patch_term_variant(variant_id: str) -> JSONResponse:
    """Return the pending term variant patch stub."""
    _ = variant_id
    return _error(
        status.HTTP_501_NOT_IMPLEMENTED,
        "not_implemented",
        "Route stub is not implemented yet.",
    )


@router.delete("/variants/{variant_id}")
def delete_term_variant(variant_id: str) -> JSONResponse:
    """Return the pending term variant delete stub."""
    _ = variant_id
    return _error(
        status.HTTP_501_NOT_IMPLEMENTED,
        "not_implemented",
        "Route stub is not implemented yet.",
    )


def _concept_payload(concept: Concept) -> ConceptPayload:
    return ConceptPayload(
        id=concept.id,
        primaryTerm=concept.primary_term,
        definition=concept.definition,
        termType=concept.term_type.value,
        status=concept.status.value,
        tags=concept.tags,
        variants=concept.variant_ids,
        createdAt=concept.created_at,
        updatedAt=concept.updated_at,
    )


def _variant_payload(variant: TermVariant) -> TermVariantPayload:
    return TermVariantPayload(
        id=variant.id,
        conceptId=variant.concept_id,
        label=variant.label,
        variantType=variant.variant_type.value,
        status=variant.status.value,
        createdAt=variant.created_at,
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
