import sqlite3
from pathlib import Path
from typing import cast

from tests.search.search_fixtures import seed_korean_search_sample

from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.search import SearchIndexRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row


def test_search_index_when_rebuilt_from_storage_returns_korean_feature_results(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        seed_korean_search_sample(connection)
        repository = SearchIndexRepository(connection)

        repository.rebuild()

        index_counts = _search_index_counts(connection)
        stamina = repository.search("스태미나", limit=2)
        entry_fatigue = repository.search("입장 피로도", limit=2)
        stagger = repository.search("경직", limit=2)
        empty = repository.search("없는 검색어", limit=2)
        whitespace = repository.search("   ", limit=2)
        punctuation = repository.search("!!!", limit=2)

    assert index_counts == {
        "concept_search_fts": 3,
        "document_search_fts": 3,
        "issue_search_fts": 3,
        "evidence_search_fts": 3,
    }
    assert [row.concept_id for row in stamina.concepts] == ["concept_stamina"]
    assert [row.document_id for row in stamina.documents] == ["doc_combat"]
    assert [row.issue_id for row in stamina.issues] == ["issue_stamina"]
    assert [row.evidence_id for row in stamina.evidence] == ["evidence_stamina"]
    assert [row.concept_id for row in entry_fatigue.concepts] == [
        "concept_entry_fatigue",
    ]
    assert [row.document_id for row in entry_fatigue.documents] == ["doc_dungeon"]
    assert [row.issue_id for row in entry_fatigue.issues] == ["issue_entry_fatigue"]
    assert [row.evidence_id for row in entry_fatigue.evidence] == [
        "evidence_entry_fatigue",
    ]
    assert [row.concept_id for row in stagger.concepts] == ["concept_stagger"]
    assert [row.document_id for row in stagger.documents] == ["doc_status"]
    assert [row.issue_id for row in stagger.issues] == ["issue_stagger"]
    assert [row.evidence_id for row in stagger.evidence] == ["evidence_stagger"]
    assert empty.is_empty
    assert whitespace.is_empty
    assert punctuation.is_empty
    assert all(len(rows) <= 2 for rows in empty)


def _search_index_counts(connection: sqlite3.Connection) -> dict[str, int]:
    concept_row = cast(
        "sqlite3.Row | None",
        connection.execute(
        "select count(*) as count from concept_search_fts",
        ).fetchone(),
    )
    document_row = cast(
        "sqlite3.Row | None",
        connection.execute(
        "select count(*) as count from document_search_fts",
        ).fetchone(),
    )
    issue_row = cast(
        "sqlite3.Row | None",
        connection.execute(
        "select count(*) as count from issue_search_fts",
        ).fetchone(),
    )
    evidence_row = cast(
        "sqlite3.Row | None",
        connection.execute(
        "select count(*) as count from evidence_search_fts",
        ).fetchone(),
    )
    return {
        "concept_search_fts": int_cell(require_row(concept_row), "count"),
        "document_search_fts": int_cell(require_row(document_row), "count"),
        "issue_search_fts": int_cell(require_row(issue_row), "count"),
        "evidence_search_fts": int_cell(require_row(evidence_row), "count"),
    }
