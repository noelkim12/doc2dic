from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from doc2dic.storage.connection import initialize_project_storage, open_database
from doc2dic.storage.migrations import (
    CorruptMigrationError,
    MigrationStateError,
    migrate_database,
)
from doc2dic.storage.sqlite_rows import int_cell, require_row, text_cell

if TYPE_CHECKING:
    import sqlite3


SEARCH_TABLES = {
    "search_index_metadata",
    "concept_search_fts",
    "document_search_fts",
    "issue_search_fts",
    "evidence_search_fts",
}


def _table_names(connection: "sqlite3.Connection") -> set[str]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select name from sqlite_master where type = 'table'",
        ).fetchall(),
    )
    return {text_cell(row, "name") for row in rows}


def _migration_versions(connection: "sqlite3.Connection") -> list[int]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select version from schema_migrations order by version",
        ).fetchall(),
    )
    return [int_cell(row, "version") for row in rows]


def _create_v1_database(db_path: Path) -> None:
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        _ = connection.execute("delete from schema_migrations where version > 1")
        _ = connection.execute("drop table if exists search_index_metadata")
        _ = connection.execute("drop table if exists concept_search_fts")
        _ = connection.execute("drop table if exists document_search_fts")
        _ = connection.execute("drop table if exists issue_search_fts")
        _ = connection.execute("drop table if exists evidence_search_fts")
        _ = connection.execute("alter table concepts drop column source_document")
        connection.commit()


def _create_v2_database(db_path: Path) -> None:
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        _ = connection.execute("delete from schema_migrations where version > 2")
        _ = connection.execute("drop table if exists issue_search_fts")
        _ = connection.execute("drop table if exists evidence_search_fts")
        _ = connection.execute("alter table concepts drop column source_document")
        connection.commit()


def test_migrations_when_run_twice_are_idempotent_and_enable_wal(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"

    first = migrate_database(db_path)
    second = migrate_database(db_path)

    with open_database(db_path) as connection:
        tables = _table_names(connection)
        journal_row = cast(
            "sqlite3.Row | None",
            connection.execute("pragma journal_mode").fetchone(),
        )
        journal_mode = text_cell(require_row(journal_row), "journal_mode")
        settings_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select count(*) as settings_count from settings",
            ).fetchone(),
        )
        settings_count = int_cell(require_row(settings_row), "settings_count")

    assert first.applied_versions == (1, 2, 3, 4)
    assert second.applied_versions == ()
    assert {
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
    }.issubset(tables)
    assert journal_mode == "wal"
    assert settings_count >= 2


def test_migrations_when_fresh_database_created_apply_latest_search_schema(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"

    result = migrate_database(db_path)

    with open_database(db_path) as connection:
        tables = _table_names(connection)
        versions = _migration_versions(connection)

    assert result.current_version == 4
    assert result.applied_versions == (1, 2, 3, 4)
    assert versions == [1, 2, 3, 4]
    assert SEARCH_TABLES.issubset(tables)


def test_migrations_when_v1_database_exists_upgrade_to_search_schema(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _create_v1_database(db_path)

    result = migrate_database(db_path)

    with open_database(db_path) as connection:
        tables = _table_names(connection)
        versions = _migration_versions(connection)

    assert result.current_version == 4
    assert result.applied_versions == (2, 3, 4)
    assert versions == [1, 2, 3, 4]
    assert SEARCH_TABLES.issubset(tables)


def test_migrations_when_v2_database_exists_upgrade_to_issue_search_schema(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _create_v2_database(db_path)

    result = migrate_database(db_path)

    with open_database(db_path) as connection:
        tables = _table_names(connection)
        versions = _migration_versions(connection)

    assert result.current_version == 4
    assert result.applied_versions == (3, 4)
    assert versions == [1, 2, 3, 4]
    assert SEARCH_TABLES.issubset(tables)


def _concept_columns(connection: "sqlite3.Connection") -> set[str]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute("pragma table_info(concepts)").fetchall(),
    )
    return {text_cell(row, "name") for row in rows}


def test_migrations_when_fresh_database_created_add_source_document_column(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"

    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        columns = _concept_columns(connection)

    assert "source_document" in columns


def test_migrations_when_v2_database_exists_upgrade_adds_source_document(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _create_v2_database(db_path)

    result = migrate_database(db_path)

    with open_database(db_path) as connection:
        columns = _concept_columns(connection)

    assert result.current_version == 4
    assert "source_document" in columns


def test_open_database_upgrades_existing_old_schema_on_access(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    # Simulate an older on-disk spec missing the v4 source_document column.
    with open_database(db_path) as connection:
        _ = connection.execute("alter table concepts drop column source_document")
        _ = connection.execute("delete from schema_migrations where version = 4")
        connection.commit()

    # Opening the existing database auto-migrates it back to the latest schema.
    with open_database(db_path) as connection:
        columns = _concept_columns(connection)
        versions = _migration_versions(connection)

    assert "source_document" in columns
    assert versions == [1, 2, 3, 4]


def test_open_database_does_not_create_a_missing_project_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite3"

    # Opening a non-existent path must not run migrations (no schema seeded).
    with open_database(db_path) as connection:
        tables = _table_names(connection)

    assert "schema_migrations" not in tables
    assert "concepts" not in tables


def test_migrations_when_checksum_changes_raise_corrupt_error(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        _ = connection.execute(
            "update schema_migrations set checksum = ? where version = ?",
            ("bad", 1),
        )
        connection.commit()

    with pytest.raises(CorruptMigrationError, match="checksum mismatch"):
        _ = migrate_database(db_path)


def test_migrations_when_database_is_newer_raise_state_error(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        _ = connection.execute(
            """
            insert into schema_migrations(version, name, checksum, applied_at)
            values (?, ?, ?, ?)
            """,
            (999, "future", "checksum", "2026-06-25T00:00:00Z"),
        )
        connection.commit()

    with pytest.raises(MigrationStateError, match="newer than this application"):
        _ = migrate_database(db_path)


def test_initialize_project_storage_when_called_creates_project_database(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)

    with open_database(db_path) as connection:
        journal_row = cast(
            "sqlite3.Row | None",
            connection.execute("pragma journal_mode").fetchone(),
        )
        journal_mode = text_cell(require_row(journal_row), "journal_mode")
        app_name_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select value as app_name from settings where key = ?",
                ("app_name",),
            ).fetchone(),
        )
        app_name = text_cell(require_row(app_name_row), "app_name")

    assert db_path == tmp_path / ".doc2dic" / "glossary.sqlite3"
    assert db_path.exists()
    assert not (tmp_path / ".doc2dic" / "doc2dic.db").exists()
    assert journal_mode == "wal"
    assert app_name == "doc2dic"
