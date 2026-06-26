"""SQLite concurrency and lock-message integration checks."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, cast

import pytest

from doc2dic.server.errors import is_sqlite_lock_error, sqlite_lock_response
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.sqlite_rows import require_row, text_cell

if TYPE_CHECKING:
    from pathlib import Path


def test_migration_and_open_database_use_wal_with_short_busy_timeout(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"

    migration = migrate_database(db_path)
    with open_database(db_path) as connection:
        journal_row = cast(
            "sqlite3.Row | None",
            connection.execute("pragma journal_mode").fetchone(),
        )
        timeout_row = cast(
            "sqlite3.Row | None",
            connection.execute("pragma busy_timeout").fetchone(),
        )

    journal_mode = text_cell(require_row(journal_row), "journal_mode")
    busy_timeout = cast("int", require_row(timeout_row)[0])

    assert migration.journal_mode == "wal"
    assert journal_mode == "wal"
    assert busy_timeout == 1000


def test_sqlite_write_lock_reports_friendly_bounded_api_error(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as first, open_database(db_path) as second:
        _ = first.execute("begin immediate")
        try:
            sql = (
                "insert into settings(key, value, updated_at) values "
                "('lock_probe', 'value', '2026-06-26T00:00:00Z')"
            )
            with pytest.raises(sqlite3.OperationalError) as raised:
                _ = second.execute(
                    sql,
                )
        finally:
            first.rollback()

    assert is_sqlite_lock_error(raised.value)
    response = sqlite_lock_response()
    expected_body = (
        '{"error":{"code":"database_locked","message":"The local glossary '
        'database is busy. Retry the request shortly."}}'
    )

    assert response.status_code == 503
    assert bytes(response.body).decode("utf-8") == expected_body
