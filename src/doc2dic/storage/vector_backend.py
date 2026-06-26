"""sqlite-vec backend for optional vector storage."""

import importlib
import sqlite3
from collections.abc import Sequence
from types import ModuleType
from typing import Protocol, cast

from doc2dic.storage.sqlite_rows import float_cell, int_cell
from doc2dic.storage.vector_types import StoredVector, VectorBackendUnavailableError


class SqliteVecModule(Protocol):
    """Runtime shape provided by the optional sqlite-vec Python package."""

    def load(self, connection: sqlite3.Connection) -> None:
        """Load sqlite-vec into a SQLite connection."""


class SqliteVecBackend:
    """sqlite-vec backed vector table operations."""

    def load(self, connection: sqlite3.Connection) -> None:
        """Load sqlite-vec only when vector capability is requested."""
        try:
            module = importlib.import_module("sqlite_vec")
        except ModuleNotFoundError as exc:
            raise VectorBackendUnavailableError(
                reason="sqlite-vec is not installed",
            ) from exc
        sqlite_vec = _sqlite_vec_module(module)
        sqlite_vec.load(connection)

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        """Create the sqlite-vec virtual table for the configured dimension."""
        _ = connection.execute("drop table if exists embedding_vectors")
        _ = connection.execute(
            f"""
            create virtual table embedding_vectors using vec0(
              embedding float[{dimension}]
            )
            """,
        )

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        """Insert or replace a sqlite-vec row using embedding id as rowid."""
        _ = connection.execute(
            "insert or replace into embedding_vectors(rowid, embedding) values (?, ?)",
            (vector.embedding_id, _vector_json(vector.values)),
        )

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        """Run sqlite-vec KNN search."""
        rows = cast(
            "list[sqlite3.Row]",
            connection.execute(
                """
                select rowid, distance
                from embedding_vectors
                where embedding match ?
                order by distance
                limit ?
                """,
                (_vector_json(vector), top_k),
            ).fetchall(),
        )
        return tuple(
            (int_cell(row, "rowid"), float_cell(row, "distance")) for row in rows
        )


def _sqlite_vec_module(module: ModuleType) -> SqliteVecModule:
    return cast("SqliteVecModule", cast("object", module))


def _vector_json(vector: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"
