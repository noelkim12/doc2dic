"""Active concept document embedding indexer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast

from doc2dic.domain import Embedding, EmbeddingOwnerType
from doc2dic.services.embedding_index_documents import (
    ActiveConceptDocument,
    active_concept_documents,
)
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingSuccess,
)
from doc2dic.storage.repositories.embeddings import EmbeddingLookup, EmbeddingRepository
from doc2dic.storage.vector_store import DIMENSION_SETTING, ENABLED_SETTING

if TYPE_CHECKING:
    from doc2dic.storage.vector_store import VectorStore

_CREATED_AT_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
_ENABLED: Final = True
_DISABLED: Final = False


@dataclass(frozen=True, slots=True)
class ConceptEmbeddingIndexResult:  # noqa: D101
    enabled: bool
    reason: str
    provider: str
    model: str
    dimension: int | None
    active_count: int
    indexed_count: int
    reused_count: int


@dataclass(frozen=True, slots=True)
class IndexContext:
    connection: sqlite3.Connection
    repository: EmbeddingRepository
    embedding_service: EmbeddingService
    vector_store: VectorStore


@dataclass(frozen=True, slots=True)
class PendingConceptBatch:
    active_documents: tuple[ActiveConceptDocument, ...]
    reusable: tuple[Embedding, ...]
    pending: tuple[ActiveConceptDocument, ...]
    metadata: EmbeddingSuccess


def index_active_concept_embeddings(  # noqa: D103
    connection: sqlite3.Connection,
    *,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
) -> ConceptEmbeddingIndexResult:
    context = IndexContext(
        connection=connection,
        repository=EmbeddingRepository(connection),
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    metadata_result = _embedding_service_metadata(embedding_service)
    match metadata_result:
        case ConceptEmbeddingIndexResult() as failure:
            return failure
        case EmbeddingSuccess(model=model):
            active_documents = active_concept_documents(connection, model=model)
            return _index_documents(context, active_documents, metadata_result)


def _embedding_service_metadata(
    embedding_service: EmbeddingService,
) -> EmbeddingSuccess | ConceptEmbeddingIndexResult:
    result = embedding_service.embed_texts(())
    match result:
        case EmbeddingFailure(message=message, provider=provider):
            return ConceptEmbeddingIndexResult(
                _DISABLED, message, provider, "", None, 0, 0, 0,
            )
        case EmbeddingSuccess() as success:
            return success


def _index_documents(
    context: IndexContext,
    active_documents: tuple[ActiveConceptDocument, ...],
    metadata: EmbeddingSuccess,
) -> ConceptEmbeddingIndexResult:
    if not active_documents:
        return ConceptEmbeddingIndexResult(
            _ENABLED, "no active concepts", metadata.provider, metadata.model,
            metadata.dimension, 0, 0, 0,
        )
    reusable, pending = _partition_reusable(context, active_documents)
    if not pending:
        return ConceptEmbeddingIndexResult(
            _ENABLED, "all concept embeddings reused",
            metadata.provider, metadata.model,
            reusable[0].dimension if reusable else None, len(active_documents), 0,
            len(reusable),
        )
    return _index_pending_documents(
        context,
        PendingConceptBatch(
            active_documents=active_documents,
            reusable=reusable,
            pending=pending,
            metadata=metadata,
        ),
    )


def _index_pending_documents(
    context: IndexContext,
    batch: PendingConceptBatch,
) -> ConceptEmbeddingIndexResult:
    embedding_result = context.embedding_service.embed_texts(
        tuple(document.text for document in batch.pending),
        input_type=EmbeddingInputType.DOCUMENT,
    )
    match embedding_result:
        case EmbeddingFailure(message=message, provider=provider):
            return ConceptEmbeddingIndexResult(
                _DISABLED, message, provider, batch.metadata.model, None,
                len(batch.active_documents), 0, len(batch.reusable),
            )
        case EmbeddingSuccess(
            provider=provider,
            model=model,
            dimension=dimension,
            embeddings=embeddings,
        ):
            if len(embeddings) != len(batch.pending):
                return ConceptEmbeddingIndexResult(
                    _DISABLED, "provider returned unexpected embedding count", provider,
                    model, dimension, len(batch.active_documents), 0,
                    len(batch.reusable),
                )
            capability = context.vector_store.ensure_capability(dimension=dimension)
            if not capability.enabled:
                return ConceptEmbeddingIndexResult(
                    _DISABLED, capability.reason, provider, model, dimension,
                    len(batch.active_documents), 0, len(batch.reusable),
                )
            indexed_count = 0
            for pending, embedding_vector in zip(
                batch.pending, embeddings, strict=True,
            ):
                embedding = _embedding_metadata(
                    context.repository,
                    pending=pending,
                    dimension=dimension,
                )
                context.repository.upsert_embedding(embedding)
                write_result = context.vector_store.upsert_vector(
                    embedding_id=embedding.id,
                    vector=embedding_vector.values,
                )
                if write_result.enabled:
                    indexed_count += 1
            return ConceptEmbeddingIndexResult(
                _ENABLED, "active concept embeddings indexed",
                provider, model, dimension,
                len(batch.active_documents), indexed_count, len(batch.reusable),
            )


def _partition_reusable(
    context: IndexContext,
    documents: tuple[ActiveConceptDocument, ...],
) -> tuple[tuple[Embedding, ...], tuple[ActiveConceptDocument, ...]]:
    reusable: list[Embedding] = []
    pending: list[ActiveConceptDocument] = []
    for document in documents:
        existing = context.repository.find_existing_embedding(
            EmbeddingLookup(
                owner_type=EmbeddingOwnerType.CONCEPT,
                owner_id=document.concept_id,
                model=document.model,
                content_hash=document.content_hash,
            ),
        )
        if existing is None:
            pending.append(document)
        elif _vector_exists(context.connection, embedding_id=existing.id):
            reusable.append(existing)
        else:
            pending.append(replace(document, existing=existing))
    return tuple(reusable), tuple(pending)


def _embedding_metadata(
    repository: EmbeddingRepository,
    *,
    pending: ActiveConceptDocument,
    dimension: int,
) -> Embedding:
    embedding_id = repository.next_embedding_id()
    if pending.existing is not None:
        embedding_id = pending.existing.id
    return Embedding(
        id=embedding_id,
        owner_type=EmbeddingOwnerType.CONCEPT,
        owner_id=pending.concept_id,
        model=pending.model,
        dimension=dimension,
        content_hash=pending.content_hash,
        created_at=datetime.now(UTC).strftime(_CREATED_AT_FORMAT),
    )


def _vector_exists(connection: sqlite3.Connection, *, embedding_id: int) -> bool:
    try:
        row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select 1 from embedding_vectors where rowid = ?",
                (embedding_id,),
            ).fetchone(),
        )
    except sqlite3.OperationalError as exc:
        if _is_missing_embedding_vectors_table(exc):
            _clear_vector_capability_settings(connection)
            return False
        raise
    return row is not None


def _is_missing_embedding_vectors_table(error: sqlite3.OperationalError) -> bool:
    return "no such table: embedding_vectors" in str(error)


def _clear_vector_capability_settings(connection: sqlite3.Connection) -> None:
    with connection:
        _ = connection.execute(
            "delete from settings where key in (?, ?)",
            (ENABLED_SETTING, DIMENSION_SETTING),
        )


__all__ = ["ConceptEmbeddingIndexResult", "index_active_concept_embeddings"]
