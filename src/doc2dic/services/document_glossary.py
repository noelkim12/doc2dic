"""Glossary term loading for deterministic document checks."""

import sqlite3
from dataclasses import dataclass
from typing import cast

from doc2dic.domain import ConceptStatus, TermVariantStatus, TermVariantType
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.storage.sqlite_rows import optional_text_cell, text_cell


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    """A stored glossary surface with concept lifecycle metadata."""

    concept_id: str
    label: str
    normalized_label: str
    variant_type: TermVariantType
    variant_status: TermVariantStatus
    concept_status: ConceptStatus


def load_glossary_terms(connection: sqlite3.Connection) -> tuple[GlossaryTerm, ...]:
    """Load concept primary terms and variants from storage."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            """
            select
              c.id as concept_id,
              c.primary_term as primary_term,
              c.status as concept_status,
              v.label as variant_label,
              v.normalized_label as normalized_label,
              v.variant_type as variant_type,
              v.status as variant_status
            from concepts c
            left join term_variants v on v.concept_id = c.id
            order by c.id, v.id
            """,
        ).fetchall(),
    )
    terms: list[GlossaryTerm] = []
    seen: set[tuple[str, str, TermVariantType]] = set()
    for row in rows:
        term = _term_from_row(row)
        key = (term.concept_id, term.normalized_label, term.variant_type)
        if key not in seen:
            terms.append(term)
            seen.add(key)
    return tuple(terms)


def term_is_active(term: GlossaryTerm) -> bool:
    """Return whether a term can participate in exact/fuzzy active checks."""
    return (
        term.concept_status is ConceptStatus.ACTIVE
        and term.variant_status is TermVariantStatus.ACTIVE
    )


def _term_from_row(row: sqlite3.Row) -> GlossaryTerm:
    label = optional_text_cell(row, "variant_label") or text_cell(row, "primary_term")
    normalized = optional_text_cell(row, "normalized_label") or normalize_term_text(
        label,
    )
    variant_type_text = optional_text_cell(
        row,
        "variant_type",
    ) or TermVariantType.PRIMARY.value
    variant_status_text = optional_text_cell(
        row,
        "variant_status",
    ) or TermVariantStatus.ACTIVE.value
    return GlossaryTerm(
        concept_id=text_cell(row, "concept_id"),
        label=label,
        normalized_label=normalized,
        variant_type=TermVariantType(variant_type_text),
        variant_status=TermVariantStatus(variant_status_text),
        concept_status=ConceptStatus(text_cell(row, "concept_status")),
    )
