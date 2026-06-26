"""Project-local state helpers for CLI command modules."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from doc2dic.storage.connection import DB_DIR_NAME, DB_FILE_NAME, open_database
from doc2dic.storage.sqlite_rows import int_cell, require_row

CONFIG_FILE_NAME: Final = "config.toml"
CONFIG_TEMPLATE: Final = """[project]\nname = \"doc2dic\"\nschema_version = 1\n"""

if TYPE_CHECKING:
    import sqlite3


class ProjectNotFoundError(RuntimeError):
    """Raised when a command requires an initialized doc2dic project."""


@dataclass(frozen=True, slots=True)
class ProjectState:
    """Resolved project-local doc2dic paths."""

    root: Path
    storage_dir: Path
    config_path: Path
    db_path: Path


@dataclass(frozen=True, slots=True)
class StorageStatus:
    """Observable storage state for the status command."""

    schema_version: int
    concept_count: int
    issue_count: int


def state_for_root(project_root: Path) -> ProjectState:
    """Build project state paths for an explicit root."""
    storage_dir = project_root / DB_DIR_NAME
    return ProjectState(
        root=project_root,
        storage_dir=storage_dir,
        config_path=storage_dir / CONFIG_FILE_NAME,
        db_path=storage_dir / DB_FILE_NAME,
    )


def discover_project(start: Path) -> ProjectState:
    """Find the nearest initialized project at or above a start directory."""
    for candidate in (start, *start.parents):
        state = state_for_root(candidate)
        if state.config_path.exists() or state.db_path.exists():
            return state
    message = "No doc2dic project found. Run `doc2dic init` in the project root."
    raise ProjectNotFoundError(message)


def ensure_config_file(state: ProjectState, *, force: bool) -> None:
    """Create the project config file when missing or force is requested."""
    state.storage_dir.mkdir(parents=True, exist_ok=True)
    if force or not state.config_path.exists():
        _ = state.config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")


def read_storage_status(state: ProjectState) -> StorageStatus:
    """Read the current migration and glossary counts from storage."""
    if not state.db_path.exists():
        message = "Doc2Dic database is missing. Run `doc2dic init` to create it."
        raise ProjectNotFoundError(message)
    with open_database(state.db_path) as connection:
        schema_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select max(version) as version from schema_migrations",
            ).fetchone(),
        )
        concept_row = cast(
            "sqlite3.Row | None",
            connection.execute("select count(*) as count from concepts").fetchone(),
        )
        issue_row = cast(
            "sqlite3.Row | None",
            connection.execute("select count(*) as count from term_issues").fetchone(),
        )
    return StorageStatus(
        schema_version=int_cell(require_row(schema_row), "version"),
        concept_count=int_cell(require_row(concept_row), "count"),
        issue_count=int_cell(require_row(issue_row), "count"),
    )
