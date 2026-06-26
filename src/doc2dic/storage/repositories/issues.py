"""Review issue SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.domain import IssueEvidence, IssueEvidenceKind, TermIssue, TermIssueType
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage.sqlite_rows import (
    float_cell,
    int_cell,
    optional_text_cell,
    text_cell,
)


class IssueRepository:
    """Persist review queue issues and evidence."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def upsert_issue(self, issue: TermIssue) -> None:
        """Insert or replace a term issue and its evidence."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into term_issues(
                  id, issue_type, status, surface, candidate_concept_id,
                  target_concept_id, created_at, resolved_at, version,
                  applied_idempotency_key
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  issue_type = excluded.issue_type,
                  status = excluded.status,
                  surface = excluded.surface,
                  candidate_concept_id = excluded.candidate_concept_id,
                  target_concept_id = excluded.target_concept_id,
                  resolved_at = excluded.resolved_at,
                  version = excluded.version,
                  applied_idempotency_key = excluded.applied_idempotency_key
                """,
                (
                    issue.id,
                    issue.issue_type.value,
                    issue.status.value,
                    issue.surface,
                    issue.candidate_concept_id,
                    issue.target_concept_id,
                    issue.created_at,
                    issue.resolved_at,
                    issue.version,
                    issue.applied_idempotency_key,
                ),
            )
            _ = self._connection.execute(
                "delete from issue_evidence where issue_id = ?",
                (issue.id,),
            )
            for evidence in issue.evidence:
                self._insert_evidence(issue.id, evidence)

    def get_issue(self, issue_id: str) -> TermIssue | None:
        """Return an issue and its evidence by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from term_issues where id = ?",
                (issue_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        evidence_rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                "select * from issue_evidence where issue_id = ? order by id",
                (issue_id,),
            ).fetchall(),
        )
        return TermIssue(
            id=text_cell(row, "id"),
            issue_type=TermIssueType(text_cell(row, "issue_type")),
            status=IssueStatus(text_cell(row, "status")),
            surface=text_cell(row, "surface"),
            candidate_concept_id=optional_text_cell(row, "candidate_concept_id"),
            target_concept_id=optional_text_cell(row, "target_concept_id"),
            evidence=tuple(_evidence_from_row(evidence) for evidence in evidence_rows),
            created_at=text_cell(row, "created_at"),
            resolved_at=optional_text_cell(row, "resolved_at"),
            version=int_cell(row, "version"),
            applied_idempotency_key=optional_text_cell(
                row,
                "applied_idempotency_key",
            ),
        )

    def list_issues(
        self,
        *,
        status: IssueStatus | None = None,
    ) -> tuple[TermIssue, ...]:
        """Return issues with evidence, optionally filtered by status."""
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                _list_issues_sql(status),
                () if status is None else (status.value,),
            ).fetchall(),
        )
        return tuple(
            _require_issue(self.get_issue(text_cell(row, "id"))) for row in rows
        )

    def _insert_evidence(self, issue_id: str, evidence: IssueEvidence) -> None:
        _ = self._connection.execute(
            """
            insert into issue_evidence(
              id, issue_id, kind, source_document_id, chunk_id, quote,
              context_before, context_after, confidence
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.id,
                issue_id,
                evidence.kind.value,
                evidence.source_document_id,
                evidence.chunk_id,
                evidence.quote,
                evidence.context_before,
                evidence.context_after,
                evidence.confidence,
            ),
        )

def _list_issues_sql(status: IssueStatus | None) -> str:
    sql = "select id from term_issues"
    if status is not None:
        sql = f"{sql} where status = ?"
    return f"{sql} order by created_at, id"


def _require_issue(issue: TermIssue | None) -> TermIssue:
    if issue is None:
        msg = "expected issue row"
        raise LookupError(msg)
    return issue


def _evidence_from_row(row: sqlite3.Row) -> IssueEvidence:
    return IssueEvidence(
        id=text_cell(row, "id"),
        kind=IssueEvidenceKind(text_cell(row, "kind")),
        source_document_id=text_cell(row, "source_document_id"),
        chunk_id=optional_text_cell(row, "chunk_id"),
        quote=text_cell(row, "quote"),
        context_before=text_cell(row, "context_before"),
        context_after=text_cell(row, "context_after"),
        confidence=float_cell(row, "confidence"),
    )
