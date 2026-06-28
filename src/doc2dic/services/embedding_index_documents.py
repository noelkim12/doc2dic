"""Document text extraction for concept embedding indexing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from doc2dic.domain import ConceptStatus, Embedding
from doc2dic.storage.json_codec import tuple_from_json_text
from doc2dic.storage.sqlite_rows import optional_text_cell, text_cell

if TYPE_CHECKING:
    import sqlite3

_HASH_SEPARATOR: Final = "\u241f"


@dataclass(frozen=True, slots=True)
class ActiveConceptDocument:
    """Active concept text prepared for embedding."""

    concept_id: str
    model: str
    text: str
    content_hash: str
    existing: Embedding | None = None


def active_concept_documents(
    connection: sqlite3.Connection,
    *,
    model: str,
) -> tuple[ActiveConceptDocument, ...]:
    """Return active concepts rendered as stable embedding documents."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            """
            select id, primary_term, definition, scope_note, non_goals_json,
              examples_json, tags_json from concepts where status = ? order by id
            """,
            (ConceptStatus.ACTIVE.value,),
        ).fetchall(),
    )
    return tuple(_document_from_row(row, model=model) for row in rows)


def _document_from_row(row: sqlite3.Row, *, model: str) -> ActiveConceptDocument:
    text = _document_text(row)
    return ActiveConceptDocument(
        concept_id=text_cell(row, "id"),
        model=model,
        text=text,
        content_hash=_content_hash(model=model, text=text),
    )


def _document_text(row: sqlite3.Row) -> str:
    sections = [
        f"Primary term: {text_cell(row, 'primary_term')}",
        f"Definition: {text_cell(row, 'definition')}",
    ]
    scope_note = optional_text_cell(row, "scope_note")
    if scope_note is not None and scope_note != "":
        sections.append(f"Scope note: {scope_note}")
    non_goals = tuple_from_json_text(text_cell(row, "non_goals_json"))
    if non_goals:
        sections.append(f"Non-goals: {'; '.join(non_goals)}")
    examples = tuple_from_json_text(text_cell(row, "examples_json"))
    if examples:
        sections.append(f"Examples: {'; '.join(examples)}")
    tags = tuple_from_json_text(text_cell(row, "tags_json"))
    if tags:
        sections.append(f"Tags: {', '.join(tags)}")
    return "\n".join(sections)


def _content_hash(*, model: str, text: str) -> str:
    return hashlib.sha256(f"{model}{_HASH_SEPARATOR}{text}".encode()).hexdigest()
