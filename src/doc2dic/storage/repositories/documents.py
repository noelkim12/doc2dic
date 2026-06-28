"""Document SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.domain import (
    Document,
    DocumentChunk,
    DocumentMimeType,
    DocumentStatus,
    TermOccurrence,
)
from doc2dic.storage.json_codec import canonical_json, tuple_from_json_text
from doc2dic.storage.sqlite_rows import (
    float_cell,
    int_cell,
    optional_text_cell,
    text_cell,
)


class DocumentRepository:
    """Persist imported documents, chunks, and occurrences."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def upsert_document(self, document: Document) -> None:
        """Insert or replace document metadata."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into documents(
                  id, path, title, content_hash, mime_type, chunk_ids_json,
                  raw_text, status, analyzed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  path = excluded.path,
                  title = excluded.title,
                  content_hash = excluded.content_hash,
                  mime_type = excluded.mime_type,
                  chunk_ids_json = excluded.chunk_ids_json,
                  raw_text = excluded.raw_text,
                  status = excluded.status,
                  analyzed_at = excluded.analyzed_at
                """,
                (
                    document.id,
                    document.path,
                    document.title,
                    document.content_hash,
                    document.mime_type.value,
                    canonical_json(document.chunk_ids),
                    document.raw_text,
                    document.status.value,
                    document.analyzed_at,
                ),
            )

    def get_document(self, document_id: str) -> Document | None:
        """Return document metadata by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from documents where id = ?",
                (document_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return _document_from_row(row)

    def list_documents(self) -> tuple[Document, ...]:
        """Return document metadata ordered for stable API responses."""
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                "select * from documents order by analyzed_at desc, id",
            ).fetchall(),
        )
        return tuple(_document_from_row(row) for row in rows)

    def upsert_chunk(self, chunk: DocumentChunk) -> None:
        """Insert or replace a document chunk."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into document_chunks(
                  id, document_id, section_title, ordinal, text_preview,
                  content_hash, raw_text
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  document_id = excluded.document_id,
                  section_title = excluded.section_title,
                  ordinal = excluded.ordinal,
                  text_preview = excluded.text_preview,
                  content_hash = excluded.content_hash,
                  raw_text = excluded.raw_text
                """,
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.section_title,
                    chunk.ordinal,
                    chunk.text_preview,
                    chunk.content_hash,
                    chunk.raw_text,
                ),
            )

    def list_chunks(self, document_id: str) -> tuple[DocumentChunk, ...]:
        """Return chunks for a document in ordinal order."""
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                "select * from document_chunks where document_id = ? order by ordinal",
                (document_id,),
            ).fetchall(),
        )
        return tuple(_chunk_from_row(row) for row in rows)

    def upsert_occurrence(self, occurrence: TermOccurrence) -> None:
        """Insert or replace a term occurrence."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into term_occurrences(
                  id, document_id, chunk_id, concept_id, surface, offset_start,
                  offset_end, confidence
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  concept_id = excluded.concept_id,
                  surface = excluded.surface,
                  offset_start = excluded.offset_start,
                  offset_end = excluded.offset_end,
                  confidence = excluded.confidence
                """,
                (
                    occurrence.id,
                    occurrence.document_id,
                    occurrence.chunk_id,
                    occurrence.concept_id,
                    occurrence.surface,
                    occurrence.offset_start,
                    occurrence.offset_end,
                    occurrence.confidence,
                ),
            )

    def list_occurrences(self, document_id: str) -> tuple[TermOccurrence, ...]:
        """Return term occurrences for a document in text order."""
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select * from term_occurrences
                where document_id = ?
                order by offset_start, offset_end, id
                """,
                (document_id,),
            ).fetchall(),
        )
        return tuple(_occurrence_from_row(row) for row in rows)


def _document_from_row(row: sqlite3.Row) -> Document:
    return Document(
        id=text_cell(row, "id"),
        path=text_cell(row, "path"),
        title=text_cell(row, "title"),
        content_hash=text_cell(row, "content_hash"),
        mime_type=DocumentMimeType(text_cell(row, "mime_type")),
        chunk_ids=tuple_from_json_text(text_cell(row, "chunk_ids_json")),
        raw_text=text_cell(row, "raw_text"),
        status=DocumentStatus(text_cell(row, "status")),
        analyzed_at=text_cell(row, "analyzed_at"),
    )


def _chunk_from_row(row: sqlite3.Row) -> DocumentChunk:
    return DocumentChunk(
        id=text_cell(row, "id"),
        document_id=text_cell(row, "document_id"),
        section_title=text_cell(row, "section_title"),
        ordinal=int_cell(row, "ordinal"),
        text_preview=text_cell(row, "text_preview"),
        content_hash=text_cell(row, "content_hash"),
        raw_text=text_cell(row, "raw_text"),
    )


def _occurrence_from_row(row: sqlite3.Row) -> TermOccurrence:
    return TermOccurrence(
        id=text_cell(row, "id"),
        document_id=text_cell(row, "document_id"),
        chunk_id=text_cell(row, "chunk_id"),
        concept_id=optional_text_cell(row, "concept_id"),
        surface=text_cell(row, "surface"),
        offset_start=int_cell(row, "offset_start"),
        offset_end=int_cell(row, "offset_end"),
        confidence=float_cell(row, "confidence"),
    )
