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
        connection.commit()


def _create_v2_database(db_path: Path) -> None:
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        _ = connection.execute("delete from schema_migrations where version > 2")
        _ = connection.execute("drop table if exists issue_search_fts")
        _ = connection.execute("drop table if exists evidence_search_fts")
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

    assert first.applied_versions == (1, 2, 3)
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

    assert result.current_version == 3
    assert result.applied_versions == (1, 2, 3)
    assert versions == [1, 2, 3]
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

    assert result.current_version == 3
    assert result.applied_versions == (2, 3)
    assert versions == [1, 2, 3]
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

    assert result.current_version == 3
    assert result.applied_versions == (3,)
    assert versions == [1, 2, 3]
    assert SEARCH_TABLES.issubset(tables)


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
