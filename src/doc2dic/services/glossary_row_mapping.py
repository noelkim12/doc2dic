"""Glossary SQLite row-to-domain mapping helpers."""

import sqlite3

from doc2dic.domain import (
    Concept,
    ConceptRelation,
    ConceptRelationStatus,
    ConceptStatus,
    ConceptTermType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.storage.json_codec import tuple_from_json_text
from doc2dic.storage.sqlite_rows import float_cell, optional_text_cell, text_cell


def relation_from_row(row: sqlite3.Row) -> ConceptRelation:
    """Convert a SQLite relation row into a domain relation."""
    return ConceptRelation(
        id=text_cell(row, "id"),
        source_concept_id=text_cell(row, "source_concept_id"),
        target_concept_id=text_cell(row, "target_concept_id"),
        relation_type=text_cell(row, "relation_type"),
        confidence=float_cell(row, "confidence"),
        status=ConceptRelationStatus(text_cell(row, "status")),
        source_document_id=optional_text_cell(row, "source_document_id"),
    )


def concept_from_row(row: sqlite3.Row) -> Concept:
    """Convert a SQLite concept row into a domain concept."""
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


def variant_from_row(row: sqlite3.Row) -> TermVariant:
    """Convert a SQLite variant row into a domain variant."""
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
