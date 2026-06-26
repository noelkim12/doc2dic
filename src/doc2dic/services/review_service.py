"""Transactional review queue service."""

import sqlite3
from datetime import UTC, datetime

from doc2dic.domain import TermIssue
from doc2dic.services.glossary_service import GlossaryService
from doc2dic.services.review_effects import apply_review_effect
from doc2dic.services.review_models import (
    ReviewActionInput,
    ReviewActionResult,
    ReviewServiceError,
    ReviewServiceErrorCode,
    service_code_for_review_error,
)
from doc2dic.services.review_state_machine import (
    IssueSnapshot,
    IssueStatus,
    ReviewRequest,
    TransitionOutcome,
    plan_review_action,
)
from doc2dic.storage.repositories.issues import IssueRepository

__all__ = [
    "ReviewActionInput",
    "ReviewActionResult",
    "ReviewService",
    "ReviewServiceError",
    "ReviewServiceErrorCode",
]


class ReviewService:
    """Coordinate review state, glossary effects, and idempotency."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store repository and glossary collaborators."""
        self._connection: sqlite3.Connection
        self._issues: IssueRepository
        self._glossary: GlossaryService
        self._connection = connection
        self._issues = IssueRepository(connection)
        self._glossary = GlossaryService(connection)

    def list_issues(
        self,
        *,
        status: IssueStatus | None = None,
    ) -> tuple[TermIssue, ...]:
        """List review issues, optionally filtered by state."""
        return self._issues.list_issues(status=status)

    def get_issue(self, issue_id: str) -> TermIssue:
        """Return one review issue or raise a typed not-found error."""
        issue = self._issues.get_issue(issue_id)
        if issue is None:
            raise ReviewServiceError(
                ReviewServiceErrorCode.ISSUE_NOT_FOUND,
                f"issue not found: {issue_id}",
            )
        return issue

    def apply_action(
        self,
        issue_id: str,
        command: ReviewActionInput,
    ) -> ReviewActionResult:
        """Apply one human review action in one short SQLite transaction."""
        with self._connection:
            issue = self.get_issue(issue_id)
            transition = plan_review_action(
                _snapshot(issue),
                ReviewRequest(
                    action=command.action,
                    expected_version=command.expected_version,
                    idempotency_key=command.idempotency_key,
                    payload=_payload(command),
                ),
            )
            match transition.outcome:
                case TransitionOutcome.ALREADY_APPLIED:
                    return ReviewActionResult(issue=issue, outcome="already_applied")
                case TransitionOutcome.REJECTED:
                    if transition.error is None:
                        message = "rejected transition must include an error"
                        raise AssertionError(message)
                    raise ReviewServiceError(
                        service_code_for_review_error(transition.error.code),
                        transition.error.message,
                    )
                case TransitionOutcome.PLANNED:
                    _ = self._connection.execute(
                        "update term_issues set version = version where id = ?",
                        (issue_id,),
                    )
                    result = apply_review_effect(self._glossary, command)
                    applied = issue.model_copy(
                        update={
                            "status": transition.status,
                            "resolved_at": _now(),
                            "version": issue.version + 1,
                            "applied_idempotency_key": command.idempotency_key,
                        },
                    )
                    self._mark_issue_applied(applied)
                    return ReviewActionResult(
                        issue=applied,
                        outcome="applied",
                        concept=result.concept,
                        variant=result.variant,
                        relation=result.relation,
                    )

    def _mark_issue_applied(self, issue: TermIssue) -> None:
        _ = self._connection.execute(
            """
            update term_issues
            set status = ?, resolved_at = ?, version = ?, applied_idempotency_key = ?
            where id = ?
            """,
            (
                issue.status.value,
                issue.resolved_at,
                issue.version,
                issue.applied_idempotency_key,
                issue.id,
            ),
        )


def _payload(command: ReviewActionInput) -> dict[str, str]:
    values = {
        "term": command.term,
        "definition": command.definition,
        "concept_id": command.concept_id,
        "variant": command.variant,
        "reason": command.reason,
        "source_concept_id": command.source_concept_id,
        "target_concept_id": command.target_concept_id,
        "relation_type": command.relation_type,
    }
    return {key: value for key, value in values.items() if value is not None}


def _snapshot(issue: TermIssue) -> IssueSnapshot:
    return IssueSnapshot(
        status=issue.status,
        version=issue.version,
        applied_idempotency_key=issue.applied_idempotency_key,
    )


def _now() -> str:
    return (
        datetime.now(tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
