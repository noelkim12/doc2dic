"""SQLite connection helpers for project-local storage."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from doc2dic.storage.migrations import migrate_database

DB_DIR_NAME: Final = ".doc2dic"
DB_FILE_NAME: Final = "glossary.sqlite3"
SQLITE_BUSY_TIMEOUT_MS: Final = 1000
SQLITE_CONNECT_TIMEOUT_SECONDS: Final = 1.0


@contextmanager
def open_database(db_path: Path) -> Generator[sqlite3.Connection]:
    """Open a configured SQLite connection.

    When the database file already exists, its schema is brought up to the
    latest version first so an older on-disk spec is migrated automatically on
    access. A missing database is never created here; callers that expect an
    initialized project guard for existence before opening.
    """
    if db_path.exists():
        _ = migrate_database(db_path)
    connection = sqlite3.connect(db_path, timeout=SQLITE_CONNECT_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    _ = connection.execute("pragma foreign_keys = on")
    _ = connection.execute("pragma journal_mode = wal")
    _ = connection.execute(f"pragma busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    try:
        yield connection
    finally:
        connection.close()


def initialize_project_storage(project_root: Path) -> Path:
    """Create `.doc2dic/glossary.sqlite3` under a project root and migrate it."""
    storage_dir = project_root / DB_DIR_NAME
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_path = storage_dir / DB_FILE_NAME
    _ = migrate_database(db_path)
    return db_path
