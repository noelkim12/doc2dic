"""FastAPI dependencies for the project-local API."""

import sqlite3
from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from doc2dic.storage import initialize_project_storage, open_database


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    """Resolved local project settings for the API process."""

    project_root: Path
    db_path: Path


def make_project_settings(project_root: Path) -> ProjectSettings:
    """Resolve storage settings for one local project root."""
    resolved_root = project_root.resolve()
    return ProjectSettings(
        project_root=resolved_root,
        db_path=initialize_project_storage(resolved_root),
    )


@lru_cache(maxsize=1)
def get_project_settings() -> ProjectSettings:
    """Return settings for the current working directory project."""
    return make_project_settings(Path.cwd())


ProjectSettingsDep = Annotated[ProjectSettings, Depends(get_project_settings)]


def get_database(
    settings: ProjectSettingsDep,
) -> Generator[sqlite3.Connection]:
    """Yield a SQLite connection for the current project database."""
    with open_database(settings.db_path) as connection:
        yield connection


DatabaseDep = Annotated[sqlite3.Connection, Depends(get_database)]
