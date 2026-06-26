"""Tool handlers for the doc2dic MCP server."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from doc2dic.context import build_explore_context
from doc2dic.mcp.guidance import (
    degraded_index_guidance,
    invalid_project_guidance,
    missing_project_guidance,
    status_guidance,
)
from doc2dic.mcp.schemas import ExploreToolInput, StatusToolInput
from doc2dic.storage.connection import DB_DIR_NAME, DB_FILE_NAME, open_database


def run_doc2dic_explore(query: str, project_path: str | Path | None = None) -> str:
    """Return terminology context or success-shaped guidance for expected gaps."""
    try:
        parsed = ExploreToolInput(
            query=query,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            return build_explore_context(
                parsed.query,
                connection=connection,
                project_root=paths.root,
            )
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)


def run_doc2dic_status(project_path: str | Path | None = None) -> str:
    """Return hidden diagnostic status for explicitly allowlisted operators."""
    try:
        parsed = StatusToolInput(
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))
    return status_guidance(paths.root, paths.db_path)


@dataclass(frozen=True, slots=True)
class _ProjectPaths:
    """Resolved project-local storage paths."""

    root: Path
    db_path: Path


def _project_paths(project_path: Path) -> _ProjectPaths:
    root = project_path.expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise OSError(project_path)
    return _ProjectPaths(root=root, db_path=root / DB_DIR_NAME / DB_FILE_NAME)
