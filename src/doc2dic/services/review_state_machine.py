"""Pure review issue state machine.

The plan sketch listed ``accepted`` as a possible issue status, but later CLI/API
sections describe acceptance as an action. This module intentionally removes
``accepted`` from persisted issue state: accepted review actions produce an
explicit ``resolved`` plan, while ``dismissed`` and ``failed`` are terminal
applied states.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field


class IssueStatus(StrEnum):
    """Stored review issue statuses."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    FAILED = "failed"


class ReviewAction(StrEnum):
    """Human review actions supported by the state machine."""

    RESOLVE_AS_EXISTING_CONCEPT = "resolve_as_existing_concept"
    RESOLVE_AS_ALIAS = "resolve_as_alias"
    RESOLVE_AS_FORBIDDEN = "resolve_as_forbidden"
    RESOLVE_AS_DEPRECATED = "resolve_as_deprecated"
    RESOLVE_AS_NEW_CONCEPT = "resolve_as_new_concept"
    RESOLVE_AS_RELATION = "resolve_as_relation"
    DISMISS = "dismiss"
    MARK_FAILED = "mark_failed"


class TransitionOutcome(StrEnum):
    """Top-level transition result categories."""

    PLANNED = "planned"
    ALREADY_APPLIED = "already_applied"
    REJECTED = "rejected"


class ReviewErrorCode(StrEnum):
    """Deterministic state-machine error codes."""

    STALE_VERSION = "stale_version"
    INVALID_PAYLOAD = "invalid_payload"
    ISSUE_CLOSED = "issue_closed"


class IssueSnapshot(BaseModel):
    """Storage-independent issue state read by the state machine."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: IssueStatus
    version: int = Field(ge=0)
    applied_idempotency_key: str | None = Field(default=None, min_length=1)


class ReviewRequest(BaseModel):
    """Human review action request parsed before mutation planning."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    action: ReviewAction
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1)
    payload: dict[str, str] = Field(default_factory=dict)


class ReviewError(BaseModel):
    """Deterministic rejection detail."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    code: ReviewErrorCode
    message: str


class PlannedEffect(BaseModel):
    """Storage-independent effect descriptor for a later mutation layer."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    effect_type: str
    payload: dict[str, str] = Field(default_factory=dict)


class ActionPlan(BaseModel):
    """Optimistic-lock mutation plan without executing any mutation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    next_status: IssueStatus
    optimistic_lock_version: int
    idempotency_key: str
    effects: tuple[PlannedEffect, ...]


class TransitionResult(BaseModel):
    """Result of pure review action planning."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    outcome: TransitionOutcome
    status: IssueStatus
    plan: ActionPlan | None = None
    error: ReviewError | None = None


@dataclass(frozen=True, slots=True)
class _ActionSpec:
    next_status: IssueStatus
    effect_types: tuple[str, ...]
    required_fields: frozenset[str]


_STALE_VERSION_MESSAGE: Final = "Issue version changed before this action was applied."
_CLOSED_ISSUE_MESSAGE: Final = "Only open review issues can be changed."
_ACTION_SPECS: Final = {
    ReviewAction.RESOLVE_AS_EXISTING_CONCEPT: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("link_existing_concept", "mark_issue_resolved"),
        required_fields=frozenset({"concept_id"}),
    ),
    ReviewAction.RESOLVE_AS_ALIAS: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("create_alias_variant", "mark_issue_resolved"),
        required_fields=frozenset({"concept_id", "variant"}),
    ),
    ReviewAction.RESOLVE_AS_FORBIDDEN: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("create_forbidden_variant", "mark_issue_resolved"),
        required_fields=frozenset({"concept_id", "variant"}),
    ),
    ReviewAction.RESOLVE_AS_DEPRECATED: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("create_deprecated_variant", "mark_issue_resolved"),
        required_fields=frozenset({"concept_id", "variant"}),
    ),
    ReviewAction.RESOLVE_AS_NEW_CONCEPT: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("create_concept", "mark_issue_resolved"),
        required_fields=frozenset({"term", "definition"}),
    ),
    ReviewAction.RESOLVE_AS_RELATION: _ActionSpec(
        next_status=IssueStatus.RESOLVED,
        effect_types=("create_relation", "mark_issue_resolved"),
        required_fields=frozenset(
            {"source_concept_id", "target_concept_id", "relation_type"},
        ),
    ),
    ReviewAction.DISMISS: _ActionSpec(
        next_status=IssueStatus.DISMISSED,
        effect_types=("mark_issue_dismissed",),
        required_fields=frozenset({"reason"}),
    ),
    ReviewAction.MARK_FAILED: _ActionSpec(
        next_status=IssueStatus.FAILED,
        effect_types=("mark_issue_failed",),
        required_fields=frozenset({"reason"}),
    ),
}
_CLOSED_ERRORS: Final = {
    IssueStatus.OPEN: None,
    IssueStatus.RESOLVED: ReviewError(
        code=ReviewErrorCode.ISSUE_CLOSED,
        message=_CLOSED_ISSUE_MESSAGE,
    ),
    IssueStatus.DISMISSED: ReviewError(
        code=ReviewErrorCode.ISSUE_CLOSED,
        message=_CLOSED_ISSUE_MESSAGE,
    ),
    IssueStatus.FAILED: ReviewError(
        code=ReviewErrorCode.ISSUE_CLOSED,
        message=_CLOSED_ISSUE_MESSAGE,
    ),
}


def plan_review_action(
    issue: IssueSnapshot,
    request: ReviewRequest,
) -> TransitionResult:
    """Plan a review action without touching storage."""
    if issue.applied_idempotency_key == request.idempotency_key:
        return TransitionResult(
            outcome=TransitionOutcome.ALREADY_APPLIED,
            status=issue.status,
        )

    closed_error = _closed_issue_error(issue.status)
    if closed_error is not None:
        return TransitionResult(
            outcome=TransitionOutcome.REJECTED,
            status=issue.status,
            error=closed_error,
        )

    if issue.version != request.expected_version:
        return TransitionResult(
            outcome=TransitionOutcome.REJECTED,
            status=issue.status,
            error=ReviewError(
                code=ReviewErrorCode.STALE_VERSION,
                message=_STALE_VERSION_MESSAGE,
            ),
        )

    spec = _action_spec(request.action)
    payload_error = _payload_error(spec, request.payload)
    if payload_error is not None:
        return TransitionResult(
            outcome=TransitionOutcome.REJECTED,
            status=issue.status,
            error=payload_error,
        )

    return TransitionResult(
        outcome=TransitionOutcome.PLANNED,
        status=spec.next_status,
        plan=ActionPlan(
            next_status=spec.next_status,
            optimistic_lock_version=issue.version,
            idempotency_key=request.idempotency_key,
            effects=_planned_effects(spec, request.payload),
        ),
    )


def _closed_issue_error(status: IssueStatus) -> ReviewError | None:
    return _CLOSED_ERRORS[status]


def _action_spec(action: ReviewAction) -> _ActionSpec:
    return _ACTION_SPECS[action]


def _payload_error(spec: _ActionSpec, payload: dict[str, str]) -> ReviewError | None:
    missing_fields = tuple(
        sorted(field for field in spec.required_fields if field not in payload)
    )
    if len(missing_fields) == 0:
        return None

    message = f"Action payload is missing required fields: {', '.join(missing_fields)}."
    return ReviewError(
        code=ReviewErrorCode.INVALID_PAYLOAD,
        message=message,
    )


def _planned_effects(
    spec: _ActionSpec,
    payload: dict[str, str],
) -> tuple[PlannedEffect, ...]:
    return tuple(
        PlannedEffect(effect_type=effect_type, payload=payload)
        for effect_type in spec.effect_types
    )


__all__ = [
    "ActionPlan",
    "IssueSnapshot",
    "IssueStatus",
    "PlannedEffect",
    "ReviewAction",
    "ReviewError",
    "ReviewErrorCode",
    "ReviewRequest",
    "TransitionOutcome",
    "TransitionResult",
    "plan_review_action",
]
