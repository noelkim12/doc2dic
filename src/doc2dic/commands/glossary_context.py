"""CLI context helpers for glossary command modules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.glossary_embeddings import ProjectGlossaryEmbeddingIndexer
from doc2dic.services.glossary_service import GlossaryError, GlossaryService
from doc2dic.storage import open_database

if TYPE_CHECKING:
    import sqlite3
    from contextlib import AbstractContextManager
    from types import TracebackType


class GlossaryServiceContext:
    """Open the discovered project database for one CLI command."""

    def __init__(self) -> None:
        """Create an unopened service context."""
        self._connection: sqlite3.Connection | None = None
        self._database: AbstractContextManager[sqlite3.Connection] | None = None

    def __enter__(self) -> GlossaryService:
        """Open storage and return a service bound to it."""
        try:
            state = discover_project(Path.cwd())
            self._database = open_database(state.db_path)
            self._connection = self._database.__enter__()
        except ProjectNotFoundError as error:
            typer.echo(str(error))
            raise typer.Exit(code=1) from error
        return GlossaryService(
            self._connection,
            ProjectGlossaryEmbeddingIndexer(self._connection),
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the storage context."""
        handled_error = exc_value if isinstance(exc_value, GlossaryError) else None
        if self._database is None:
            if handled_error is not None:
                typer.echo(f"Error: {handled_error}", err=True)
                raise typer.Exit(code=1) from None
            return
        _ = self._database.__exit__(exc_type, exc_value, traceback)
        if handled_error is not None:
            typer.echo(f"Error: {handled_error}", err=True)
            raise typer.Exit(code=1) from None


def glossary_service() -> GlossaryServiceContext:
    """Return a context manager for CLI glossary work."""
    return GlossaryServiceContext()
