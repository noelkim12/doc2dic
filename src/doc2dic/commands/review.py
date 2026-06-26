"""Review command group."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.review_service import (
    ReviewActionInput,
    ReviewService,
    ReviewServiceError,
)
from doc2dic.services.review_state_machine import IssueStatus, ReviewAction
from doc2dic.storage import open_database

if TYPE_CHECKING:
    import sqlite3
    from contextlib import AbstractContextManager
    from types import TracebackType

app = typer.Typer(help="Review pending glossary issues.")


@app.callback()
def review() -> None:
    """Show review command group help."""


@app.command("list")
def list_issues(
    status: Annotated[
        IssueStatus | None,
        typer.Option("--status", help="Filter by review status."),
    ] = None,
) -> None:
    """List review issues."""
    with _review_service() as service:
        issues = service.list_issues(status=status)
    for issue in issues:
        typer.echo(f"{issue.id}\t{issue.status.value}\t{issue.surface}")


@app.command("show")
def show_issue(issue_id: Annotated[str, typer.Argument(help="Issue id.")]) -> None:
    """Show one review issue."""
    with _review_service() as service:
        issue = service.get_issue(issue_id)
    typer.echo(f"ID: {issue.id}")
    typer.echo(f"Type: {issue.issue_type.value}")
    typer.echo(f"Status: {issue.status.value}")
    typer.echo(f"Surface: {issue.surface}")
    typer.echo(f"Version: {issue.version}")


@app.command("dismiss")
def dismiss_issue(
    issue_id: Annotated[str, typer.Argument(help="Issue id.")],
    expected_version: Annotated[int, typer.Option("--expected-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    reason: Annotated[str, typer.Option("--reason")],
) -> None:
    """Dismiss an open issue."""
    _apply(
        issue_id,
        ReviewActionInput(
            ReviewAction.DISMISS,
            expected_version,
            idempotency_key,
            reason=reason,
        ),
    )


@app.command("resolve-as-new-concept")
def resolve_as_new_concept(
    issue_id: Annotated[str, typer.Argument(help="Issue id.")],
    expected_version: Annotated[int, typer.Option("--expected-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    term: Annotated[str, typer.Option("--term")],
    definition: Annotated[str, typer.Option("--definition")],
) -> None:
    """Resolve an issue by creating one concept."""
    _apply(
        issue_id,
        ReviewActionInput(
            ReviewAction.RESOLVE_AS_NEW_CONCEPT,
            expected_version,
            idempotency_key,
            term=term,
            definition=definition,
        ),
    )


@app.command("resolve-as-alias")
def resolve_as_alias(
    issue_id: Annotated[str, typer.Argument(help="Issue id.")],
    expected_version: Annotated[int, typer.Option("--expected-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    concept_id: Annotated[str, typer.Option("--concept-id")],
    variant: Annotated[str, typer.Option("--variant")],
) -> None:
    """Resolve an issue by adding an alias variant."""
    _apply(
        issue_id,
        ReviewActionInput(
            ReviewAction.RESOLVE_AS_ALIAS,
            expected_version,
            idempotency_key,
            concept_id=concept_id,
            variant=variant,
        ),
    )


@app.command("resolve-as-forbidden")
def resolve_as_forbidden(
    issue_id: Annotated[str, typer.Argument(help="Issue id.")],
    expected_version: Annotated[int, typer.Option("--expected-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    concept_id: Annotated[str, typer.Option("--concept-id")],
    variant: Annotated[str, typer.Option("--variant")],
) -> None:
    """Resolve an issue by adding a forbidden variant."""
    _apply(
        issue_id,
        ReviewActionInput(
            ReviewAction.RESOLVE_AS_FORBIDDEN,
            expected_version,
            idempotency_key,
            concept_id=concept_id,
            variant=variant,
        ),
    )


@app.command("resolve-as-relation")
def resolve_as_relation(  # noqa: PLR0913
    issue_id: Annotated[str, typer.Argument(help="Issue id.")],
    expected_version: Annotated[int, typer.Option("--expected-version")],
    idempotency_key: Annotated[str, typer.Option("--idempotency-key")],
    source_concept_id: Annotated[str, typer.Option("--source-concept-id")],
    target_concept_id: Annotated[str, typer.Option("--target-concept-id")],
    relation_type: Annotated[str, typer.Option("--relation-type")] = "related_to",
) -> None:
    """Resolve an issue by adding a concept relation."""
    _apply(
        issue_id,
        ReviewActionInput(
            ReviewAction.RESOLVE_AS_RELATION,
            expected_version,
            idempotency_key,
            source_concept_id=source_concept_id,
            target_concept_id=target_concept_id,
            relation_type=relation_type,
        ),
    )


def _apply(issue_id: str, command: ReviewActionInput) -> None:
    with _review_service() as service:
        result = service.apply_action(issue_id, command)
    typer.echo(f"Review action {result.outcome}: {result.issue.id}")


class _ReviewServiceContext:
    """Open the discovered project database for review commands."""

    def __init__(self) -> None:
        """Create an unopened review service context."""
        self._database: AbstractContextManager[sqlite3.Connection] | None = None

    def __enter__(self) -> ReviewService:
        """Open storage and return a review service bound to it."""
        try:
            state = discover_project(Path.cwd())
            self._database = open_database(state.db_path)
            connection = self._database.__enter__()
        except ProjectNotFoundError as error:
            typer.echo(str(error))
            raise typer.Exit(code=1) from error
        return ReviewService(connection)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close storage and convert user-facing review errors."""
        handled_error = exc_value if isinstance(exc_value, ReviewServiceError) else None
        if self._database is not None:
            _ = self._database.__exit__(exc_type, exc_value, traceback)
        if handled_error is not None:
            typer.echo(f"Error: {handled_error}", err=True)
            raise typer.Exit(code=1) from None


def _review_service() -> _ReviewServiceContext:
    return _ReviewServiceContext()
