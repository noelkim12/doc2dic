"""Embedding metadata SQLite repository."""

import sqlite3
from typing import cast

from doc2dic.domain import Embedding, EmbeddingOwnerType
from doc2dic.storage.sqlite_rows import int_cell, text_cell


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
        return Embedding(
            id=int_cell(row, "id"),
            owner_type=EmbeddingOwnerType(text_cell(row, "owner_type")),
            owner_id=text_cell(row, "owner_id"),
            model=text_cell(row, "model"),
            dimension=int_cell(row, "dimension"),
            content_hash=text_cell(row, "content_hash"),
            created_at=text_cell(row, "created_at"),
        )
