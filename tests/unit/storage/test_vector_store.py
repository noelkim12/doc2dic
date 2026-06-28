import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from doc2dic.domain import Embedding, EmbeddingOwnerType
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.embeddings import EmbeddingLookup, EmbeddingRepository
from doc2dic.storage.sqlite_rows import float_cell, int_cell, require_row, text_cell
from doc2dic.storage.vector_store import (
    StoredVector,
    VectorBackendUnavailableError,
    VectorStore,
)


@dataclass(slots=True)
class FakeVectorBackend:
    is_available: bool = True
    create_count: int = 0

    def load(self, connection: sqlite3.Connection) -> None:
        if not self.is_available:
            raise VectorBackendUnavailableError(reason="fake sqlite-vec missing")
        connection.create_function("vec_distance", 2, _distance)

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        assert dimension > 0
        self.create_count += 1
        _ = connection.execute("drop table if exists embedding_vectors")
        _ = connection.execute(
            """
            create table embedding_vectors(
              rowid integer primary key,
              embedding text not null
            )
            """,
        )

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        _ = connection.execute(
            "insert or replace into embedding_vectors(rowid, embedding) values (?, ?)",
            (vector.embedding_id, _encode(vector.values)),
        )

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        rows = cast(
            "list[sqlite3.Row]",
            connection.execute(
                """
                select rowid, vec_distance(embedding, ?) as distance
                from embedding_vectors
                order by distance
                limit ?
                """,
                (_encode(vector), top_k),
            ).fetchall(),
        )
        return tuple(
            (int_cell(row, "rowid"), float_cell(row, "distance")) for row in rows
        )


def test_vector_store_when_backend_unavailable_returns_disabled_result(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        store = VectorStore(connection, backend=FakeVectorBackend(is_available=False))

        capability = store.ensure_capability(dimension=3)
        write_result = store.upsert_vector(embedding_id=1, vector=(1.0, 2.0, 3.0))
        query_result = store.query_top_k(vector=(1.0, 2.0, 3.0), top_k=5)
        placeholder_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select name from sqlite_master where type = 'table' and name = ?",
                ("embedding_vectors",),
            ).fetchone(),
        )

    assert capability.enabled is False
    assert capability.reason == "fake sqlite-vec missing"
    assert write_result.enabled is False
    assert query_result.enabled is False
    assert query_result.matches == ()
    assert require_row(placeholder_row)["name"] == "embedding_vectors"


def test_vector_store_when_enabled_aligns_embedding_rowids_and_queries_top_k(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    backend = FakeVectorBackend()

    with open_database(db_path) as connection:
        embedding_repository = EmbeddingRepository(connection)
        embedding_ids = ((1, "concept_a"), (2, "concept_b"), (3, "concept_c"))
        for embedding_id, owner_id in embedding_ids:
            embedding_repository.upsert_embedding(_embedding(embedding_id, owner_id))

        store = VectorStore(connection, backend=backend)
        capability = store.ensure_capability(dimension=3)
        first = store.upsert_vector(embedding_id=1, vector=(1.0, 0.0, 0.0))
        _ = store.upsert_vector(embedding_id=2, vector=(0.0, 1.0, 0.0))
        _ = store.upsert_vector(embedding_id=3, vector=(1.0, 1.0, 0.0))

        query_result = store.query_top_k(vector=(0.9, 0.1, 0.0), top_k=2)
        settings_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select value from settings where key = ?",
                ("embedding_vectors_enabled",),
            ).fetchone(),
        )

    assert capability.enabled is True
    assert capability.dimension == 3
    assert first.enabled is True
    assert query_result.enabled is True
    assert tuple(match.embedding_id for match in query_result.matches) == (1, 3)
    assert text_cell(require_row(settings_row), "value") == "true"


def test_vector_store_when_dimension_changes_rebuilds_vector_table(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    backend = FakeVectorBackend()

    with open_database(db_path) as connection:
        embedding_repository = EmbeddingRepository(connection)
        embedding_repository.upsert_embedding(_embedding(1, "concept_a"))
        store = VectorStore(connection, backend=backend)
        _ = store.ensure_capability(dimension=3)
        _ = store.upsert_vector(embedding_id=1, vector=(1.0, 0.0, 0.0))

        _ = store.ensure_capability(dimension=2)
        query_result = store.query_top_k(vector=(1.0, 0.0), top_k=5)
        dimension_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select value from settings where key = ?",
                ("embedding_vectors_dimension",),
            ).fetchone(),
        )

    assert backend.create_count == 2
    assert query_result.enabled is True
    assert query_result.matches == ()
    assert text_cell(require_row(dimension_row), "value") == "2"


def test_vector_store_when_settings_match_but_vector_table_is_missing_recreates_table(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    backend = FakeVectorBackend()

    with open_database(db_path) as connection:
        embedding_repository = EmbeddingRepository(connection)
        embedding_repository.upsert_embedding(_embedding(1, "concept_a"))
        with connection:
            _ = connection.execute("drop table embedding_vectors")
            _ = connection.execute(
                """
                insert into settings(key, value, updated_at)
                values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                on conflict(key) do update set value = excluded.value
                """,
                ("embedding_vectors_enabled", "true"),
            )
            _ = connection.execute(
                """
                insert into settings(key, value, updated_at)
                values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                on conflict(key) do update set value = excluded.value
                """,
                ("embedding_vectors_dimension", "3"),
            )

        store = VectorStore(connection, backend=backend)
        capability = store.ensure_capability(dimension=3)
        write_result = store.upsert_vector(embedding_id=1, vector=(1.0, 0.0, 0.0))
        vector_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select rowid from embedding_vectors where rowid = ?",
                (1,),
            ).fetchone(),
        )

    assert capability.enabled is True
    assert capability.dimension == 3
    assert backend.create_count == 1
    assert write_result.enabled is True
    assert int_cell(require_row(vector_row), "rowid") == 1


def test_vector_store_when_vector_dimension_mismatches_disables_write(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        embedding_repository = EmbeddingRepository(connection)
        embedding_repository.upsert_embedding(_embedding(1, "concept_a"))
        store = VectorStore(connection, backend=FakeVectorBackend())
        _ = store.ensure_capability(dimension=3)

        write_result = store.upsert_vector(embedding_id=1, vector=(1.0, 0.0))

    assert write_result.enabled is False
    assert write_result.reason == (
        "vector dimension 2 does not match configured dimension 3"
    )


def test_embedding_repository_when_lookup_matches_owner_model_and_hash_reuses_row(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        repository = EmbeddingRepository(connection)
        expected = _embedding(7, "concept_a")
        repository.upsert_embedding(expected)
        repository.upsert_embedding(_embedding(8, "concept_a"))

        found = repository.find_existing_embedding(
            EmbeddingLookup(
                owner_type=EmbeddingOwnerType.CONCEPT,
                owner_id="concept_a",
                model="fake-embedding",
                content_hash="0123456789abcdef7",
            ),
        )
        missing = repository.find_existing_embedding(
            EmbeddingLookup(
                owner_type=EmbeddingOwnerType.CONCEPT,
                owner_id="concept_a",
                model="fake-embedding",
                content_hash="missing-missing-00",
            ),
        )

    assert found == expected
    assert missing is None


def test_embedding_repository_when_allocating_next_id_uses_max_plus_one(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        repository = EmbeddingRepository(connection)
        empty_next_id = repository.next_embedding_id()
        repository.upsert_embedding(_embedding(1, "concept_a"))
        repository.upsert_embedding(_embedding(42, "concept_b"))

        allocated_id = repository.next_embedding_id()
        collision_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select id from embeddings where id = ?",
                (allocated_id,),
            ).fetchone(),
        )

    assert empty_next_id == 1
    assert allocated_id == 43
    assert collision_row is None


def _embedding(embedding_id: int, owner_id: str) -> Embedding:
    return Embedding(
        id=embedding_id,
        owner_type=EmbeddingOwnerType.CONCEPT,
        owner_id=owner_id,
        model="fake-embedding",
        dimension=3,
        content_hash=f"0123456789abcdef{embedding_id}",
        created_at="2026-06-25T00:00:00Z",
    )


def _encode(vector: Sequence[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def _distance(left_json: str, right_json: str) -> float:
    left = _decode(left_json)
    right = _decode(right_json)
    squared_deltas = (
        (left_value - right_value) ** 2
        for left_value, right_value in zip(left, right, strict=True)
    )
    return math.sqrt(sum(squared_deltas))


def _decode(vector_json: str) -> tuple[float, ...]:
    return tuple(float(value) for value in vector_json.strip("[]").split(","))
