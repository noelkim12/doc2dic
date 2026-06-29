"""Glossary SQLite row mapping and SQL helpers."""

import sqlite3
from typing import cast

from doc2dic.domain import (
    Concept,
    ConceptRelation,
    ConceptStatus,
    Tag,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.glossary_keys import prefixed_id
from doc2dic.services.glossary_models import DuplicateGlossaryItemError
from doc2dic.services.glossary_row_mapping import concept_from_row, variant_from_row
from doc2dic.storage.json_codec import canonical_json
from doc2dic.storage.sqlite_rows import text_cell

type ConceptParams = tuple[
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str | None,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str,
    str,
]


def list_concept_rows(
    connection: sqlite3.Connection,
    *,
    status: ConceptStatus | None,
    tag: str | None,
) -> tuple[Concept, ...]:
    """Return concept rows filtered by status or tag."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            _list_sql(status, tag),
            _list_params(status, tag),
        ).fetchall(),
    )
    return tuple(concept_from_row(row) for row in rows)


def find_concept(connection: sqlite3.Connection, concept_id: str) -> Concept | None:
    """Return one concept row by id when present."""
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select * from concepts where id = ?",
            (concept_id,),
        ).fetchone(),
    )
    return None if row is None else concept_from_row(row)


def ensure_label_available(connection: sqlite3.Connection, normalized: str) -> None:
    """Raise when a normalized term label already exists."""
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select id from term_variants where normalized_label = ?",
            (normalized,),
        ).fetchone(),
    )
    if row is not None:
        message = f"duplicate term label: {normalized}"
        raise DuplicateGlossaryItemError(message)


def ensure_primary_variant_available(
    connection: sqlite3.Connection,
    concept_id: str,
) -> None:
    """Raise when a concept already has an active primary variant."""
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            """
            select id from term_variants
            where concept_id = ? and variant_type = ? and status = ?
            """,
            (
                concept_id,
                TermVariantType.PRIMARY.value,
                TermVariantStatus.ACTIVE.value,
            ),
        ).fetchone(),
    )
    if row is not None:
        msg = f"concept already has a primary variant: {concept_id}"
        raise DuplicateGlossaryItemError(msg)


def upsert_concept_row(connection: sqlite3.Connection, concept: Concept) -> None:
    """Insert or update one concept row."""
    _ = connection.execute(
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
          source_document = excluded.source_document,
          physical_name = excluded.physical_name,
          updated_at = excluded.updated_at
        """,
        _concept_params(concept),
    )


def insert_variant_row(connection: sqlite3.Connection, variant: TermVariant) -> None:
    """Insert one term variant row."""
    _ = connection.execute(
        """
        insert into term_variants(
          id, concept_id, label, normalized_label, language, variant_type,
          reason, status, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def replace_concept_tags(
    connection: sqlite3.Connection,
    concept_id: str,
    tags: tuple[str, ...],
) -> None:
    """Replace normalized tag links for one concept."""
    _ = connection.execute(
        "delete from concept_tags where concept_id = ?",
        (concept_id,),
    )
    for tag in tags:
        tag_id = prefixed_id("tag", tag)
        _ = connection.execute(
            "insert or ignore into tags(id, label) values (?, ?)",
            (tag_id, tag),
        )
        _ = connection.execute(
            "insert into concept_tags(concept_id, tag_id) values (?, ?)",
            (concept_id, tag_id),
        )


def insert_relation_row(
    connection: sqlite3.Connection,
    relation: ConceptRelation,
) -> None:
    """Insert one concept relation row."""
    _ = connection.execute(
        """
        insert into concept_relations(
          id, source_concept_id, target_concept_id, relation_type,
          confidence, source_document_id, status
        ) values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            relation.id,
            relation.source_concept_id,
            relation.target_concept_id,
            relation.relation_type,
            relation.confidence,
            relation.source_document_id,
            relation.status.value,
        ),
    )


def list_variant_rows(
    connection: sqlite3.Connection,
    concept_id: str,
) -> tuple[TermVariant, ...]:
    """Return term variants attached to a concept."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            """
            select * from term_variants
            where concept_id = ? order by created_at, id
            """,
            (concept_id,),
        ).fetchall(),
    )
    return tuple(variant_from_row(row) for row in rows)


def list_tag_rows(connection: sqlite3.Connection) -> tuple[Tag, ...]:
    """Return all stored tags."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute("select * from tags order by label").fetchall(),
    )
    return tuple(
        Tag(id=text_cell(row, "id"), label=text_cell(row, "label")) for row in rows
    )


def _concept_params(concept: Concept) -> ConceptParams:
    return (
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
    )


def _list_sql(status: ConceptStatus | None, tag: str | None) -> str:
    sql = "select c.* from concepts c"
    if tag is not None:
        sql = (
            f"{sql} join concept_tags ct on ct.concept_id = c.id "
            "join tags t on t.id = ct.tag_id"
        )
    clauses: list[str] = []
    if status is not None:
        clauses.append("c.status = ?")
    if tag is not None:
        clauses.append("t.label = ?")
    if clauses:
        sql = f"{sql} where {' and '.join(clauses)}"
    return f"{sql} order by c.primary_term"


def _list_params(status: ConceptStatus | None, tag: str | None) -> tuple[str, ...]:
    params: list[str] = []
    if status is not None:
        params.append(status.value)
    if tag is not None:
        params.append(tag.strip().casefold())
    return tuple(params)
