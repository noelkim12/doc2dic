from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

from doc2dic.domain import Concept, ConceptStatus, ConceptTermType
from doc2dic.services.embedding_index import (
    ConceptEmbeddingIndexResult,
    index_active_concept_embeddings,
)
from doc2dic.services.embedding_service import (
    DisabledEmbeddingProvider,
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingVector,
)
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories import ConceptRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row
from doc2dic.storage.vector_store import StoredVector, VectorStore
from doc2dic.storage.vector_types import VectorBackendUnavailableError

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Sequence
    from pathlib import Path

    from doc2dic.services.embedding_service import EmbeddingProvider


@dataclass(slots=True)
class RecordingEmbeddingProvider:
    dimension: int = 3
    model: str = "recording-model"
    provider_name: str = "recording-provider"
    calls: list[tuple[tuple[str, ...], EmbeddingInputType]] = field(
        default_factory=list,
    )

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        self.calls.append((texts, input_type))
        return tuple(
            EmbeddingVector(
                text=text,
                model=self.model,
                values=tuple(float(index + 1) for index in range(self.dimension)),
            )
            for text in texts
        )


@dataclass(frozen=True, slots=True)
class WrongDimensionProvider:
    dimension: int = 3
    model: str = "wrong-dimension"
    provider_name: str = "wrong-dimension-provider"

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        _ = input_type
        return tuple(
            EmbeddingVector(text=text, model=self.model, values=(1.0, 2.0))
            for text in texts
        )


@dataclass(slots=True)
class RecordingVectorBackend:
    is_available: bool = True
    create_dimensions: list[int] = field(default_factory=list)
    upsert_count: int = 0

    def load(self, connection: sqlite3.Connection) -> None:
        if not self.is_available:
            raise VectorBackendUnavailableError(reason="fake vector backend disabled")
        del connection

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        self.create_dimensions.append(dimension)
        _ = connection.execute("drop table if exists embedding_vectors")
        _ = connection.execute(
            "create table embedding_vectors(rowid integer primary key, embedding text)",
        )

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        self.upsert_count += 1
        _ = connection.execute(
            "insert or replace into embedding_vectors(rowid, embedding) values (?, ?)",
            (vector.embedding_id, json.dumps(vector.values)),
        )

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        del connection, vector, top_k
        return ()


def test_active_concepts_are_embedded_as_document_text(tmp_path: Path) -> None:
    provider = RecordingEmbeddingProvider(dimension=5)

    with open_database(_migrated_db(tmp_path)) as connection:
        repository = ConceptRepository(connection)
        active = _concept("concept_active", status=ConceptStatus.ACTIVE)
        repository.upsert_concept(active)
        repository.upsert_concept(
            _concept("concept_deprecated", status=ConceptStatus.DEPRECATED),
        )
        backend = RecordingVectorBackend()

        result = _index(connection, provider, backend)

    assert (result.enabled, result.indexed_count, result.dimension) == (True, 1, 5)
    assert backend.create_dimensions == [5]
    assert provider.calls[0][1] is EmbeddingInputType.DOCUMENT
    embedded_text = provider.calls[0][0][0]
    assert all(
        text in embedded_text
        for text in (
            "Primary term: Active Term", "Definition: Active definition",
            "Scope note: Active scope", "Non-goals: Not this; Not that",
            "Examples: Active example", "Tags: combat, economy",
        )
    )
    assert "Deprecated" not in embedded_text


def test_content_hash_reuse_avoids_duplicate_metadata_and_vector_writes(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    backend = RecordingVectorBackend()

    with open_database(_migrated_db(tmp_path)) as connection:
        repository = ConceptRepository(connection)
        repository.upsert_concept(_concept("concept_first"))
        repository.upsert_concept(_concept("concept_second", primary_term="Second"))
        store = VectorStore(connection, backend=backend)

        first = _index(connection, provider, store)
        second = _index(connection, provider, store)

        embedding_count = _table_count(connection, "embeddings")
        vector_count = _table_count(connection, "embedding_vectors")

    assert (
        first.indexed_count, first.reused_count, second.indexed_count,
        second.reused_count, len(provider.calls), backend.upsert_count,
        embedding_count, vector_count,
    ) == (2, 0, 0, 2, 1, 2, 2, 2)


def test_metadata_without_vector_is_reindexed_without_duplicate_metadata(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    backend = RecordingVectorBackend()

    with open_database(_migrated_db(tmp_path)) as connection:
        ConceptRepository(connection).upsert_concept(_concept("concept_active"))
        store = VectorStore(connection, backend=backend)

        first = _index(connection, provider, store)
        _ = connection.execute("delete from embedding_vectors")
        stale = _index(connection, provider, store)

        embedding_count = _table_count(connection, "embeddings")
        vector_count = _table_count(connection, "embedding_vectors")

    assert stale.enabled is True
    assert (
        first.indexed_count, stale.indexed_count, stale.reused_count,
        len(provider.calls), backend.upsert_count, embedding_count, vector_count,
    ) == (1, 1, 0, 2, 2, 1, 1)


def test_metadata_without_vector_table_is_reindexed_after_table_recreate(
    tmp_path: Path,
) -> None:
    provider = RecordingEmbeddingProvider()
    backend = RecordingVectorBackend()

    with open_database(_migrated_db(tmp_path)) as connection:
        ConceptRepository(connection).upsert_concept(_concept("concept_active"))
        store = VectorStore(connection, backend=backend)

        first = _index(connection, provider, store)
        _ = connection.execute("drop table embedding_vectors")
        stale = _index(connection, provider, store)

        embedding_count = _table_count(connection, "embeddings")
        vector_count = _table_count(connection, "embedding_vectors")

    assert stale.enabled is True
    assert (
        first.indexed_count, stale.indexed_count, stale.reused_count,
        len(provider.calls), backend.upsert_count, embedding_count, vector_count,
    ) == (1, 1, 0, 2, 2, 1, 1)


def test_disabled_provider_skips_writes_safely(tmp_path: Path) -> None:
    backend = RecordingVectorBackend()

    with open_database(_migrated_db(tmp_path)) as connection:
        ConceptRepository(connection).upsert_concept(_concept("concept_active"))

        result = _index(connection, DisabledEmbeddingProvider(), backend)
        backend_disabled = _index(
            connection,
            RecordingEmbeddingProvider(),
            RecordingVectorBackend(is_available=False),
        )

        embedding_count = _table_count(connection, "embeddings")
        vector_count = _table_count(connection, "embedding_vectors")

    assert result.enabled is False
    assert backend_disabled.enabled is False
    assert (
        result.indexed_count, result.reused_count, embedding_count, vector_count,
        backend.upsert_count,
    ) == (0, 0, 0, 0, 0)


def test_invalid_provider_dimension_returns_failure_without_partial_writes(
    tmp_path: Path,
) -> None:
    backend = RecordingVectorBackend()

    with open_database(_migrated_db(tmp_path)) as connection:
        ConceptRepository(connection).upsert_concept(_concept("concept_active"))

        result = _index(connection, WrongDimensionProvider(), backend)

        embedding_count = _table_count(connection, "embeddings")
        vector_count = _table_count(connection, "embedding_vectors")

    assert result.enabled is False
    assert result.reason == "provider returned vector with unexpected dimension"
    assert (embedding_count, vector_count, backend.upsert_count) == (0, 0, 0)


def test_indexing_does_not_modify_concept_rows(tmp_path: Path) -> None:
    provider = RecordingEmbeddingProvider()

    with open_database(_migrated_db(tmp_path)) as connection:
        repository = ConceptRepository(connection)
        concept = _concept("concept_active")
        repository.upsert_concept(concept)
        before = repository.get_concept(concept.id)

        _ = _index(connection, provider, RecordingVectorBackend())
        after = repository.get_concept(concept.id)

    assert (before, after) == (concept, concept)


def _migrated_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    return db_path


def _index(
    connection: sqlite3.Connection,
    provider: EmbeddingProvider,
    backend: RecordingVectorBackend | VectorStore,
) -> ConceptEmbeddingIndexResult:
    if isinstance(backend, VectorStore):
        store = backend
    else:
        store = VectorStore(connection, backend=backend)
    return index_active_concept_embeddings(
        connection,
        embedding_service=EmbeddingService(provider),
        vector_store=store,
    )


def _concept(
    concept_id: str,
    *,
    status: ConceptStatus = ConceptStatus.ACTIVE,
    primary_term: str = "Active Term",
) -> Concept:
    return Concept(
        id=concept_id,
        primary_term=primary_term,
        definition="Active definition",
        term_type=ConceptTermType.MECHANIC,
        status=status,
        tags=("combat", "economy"),
        scope_note="Active scope",
        non_goals=("Not this", "Not that"),
        examples=("Active example",),
        created_at="2026-06-26T00:00:00Z",
        updated_at="2026-06-26T00:00:00Z",
    )


def _table_count(
    connection: sqlite3.Connection,
    table_name: Literal["embeddings", "embedding_vectors"],
) -> int:
    match table_name:
        case "embeddings":
            query = "select count(*) as row_count from embeddings"
        case "embedding_vectors":
            query = "select count(*) as row_count from embedding_vectors"
    row = require_row(
        cast("sqlite3.Row | None", connection.execute(query).fetchone()),
    )
    return int_cell(row, "row_count")
