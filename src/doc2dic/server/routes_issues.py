"""Issue routes for the local API contract."""

import sqlite3
from typing import Annotated, ClassVar

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette import status

from doc2dic.domain import IssueEvidence, TermIssue
from doc2dic.server.dependencies import DatabaseDep
from doc2dic.server.errors import (
    error_response,
    is_sqlite_lock_error,
    sqlite_lock_response,
)
from doc2dic.services.review_service import (
    ReviewActionInput,
    ReviewActionResult,
    ReviewService,
    ReviewServiceError,
    ReviewServiceErrorCode,
)
from doc2dic.services.review_state_machine import IssueStatus, ReviewAction

router = APIRouter(prefix="/api/issues", tags=["issues"])


class IssueActionBody(BaseModel):
    """Accepted review action body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    expected_version: int = Field(alias="expectedVersion", ge=0)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1)
    action: ReviewAction | None = None
    term: str | None = Field(default=None, min_length=1, max_length=160)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    concept_id: str | None = Field(default=None, alias="conceptId")
    variant: str | None = Field(default=None, min_length=1, max_length=160)
    reason: str | None = Field(default=None, min_length=1, max_length=400)
    source_concept_id: str | None = Field(default=None, alias="sourceConceptId")
    target_concept_id: str | None = Field(default=None, alias="targetConceptId")
    relation_type: str | None = Field(default=None, alias="relationType")


class EvidencePayload(BaseModel):
    """Issue evidence response payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    kind: str
    source_document_id: str = Field(alias="sourceDocumentId")
    quote: str
    confidence: float
    chunk_id: str | None = Field(default=None, alias="chunkId")
    context_before: str = Field(alias="contextBefore")
    context_after: str = Field(alias="contextAfter")


class IssuePayload(BaseModel):
    """Term issue response payload matching the frozen contract."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    issue_type: str = Field(alias="issueType")
    status: str
    surface: str
    evidence: tuple[EvidencePayload, ...]
    created_at: str = Field(alias="createdAt")
    candidate_concept_id: str | None = Field(default=None, alias="candidateConceptId")
    target_concept_id: str | None = Field(default=None, alias="targetConceptId")
    resolved_at: str | None = Field(default=None, alias="resolvedAt")
    version: int
    applied_idempotency_key: str | None = Field(
        default=None,
        alias="appliedIdempotencyKey",
    )


class IssueActionPayload(BaseModel):
    """Review action response payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    outcome: str
    issue: IssuePayload
    concept_id: str | None = Field(default=None, alias="conceptId")
    variant_id: str | None = Field(default=None, alias="variantId")
    relation_id: str | None = Field(default=None, alias="relationId")


@router.get("", response_model=None)
def list_issues(
    database: DatabaseDep,
    issue_status: Annotated[IssueStatus | None, Query(alias="status")] = None,
) -> tuple[IssuePayload, ...] | JSONResponse:
    """Return review issues from the project glossary."""
    try:
        return tuple(
            _issue_payload(issue)
            for issue in ReviewService(database).list_issues(status=issue_status)
        )
    except sqlite3.OperationalError as error:
        return _database_error(error)


@router.get("/{issue_id}", response_model=None)
def get_issue(database: DatabaseDep, issue_id: str) -> IssuePayload | JSONResponse:
    """Return one review issue."""
    try:
        return _issue_payload(ReviewService(database).get_issue(issue_id))
    except ReviewServiceError as error:
        return _service_error(error)


@router.post("/{issue_id}/accept", response_model=IssueActionPayload)
def accept_issue(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
) -> IssueActionPayload | JSONResponse:
    """Apply a body-selected review acceptance action."""
    action = body.action or ReviewAction.RESOLVE_AS_EXISTING_CONCEPT
    return _apply(database, issue_id, body, action)


@router.post("/{issue_id}/dismiss", response_model=IssueActionPayload)
def dismiss_issue(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
) -> IssueActionPayload | JSONResponse:
    """Dismiss an open review issue."""
    return _apply(database, issue_id, body, ReviewAction.DISMISS)


@router.post("/{issue_id}/resolve-as-new-concept", response_model=IssueActionPayload)
def resolve_issue_as_new_concept(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
) -> IssueActionPayload | JSONResponse:
    """Resolve an issue by creating one concept and primary variant."""
    return _apply(database, issue_id, body, ReviewAction.RESOLVE_AS_NEW_CONCEPT)


@router.post("/{issue_id}/resolve-as-alias", response_model=IssueActionPayload)
def resolve_issue_as_alias(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
) -> IssueActionPayload | JSONResponse:
    """Resolve an issue by adding an alias variant."""
    return _apply(database, issue_id, body, ReviewAction.RESOLVE_AS_ALIAS)


@router.post("/{issue_id}/resolve-as-forbidden", response_model=IssueActionPayload)
def resolve_issue_as_forbidden(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
) -> IssueActionPayload | JSONResponse:
    """Resolve an issue by adding a forbidden variant."""
    return _apply(database, issue_id, body, ReviewAction.RESOLVE_AS_FORBIDDEN)


def _apply(
    database: DatabaseDep,
    issue_id: str,
    body: IssueActionBody,
    action: ReviewAction,
) -> IssueActionPayload | JSONResponse:
    try:
        result = ReviewService(database).apply_action(issue_id, _command(body, action))
    except ReviewServiceError as error:
        return _service_error(error)
    except sqlite3.OperationalError as error:
        return _database_error(error)
    return _action_payload(result)


def _command(body: IssueActionBody, action: ReviewAction) -> ReviewActionInput:
    return ReviewActionInput(
        action=action,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        term=body.term,
        definition=body.definition,
        concept_id=body.concept_id,
        variant=body.variant,
        reason=body.reason,
        source_concept_id=body.source_concept_id,
        target_concept_id=body.target_concept_id,
        relation_type=body.relation_type,
    )


def _action_payload(result: ReviewActionResult) -> IssueActionPayload:
    return IssueActionPayload(
        outcome=result.outcome,
        issue=_issue_payload(result.issue),
        conceptId=None if result.concept is None else result.concept.id,
        variantId=None if result.variant is None else result.variant.id,
        relationId=None if result.relation is None else result.relation.id,
    )


def _issue_payload(issue: TermIssue) -> IssuePayload:
    return IssuePayload(
        id=issue.id,
        issueType=issue.issue_type.value,
        status=issue.status.value,
        surface=issue.surface,
        evidence=tuple(_evidence_payload(evidence) for evidence in issue.evidence),
        createdAt=issue.created_at,
        candidateConceptId=issue.candidate_concept_id,
        targetConceptId=issue.target_concept_id,
        resolvedAt=issue.resolved_at,
        version=issue.version,
        appliedIdempotencyKey=issue.applied_idempotency_key,
    )


def _evidence_payload(evidence: IssueEvidence) -> EvidencePayload:
    return EvidencePayload(
        id=evidence.id,
        kind=evidence.kind.value,
        sourceDocumentId=evidence.source_document_id,
        quote=evidence.quote,
        confidence=evidence.confidence,
        chunkId=evidence.chunk_id,
        contextBefore=evidence.context_before,
        contextAfter=evidence.context_after,
    )


def _service_error(error: ReviewServiceError) -> JSONResponse:
    return error_response(_status_for_error(error.code), error.code.value, str(error))


def _database_error(error: sqlite3.OperationalError) -> JSONResponse:
    if is_sqlite_lock_error(error):
        return sqlite_lock_response()
    return error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "database_error",
        "The local glossary database could not complete the request.",
    )


def _status_for_error(code: ReviewServiceErrorCode) -> int:
    match code:
        case (
            ReviewServiceErrorCode.ISSUE_NOT_FOUND
            | ReviewServiceErrorCode.CONCEPT_NOT_FOUND
        ):
            return status.HTTP_404_NOT_FOUND
        case (
            ReviewServiceErrorCode.STALE_VERSION
            | ReviewServiceErrorCode.ISSUE_CLOSED
            | ReviewServiceErrorCode.DUPLICATE_TERM
        ):
            return status.HTTP_409_CONFLICT
        case (
            ReviewServiceErrorCode.INVALID_PAYLOAD
            | ReviewServiceErrorCode.INVALID_RELATION
        ):
            return status.HTTP_400_BAD_REQUEST
