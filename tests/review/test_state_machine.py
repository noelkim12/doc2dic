"""Review issue state machine tests."""

from doc2dic.services.review_state_machine import (
    IssueSnapshot,
    IssueStatus,
    ReviewAction,
    ReviewErrorCode,
    ReviewRequest,
    TransitionOutcome,
    plan_review_action,
)


def test_resolve_as_new_concept_when_issue_is_open_returns_creation_plan() -> None:
    """Given an open issue, when resolving, then a storage-free plan is returned."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=7)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_NEW_CONCEPT,
        expected_version=7,
        idempotency_key="idem-new-1",
        payload={"term": "stamina", "definition": "Dungeon entry resource."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.PLANNED
    assert result.error is None
    assert result.plan is not None
    assert result.plan.next_status is IssueStatus.RESOLVED
    assert result.plan.optimistic_lock_version == 7
    assert result.plan.idempotency_key == "idem-new-1"
    assert tuple(effect.effect_type for effect in result.plan.effects) == (
        "create_concept",
        "mark_issue_resolved",
    )


def test_dismiss_when_issue_is_open_returns_dismissal_plan() -> None:
    """Given an open issue, when dismissing, then dismissal is deterministic."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=2)
    request = ReviewRequest(
        action=ReviewAction.DISMISS,
        expected_version=2,
        idempotency_key="idem-dismiss-1",
        payload={"reason": "False positive."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.next_status is IssueStatus.DISMISSED
    assert tuple(effect.effect_type for effect in result.plan.effects) == (
        "mark_issue_dismissed",
    )


def test_duplicate_resolve_when_key_already_applied_returns_no_plan() -> None:
    """Given an applied key, when repeated, then no second creation is planned."""
    issue = IssueSnapshot(
        status=IssueStatus.RESOLVED,
        version=8,
        applied_idempotency_key="idem-new-1",
    )
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_NEW_CONCEPT,
        expected_version=7,
        idempotency_key="idem-new-1",
        payload={"term": "stamina", "definition": "Dungeon entry resource."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.ALREADY_APPLIED
    assert result.error is None
    assert result.plan is None
    assert result.status is IssueStatus.RESOLVED


def test_stale_version_when_issue_is_open_returns_stale_version_error() -> None:
    """Given an old version, when resolving, then optimistic locking rejects it."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=8)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_ALIAS,
        expected_version=7,
        idempotency_key="idem-alias-1",
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
    """Given missing action data, when resolving, then payload validation fails."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=1)
    request = ReviewRequest(
        action=ReviewAction.RESOLVE_AS_ALIAS,
        expected_version=1,
        idempotency_key="idem-alias-2",
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
        idempotency_key="idem-forbidden-1",
        payload={"concept_id": "concept-1", "variant": "bad-term"},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is ReviewErrorCode.ISSUE_CLOSED
    assert result.error.message == "Only open review issues can be changed."
    assert result.plan is None


def test_failed_issue_state_when_marked_failed_returns_failure_plan() -> None:
    """Given an open issue, when marking failed, then failure semantics are explicit."""
    issue = IssueSnapshot(status=IssueStatus.OPEN, version=3)
    request = ReviewRequest(
        action=ReviewAction.MARK_FAILED,
        expected_version=3,
        idempotency_key="idem-failed-1",
        payload={"reason": "Concept creation precondition failed."},
    )

    result = plan_review_action(issue, request)

    assert result.outcome is TransitionOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.next_status is IssueStatus.FAILED
    assert tuple(effect.effect_type for effect in result.plan.effects) == (
        "mark_issue_failed",
    )
