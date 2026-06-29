"""Concept and term variant SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.storage.json_codec import canonical_json, tuple_from_json_text
from doc2dic.storage.sqlite_rows import optional_text_cell, text_cell


class ConceptRepository:
    """Persist concepts and their term variants."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def upsert_concept(self, concept: Concept) -> None:
        """Insert or replace a concept row."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into concepts(
                  id, primary_term, definition, term_type, status, tags_json,
                  variants_json, scope_note, non_goals_json, examples_json, owner,
                  source_document, physical_name, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  primary_term = excluded.primary_term,
                  definition = excluded.definition,
                  term_type = excluded.term_type,
                  status = excluded.status,
                  tags_json = excluded.tags_json,
                  variants_json = excluded.variants_json,
                  scope_note = excluded.scope_note,
                  non_goals_json = excluded.non_goals_json,
                  examples_json = excluded.examples_json,
                  owner = excluded.owner,
                  source_document = excluded.source_document,
                  physical_name = excluded.physical_name,
                  updated_at = excluded.updated_at
                """,
                (
                    concept.id,
                    concept.primary_term,
                    concept.definition,
                    concept.term_type.value,
                    concept.status.value,
                    canonical_json(concept.tags),
                    canonical_json(concept.variant_ids),
                    concept.scope_note,
                    canonical_json(concept.non_goals),
                    canonical_json(concept.examples),
                    concept.owner,
                    concept.source_document,
                    concept.physical_name,
                    concept.created_at,
                    concept.updated_at,
                ),
            )

    def get_concept(self, concept_id: str) -> Concept | None:
        """Return a concept by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from concepts where id = ?",
                (concept_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return Concept(
            id=text_cell(row, "id"),
            primary_term=text_cell(row, "primary_term"),
            definition=text_cell(row, "definition"),
            term_type=ConceptTermType(text_cell(row, "term_type")),
            status=ConceptStatus(text_cell(row, "status")),
            tags=tuple_from_json_text(text_cell(row, "tags_json")),
            variant_ids=tuple_from_json_text(text_cell(row, "variants_json")),
            created_at=text_cell(row, "created_at"),
            updated_at=text_cell(row, "updated_at"),
            scope_note=optional_text_cell(row, "scope_note"),
            non_goals=tuple_from_json_text(text_cell(row, "non_goals_json")),
            examples=tuple_from_json_text(text_cell(row, "examples_json")),
            owner=optional_text_cell(row, "owner"),
            source_document=optional_text_cell(row, "source_document"),
            physical_name=optional_text_cell(row, "physical_name"),
        )

    def upsert_variant(self, variant: TermVariant) -> None:
        """Insert or replace a term variant row."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into term_variants(
                  id, concept_id, label, normalized_label, language, variant_type,
                  reason, status, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  concept_id = excluded.concept_id,
                  label = excluded.label,
                  normalized_label = excluded.normalized_label,
                  language = excluded.language,
                  variant_type = excluded.variant_type,
                  reason = excluded.reason,
                  status = excluded.status
                """,
                (
                    variant.id,
                    variant.concept_id,
                    variant.label,
                    variant.normalized_label,
                    variant.language,
                    variant.variant_type.value,
                    variant.reason,
                    variant.status.value,
                    variant.created_at,
                ),
            )

    def get_variant(self, variant_id: str) -> TermVariant | None:
        """Return a term variant by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from term_variants where id = ?",
                (variant_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return TermVariant(
            id=text_cell(row, "id"),
            concept_id=text_cell(row, "concept_id"),
            label=text_cell(row, "label"),
            normalized_label=text_cell(row, "normalized_label"),
            language=text_cell(row, "language"),
            variant_type=TermVariantType(text_cell(row, "variant_type")),
            reason=optional_text_cell(row, "reason"),
            status=TermVariantStatus(text_cell(row, "status")),
            created_at=text_cell(row, "created_at"),
        )
