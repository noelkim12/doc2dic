"""Storage-backed glossary concept, variant, tag, and relation service."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from doc2dic.domain import (
    Concept,
    ConceptRelation,
    ConceptRelationStatus,
    ConceptStatus,
    Tag,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.glossary_keys import (
    generated_prefixed_id,
    normalize_label,
    normalize_tags,
    relation_id,
)
from doc2dic.services.glossary_models import (
    CreateConceptInput,
    CreateRelationInput,
    CreateVariantInput,
    DuplicateGlossaryItemError,
    GlossaryError,
    GlossaryItemNotFoundError,
    InvalidRelationTargetError,
    UpdateConceptInput,
)
from doc2dic.services.glossary_row_mapping import relation_from_row
from doc2dic.services.glossary_rows import (
    ensure_label_available,
    ensure_primary_variant_available,
    find_concept,
    insert_relation_row,
    insert_variant_row,
    list_concept_rows,
    list_tag_rows,
    list_variant_rows,
    replace_concept_tags,
    upsert_concept_row,
)

if TYPE_CHECKING:
    import sqlite3
    from contextlib import AbstractContextManager

    from doc2dic.services.embedding_index import ConceptEmbeddingIndexResult


class GlossaryEmbeddingIndexer(Protocol):
    """Capability for refreshing glossary concept embeddings after mutations."""

    def index_active_concepts(self) -> ConceptEmbeddingIndexResult:
        """Backfill or refresh embeddings for active concepts."""
        ...

__all__ = [
    "CreateConceptInput",
    "CreateRelationInput",
    "CreateVariantInput",
    "DuplicateGlossaryItemError",
    "GlossaryError",
    "GlossaryItemNotFoundError",
    "GlossaryService",
    "InvalidRelationTargetError",
    "UpdateConceptInput",
    "normalize_label",
    "relation_from_row",
]


class GlossaryService:
    """Coordinate glossary mutations behind one SQLite transaction boundary."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        embedding_indexer: GlossaryEmbeddingIndexer | None = None,
    ) -> None:
        """Store the SQLite connection for this service instance."""
        self._connection: sqlite3.Connection
        self._connection = connection
        self._embedding_indexer: GlossaryEmbeddingIndexer | None
        self._embedding_indexer = embedding_indexer
        self.last_embedding_index_result: ConceptEmbeddingIndexResult | None
        self.last_embedding_index_result = None

    def create_concept(self, command: CreateConceptInput) -> Concept:
        """Create a concept and its primary variant."""
        now = _now()
        normalized = normalize_label(command.primary_term)
        concept_id = generated_prefixed_id("concept")
        variant_id = generated_prefixed_id("variant")
        concept = Concept(
            id=concept_id,
            primary_term=command.primary_term.strip(),
            definition=command.definition.strip(),
            term_type=command.term_type,
            status=ConceptStatus.ACTIVE,
            tags=normalize_tags(command.tags),
            variant_ids=(variant_id,),
            created_at=now,
            updated_at=now,
            source_document=_clean_optional(command.source_document),
        )
        variant = TermVariant(
            id=variant_id,
            concept_id=concept_id,
            label=concept.primary_term,
            normalized_label=normalized,
            variant_type=TermVariantType.PRIMARY,
            status=TermVariantStatus.ACTIVE,
            created_at=now,
        )
        with self._transaction():
            ensure_label_available(self._connection, normalized)
            upsert_concept_row(self._connection, concept)
            insert_variant_row(self._connection, variant)
            replace_concept_tags(self._connection, concept.id, concept.tags)
        self._refresh_embeddings()
        return concept

    def list_concepts(
        self,
        *,
        status: ConceptStatus | None = None,
        tag: str | None = None,
    ) -> tuple[Concept, ...]:
        """List concepts, optionally filtered by status or tag."""
        return list_concept_rows(self._connection, status=status, tag=tag)

    def get_concept(self, concept_id: str) -> Concept:
        """Return one concept or raise a typed not-found error."""
        concept = find_concept(self._connection, concept_id)
        if concept is None:
            message = f"concept not found: {concept_id}"
            raise GlossaryItemNotFoundError(message)
        return concept

    def update_concept(self, concept_id: str, command: UpdateConceptInput) -> Concept:
        """Patch concept fields and keep tag links synchronized."""
        current = self.get_concept(concept_id)
        primary_term = _updated_text(command.primary_term, current.primary_term)
        definition = _updated_text(command.definition, current.definition)
        tags = (
            normalize_tags(command.tags) if command.tags is not None else current.tags
        )
        source_document = (
            _clean_optional(command.source_document)
            if command.source_document is not None
            else current.source_document
        )
        updated = current.model_copy(
            update={
                "primary_term": primary_term,
                "definition": definition,
                "term_type": command.term_type or current.term_type,
                "status": command.status or current.status,
                "tags": tags,
                "source_document": source_document,
                "updated_at": _now(),
            },
        )
        with self._transaction():
            if normalize_label(primary_term) != normalize_label(current.primary_term):
                ensure_label_available(self._connection, normalize_label(primary_term))
            upsert_concept_row(self._connection, updated)
            replace_concept_tags(self._connection, updated.id, updated.tags)
        self._refresh_embeddings()
        return updated

    def deprecate_concept(self, concept_id: str) -> Concept:
        """Mark a concept as deprecated."""
        return self.update_concept(
            concept_id,
            UpdateConceptInput(status=ConceptStatus.DEPRECATED),
        )

    def delete_concept(self, concept_id: str) -> None:
        """Delete a concept and cascading variants, tags, and relations."""
        _ = self.get_concept(concept_id)
        with self._transaction():
            _ = self._connection.execute(
                "delete from concepts where id = ?",
                (concept_id,),
            )

    def add_variant(self, command: CreateVariantInput) -> TermVariant:
        """Attach a non-duplicated variant to an existing concept."""
        concept = self.get_concept(command.concept_id)
        normalized = normalize_label(command.label)
        variant = TermVariant(
            id=generated_prefixed_id("variant"),
            concept_id=command.concept_id,
            label=command.label.strip(),
            normalized_label=normalized,
            variant_type=command.variant_type,
            status=command.status,
            language=command.language,
            reason=command.reason,
            created_at=_now(),
        )
        with self._transaction():
            ensure_label_available(self._connection, normalized)
            if command.variant_type is TermVariantType.PRIMARY:
                ensure_primary_variant_available(self._connection, command.concept_id)
            insert_variant_row(self._connection, variant)
            variant_ids = (*concept.variant_ids, variant.id)
            upsert_concept_row(
                self._connection,
                concept.model_copy(update={"variant_ids": variant_ids}),
            )
        self._refresh_embeddings()
        return variant

    def add_relation(self, command: CreateRelationInput) -> ConceptRelation:
        """Create a relation after validating both concept endpoints."""
        self._ensure_relation_targets(command)
        relation = ConceptRelation(
            id=relation_id(command),
            source_concept_id=command.source_concept_id,
            target_concept_id=command.target_concept_id,
            relation_type=command.relation_type,
            confidence=command.confidence,
            status=ConceptRelationStatus.APPROVED,
            source_document_id=command.source_document_id,
        )
        with self._transaction():
            insert_relation_row(self._connection, relation)
        return relation

    def list_variants(self, concept_id: str) -> tuple[TermVariant, ...]:
        """Return variants attached to a concept."""
        return list_variant_rows(self._connection, concept_id)

    def list_tags(self) -> tuple[Tag, ...]:
        """Return all stored tags."""
        return list_tag_rows(self._connection)

    def _ensure_relation_targets(self, command: CreateRelationInput) -> None:
        if command.source_concept_id == command.target_concept_id:
            msg = "relation target must differ from source"
            raise InvalidRelationTargetError(msg)
        if find_concept(self._connection, command.source_concept_id) is None:
            message = f"relation source not found: {command.source_concept_id}"
            raise InvalidRelationTargetError(message)
        if find_concept(self._connection, command.target_concept_id) is None:
            message = f"relation target not found: {command.target_concept_id}"
            raise InvalidRelationTargetError(message)

    def _transaction(self) -> AbstractContextManager[sqlite3.Connection | None]:
        if self._connection.in_transaction:
            return nullcontext()
        return self._connection

    def _refresh_embeddings(self) -> None:
        if self._embedding_indexer is None:
            return
        self.last_embedding_index_result = (
            self._embedding_indexer.index_active_concepts()
        )


def _updated_text(candidate: str | None, fallback: str) -> str:
    if candidate:
        return candidate.strip()
    return fallback


def _clean_optional(candidate: str | None) -> str | None:
    if candidate is None:
        return None
    stripped = candidate.strip()
    return stripped or None


def _now() -> str:
    return (
        datetime.now(tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
