"""Acceptance-path tests for the review issue state machine."""

from doc2dic.services.review_state_machine import (
    IssueSnapshot,
    IssueStatus,
    ReviewAction,
    ReviewErrorCode,
    ReviewRequest,
    TransitionOutcome,
    plan_review_action,
)


def test_allowed_resolve_action_when_open_returns_resolved_plan() -> None:
    """Given an open issue, when resolving, then a resolved plan is returned."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=7)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_NEW_CONCEPT,
        expected_version=7,
        idempotency_key="unit-new-1",
        payload={"term": "stamina", "definition": "Dungeon entry resource."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.PLANNED
    assert result.error is None
    assert result.plan is not None
    assert result.status is IssueStatus.RESOLVED
    assert result.plan.next_status is IssueStatus.RESOLVED
    assert result.plan.optimistic_lock_version == 7
    assert result.plan.idempotency_key == "unit-new-1"
    assert tuple(effect.effect_type for effect in result.plan.effects) == (
        "create_concept",
        "mark_issue_resolved",
    )


def test_duplicate_action_when_key_already_applied_returns_no_plan() -> None:
    """Given an applied key, when replayed, then duplicate work is not planned."""
    issue = IssueSnapshot(
        status=IssueStatus.RESOLVED,
        version=8,
        applied_idempotency_key="unit-new-1",
    )
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_NEW_CONCEPT,
        expected_version=7,
        idempotency_key="unit-new-1",
        payload={"term": "stamina", "definition": "Dungeon entry resource."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.ALREADY_APPLIED
    assert result.status is IssueStatus.RESOLVED
    assert result.error is None
    assert result.plan is None


def test_stale_version_when_open_returns_stale_version_error() -> None:
    """Given a stale version, when resolving, then optimistic locking rejects it."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=8)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_ALIAS,
        expected_version=7,
        idempotency_key="unit-alias-1",
        payload={"concept_id": "concept-1", "variant": "stam"},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is ReviewErrorCode.STALE_VERSION
    assert result.error.message == (
        "Issue version changed before this action was applied."
    )
    assert result.plan is None


def test_invalid_payload_when_required_field_missing_returns_payload_error() -> None:
    """Given missing action payload data, when resolving, then it is rejected."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=1)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_ALIAS,
        expected_version=1,
        idempotency_key="unit-alias-2",
        payload={"concept_id": "concept-1"},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is ReviewErrorCode.INVALID_PAYLOAD
    assert result.error.message == "Action payload is missing required fields: variant."
    assert result.plan is None


def test_dismissed_issue_when_mutated_returns_closed_issue_error() -> None:
    """Given a dismissed issue, when resolving, then mutation is refused."""
    issue = IssueSnapshot(status=IssueStatus.DISMISSED, version=4)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_FORBIDDEN,
        expected_version=4,
        idempotency_key="unit-forbidden-1",
        payload={"concept_id": "concept-1", "variant": "bad-term"},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is ReviewErrorCode.ISSUE_CLOSED
    assert result.error.message == "Only open review issues can be changed."
    assert result.plan is None
