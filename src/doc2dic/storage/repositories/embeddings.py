"""Embedding metadata SQLite repository."""

import sqlite3
from dataclasses import dataclass
from typing import cast

from doc2dic.domain import Embedding, EmbeddingOwnerType
from doc2dic.storage.sqlite_rows import int_cell, text_cell


@dataclass(frozen=True, slots=True)
class EmbeddingLookup:
    """Stable key for reusable embedding metadata rows."""

    owner_type: EmbeddingOwnerType
    owner_id: str
    model: str
    content_hash: str


class EmbeddingRepository:
    """Persist embedding metadata without sqlite-vec dependency."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def upsert_embedding(self, embedding: Embedding) -> None:
        """Insert or replace embedding metadata."""
        with self._connection:
            _ = self._connection.execute(
                """
                insert into embeddings(
                  id, owner_type, owner_id, model, dimension, content_hash, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  owner_type = excluded.owner_type,
                  owner_id = excluded.owner_id,
                  model = excluded.model,
                  dimension = excluded.dimension,
                  content_hash = excluded.content_hash
                """,
                (
                    embedding.id,
                    embedding.owner_type.value,
                    embedding.owner_id,
                    embedding.model,
                    embedding.dimension,
                    embedding.content_hash,
                    embedding.created_at,
                ),
            )

    def get_embedding(self, embedding_id: int) -> Embedding | None:
        """Return embedding metadata by id."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select * from embeddings where id = ?",
                (embedding_id,),
            ).fetchone(),
        )
        if row is None:
            return None
        return _embedding_from_row(row)

    def find_existing_embedding(self, lookup: EmbeddingLookup) -> Embedding | None:
        """Return reusable embedding metadata for the exact owner/model/hash key."""
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                """
                select * from embeddings
                where owner_type = ?
                  and owner_id = ?
                  and model = ?
                  and content_hash = ?
                order by id desc
                limit 1
                """,
                (
                    lookup.owner_type.value,
                    lookup.owner_id,
                    lookup.model,
                    lookup.content_hash,
                ),
            ).fetchone(),
        )
        if row is None:
            return None
        return _embedding_from_row(row)

    def next_embedding_id(self) -> int:
        """Return the next integer embedding id for local metadata inserts."""
        row = cast(
            "sqlite3.Row",
            self._connection.execute(
                "select coalesce(max(id), 0) + 1 as next_id from embeddings",
            ).fetchone(),
        )
        return int_cell(row, "next_id")


def _embedding_from_row(row: sqlite3.Row) -> Embedding:
    return Embedding(
        id=int_cell(row, "id"),
        owner_type=EmbeddingOwnerType(text_cell(row, "owner_type")),
        owner_id=text_cell(row, "owner_id"),
        model=text_cell(row, "model"),
        dimension=int_cell(row, "dimension"),
        content_hash=text_cell(row, "content_hash"),
        created_at=text_cell(row, "created_at"),
    )
