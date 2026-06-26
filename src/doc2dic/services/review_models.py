"""Review service input and result models."""

from dataclasses import dataclass
from enum import StrEnum

from doc2dic.domain import Concept, ConceptRelation, TermIssue, TermVariant
from doc2dic.services.review_state_machine import ReviewAction, ReviewErrorCode


class ReviewServiceErrorCode(StrEnum):
    """Boundary-safe review service error codes."""

    ISSUE_NOT_FOUND = "issue_not_found"
    STALE_VERSION = "stale_version"
    INVALID_PAYLOAD = "invalid_payload"
    ISSUE_CLOSED = "issue_closed"
    DUPLICATE_TERM = "duplicate_term"
    CONCEPT_NOT_FOUND = "concept_not_found"
    INVALID_RELATION = "invalid_relation"


class ReviewServiceError(RuntimeError):
    """Raised when a review action cannot be applied."""

    def __init__(self, code: ReviewServiceErrorCode, message: str) -> None:
        """Store deterministic error details for CLI and API boundaries."""
        super().__init__(message)
        self.code: ReviewServiceErrorCode
        self.code = code


@dataclass(frozen=True, slots=True)
class ReviewActionInput:
    """Parsed review action command."""

    action: ReviewAction
    expected_version: int
    idempotency_key: str
    term: str | None = None
    definition: str | None = None
    concept_id: str | None = None
    variant: str | None = None
    reason: str | None = None
    source_concept_id: str | None = None
    target_concept_id: str | None = None
    relation_type: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewActionResult:
    """Applied review action receipt."""

    issue: TermIssue
    outcome: str
    concept: Concept | None = None
    variant: TermVariant | None = None
    relation: ConceptRelation | None = None


def service_code_for_review_error(
    code: ReviewErrorCode,
) -> ReviewServiceErrorCode:
    """Map pure state-machine errors to service boundary errors."""
    match code:
        case ReviewErrorCode.STALE_VERSION:
            return ReviewServiceErrorCode.STALE_VERSION
        case ReviewErrorCode.INVALID_PAYLOAD:
            return ReviewServiceErrorCode.INVALID_PAYLOAD
        case ReviewErrorCode.ISSUE_CLOSED:
            return ReviewServiceErrorCode.ISSUE_CLOSED
