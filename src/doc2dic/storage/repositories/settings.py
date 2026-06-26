"""Settings SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.storage.sqlite_rows import text_cell


class SettingsRepository:
    """Read and write project-local settings."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def set_value(self, key: str, value: str) -> None:
        """Persist a setting value."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into settings(key, value, updated_at)
                values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                on conflict(key) do update set
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (key, value),
            )

    def get_value(self, key: str) -> str | None:
        """Return a setting value by key."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select value from settings where key = ?",
                (key,),
            ).fetchone(),
        )
        if row is None:
            return None
        return text_cell(row, "value")
