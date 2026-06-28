"""Idempotent SQLite migrations for doc2dic storage."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, cast

from doc2dic.storage.sqlite_rows import (
    int_cell,
    optional_int_cell,
    require_row,
    text_cell,
)

LATEST_SCHEMA_VERSION: Final = 4
MANAGED_TABLES: Final = frozenset(
    {
        "concepts",
        "term_variants",
        "tags",
        "concept_tags",
        "concept_relations",
        "documents",
        "document_chunks",
        "term_occurrences",
        "term_issues",
        "issue_evidence",
        "embeddings",
        "embedding_vectors",
        "graph_snapshots",
        "jobs",
        "schema_migrations",
        "settings",
        "search_index_metadata",
        "concept_search_fts",
        "document_search_fts",
        "issue_search_fts",
        "evidence_search_fts",
    },
)


class MigrationStateError(RuntimeError):
    """Raised when a database migration state cannot be upgraded safely."""


class CorruptMigrationError(RuntimeError):
    """Raised when an applied migration record no longer matches code."""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Migration execution receipt."""

    db_path: Path
    applied_versions: tuple[int, ...]
    current_version: int
    journal_mode: str


@dataclass(frozen=True, slots=True)
class MigrationDefinition:
    """Versioned SQL migration stored alongside this module."""

    version: int
    name: str
    filename: str

    def script(self) -> str:
        """Return this migration's SQL script."""
        return Path(__file__).with_name(self.filename).read_text(encoding="utf-8")

    def checksum(self) -> str:
        """Return this migration's source checksum."""
        return _checksum(self.script())


MIGRATIONS: Final = (
    MigrationDefinition(1, "initial_storage_schema", "schema.sql"),
    MigrationDefinition(2, "search_schema", "search_schema.sql"),
    MigrationDefinition(3, "issue_search_schema", "issue_search_schema.sql"),
    MigrationDefinition(4, "concept_source_schema", "concept_source_schema.sql"),
)


def migrate_database(db_path: Path) -> MigrationResult:
    """Apply storage migrations and return the versions applied in this run."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrations_by_version = _migrations_by_version()
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ = connection.execute("pragma foreign_keys = on")
        journal_row = cast(
            "sqlite3.Row | None",
            connection.execute("pragma journal_mode = wal").fetchone(),
        )
        journal_mode = text_cell(require_row(journal_row), "journal_mode")
        _reject_legacy_state(connection)
        _ensure_migration_table(connection)
        _verify_applied_migrations(connection, migrations_by_version)

        applied_versions = _apply_pending_migrations(connection)

        current_version = _current_version(connection)
    return MigrationResult(
        db_path=db_path,
        applied_versions=applied_versions,
        current_version=current_version,
        journal_mode=journal_mode,
    )

def _checksum(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _migrations_by_version() -> Mapping[int, MigrationDefinition]:
    return {migration.version: migration for migration in MIGRATIONS}


def _reject_legacy_state(connection: sqlite3.Connection) -> None:
    tables = _table_names(connection)
    if "schema_migrations" not in tables and len(tables & MANAGED_TABLES) > 0:
        message = "old migration state lacks schema_migrations; refusing partial apply"
        raise MigrationStateError(message)


def _table_names(connection: sqlite3.Connection) -> frozenset[str]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select name from sqlite_master where type = 'table'",
        ).fetchall(),
    )
    return frozenset(text_cell(row, "name") for row in rows)


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    _ = connection.execute(
        """
        create table if not exists schema_migrations (
          version integer primary key,
          name text not null,
          checksum text not null,
          applied_at text not null
        )
        """,
    )


def _verify_applied_migrations(
    connection: sqlite3.Connection,
    migrations_by_version: Mapping[int, MigrationDefinition],
) -> None:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select version, checksum from schema_migrations order by version",
        ).fetchall(),
    )
    for row in rows:
        version = int_cell(row, "version")
        migration = migrations_by_version.get(version)
        if migration is None:
            message = "database schema is newer than this application"
            raise MigrationStateError(message)
        if text_cell(row, "checksum") != migration.checksum():
            message = f"schema migration checksum mismatch for version {version}"
            raise CorruptMigrationError(message)


def _has_version(connection: sqlite3.Connection, version: int) -> bool:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select 1 from schema_migrations where version = ?",
            (version,),
        ).fetchone(),
    )
    return row is not None


def _apply_pending_migrations(connection: sqlite3.Connection) -> tuple[int, ...]:
    applied_versions: list[int] = []
    for migration in MIGRATIONS:
        if not _has_version(connection, migration.version):
            _apply_migration(connection, migration)
            applied_versions.append(migration.version)
    return tuple(applied_versions)


def _apply_migration(
    connection: sqlite3.Connection,
    migration: MigrationDefinition,
) -> None:
    with connection:
        for statement in _statements(migration.script()):
            _ = connection.execute(statement)
        _ = connection.execute(
            """
            insert into schema_migrations(version, name, checksum, applied_at)
            values (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            """,
            (migration.version, migration.name, migration.checksum()),
        )
        if migration.version == 1:
            _seed_initial_settings(connection)


def _seed_initial_settings(connection: sqlite3.Connection) -> None:
    _ = connection.execute(
        """
        insert or ignore into settings(key, value, updated_at)
        values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        """,
        ("app_name", "doc2dic"),
    )
    _ = connection.execute(
        """
        insert or ignore into settings(key, value, updated_at)
        values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        """,
        ("embedding_vectors_enabled", "false"),
    )


def _statements(script: str) -> tuple[str, ...]:
    return tuple(
        statement.strip() for statement in script.split(";") if statement.strip()
    )


def _current_version(connection: sqlite3.Connection) -> int:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select max(version) as version from schema_migrations",
        ).fetchone(),
    )
    version = optional_int_cell(require_row(row), "version")
    if version is None:
        return 0
    return version
