"""Optional vector search facade."""

import sqlite3
from collections.abc import Sequence
from typing import cast

from doc2dic.storage.sqlite_rows import optional_int_cell, require_row, text_cell
from doc2dic.storage.vector_backend import JsonVectorBackend
from doc2dic.storage.vector_types import (
    StoredVector,
    VectorBackend,
    VectorBackendUnavailableError,
    VectorCapability,
    VectorMatch,
    VectorQueryResult,
    VectorWriteResult,
)

ENABLED_SETTING = "embedding_vectors_enabled"
DIMENSION_SETTING = "embedding_vectors_dimension"


class VectorStore:
    """Optional vector storage facade that preserves exact/fuzzy-only operation."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        backend: VectorBackend | None = None,
    ) -> None:
        """Store the SQLite connection and optional backend."""
        self._connection: sqlite3.Connection
        self._connection = connection
        self._backend: VectorBackend
        self._backend = backend or JsonVectorBackend()
        self._backend_loaded: bool
        self._backend_loaded = False

    def ensure_capability(self, *, dimension: int) -> VectorCapability:
        """Enable vector search when sqlite-vec is available."""
        if dimension <= 0:
            return self._disable(reason="embedding dimension must be positive")
        loaded = self._load_backend()
        if not loaded.enabled:
            return loaded

        configured_dimension = self._configured_dimension()
        if configured_dimension != dimension or not self._vector_table_exists():
            with self._connection:
                self._backend.create_table(self._connection, dimension)
                self._set_setting(ENABLED_SETTING, "true")
                self._set_setting(DIMENSION_SETTING, str(dimension))
        else:
            self._set_setting(ENABLED_SETTING, "true")
        return VectorCapability(
            enabled=True,
            reason="vector search enabled",
            dimension=dimension,
        )

    def upsert_vector(
        self,
        *,
        embedding_id: int,
        vector: Sequence[float],
    ) -> VectorWriteResult:
        """Write a vector row aligned to embeddings.id when vector search is enabled."""
        capability = self._current_capability()
        if not capability.enabled:
            return VectorWriteResult(enabled=False, reason=capability.reason)
        values = tuple(float(value) for value in vector)
        if len(values) != capability.dimension:
            reason = (
                f"vector dimension {len(values)} does not match configured dimension "
                f"{capability.dimension}"
            )
            return VectorWriteResult(enabled=False, reason=reason)
        if not self._embedding_exists(embedding_id):
            return VectorWriteResult(
                enabled=False,
                reason="embedding metadata row is missing",
            )
        with self._connection:
            self._backend.upsert_vector(
                self._connection,
                StoredVector(embedding_id=embedding_id, values=values),
            )
        return VectorWriteResult(enabled=True, reason="vector stored")

    def query_top_k(
        self,
        *,
        vector: Sequence[float],
        top_k: int,
    ) -> VectorQueryResult:
        """Return nearest embedding ids when vector search is enabled."""
        capability = self._current_capability()
        if not capability.enabled:
            return VectorQueryResult(
                enabled=False,
                reason=capability.reason,
                matches=(),
            )
        if top_k <= 0:
            return VectorQueryResult(
                enabled=True,
                reason="top_k must be positive",
                matches=(),
            )
        return self._query_enabled(vector=vector, top_k=top_k, capability=capability)

    def _query_enabled(
        self,
        *,
        vector: Sequence[float],
        top_k: int,
        capability: VectorCapability,
    ) -> VectorQueryResult:
        values = tuple(float(value) for value in vector)
        if len(values) != capability.dimension:
            reason = (
                f"query dimension {len(values)} does not match configured dimension "
                f"{capability.dimension}"
            )
            return VectorQueryResult(enabled=False, reason=reason, matches=())
        pairs = self._backend.query_top_k(self._connection, values, top_k)
        matches = tuple(
            VectorMatch(embedding_id=rowid, distance=distance)
            for rowid, distance in pairs
        )
        return VectorQueryResult(
            enabled=True,
            reason="vector search complete",
            matches=matches,
        )

    def _load_backend(self) -> VectorCapability:
        if self._backend_loaded:
            return VectorCapability(
                enabled=True,
                reason="vector backend loaded",
                dimension=None,
            )
        try:
            self._backend.load(self._connection)
        except VectorBackendUnavailableError as exc:
            return self._disable(reason=exc.reason)
        self._backend_loaded = True
        return VectorCapability(
            enabled=True,
            reason="vector backend loaded",
            dimension=None,
        )

    def _disable(self, *, reason: str) -> VectorCapability:
        self._set_setting(ENABLED_SETTING, "false")
        return VectorCapability(enabled=False, reason=reason, dimension=None)

    def _current_capability(self) -> VectorCapability:
        loaded = self._load_backend()
        if not loaded.enabled:
            return loaded
        if self._setting(ENABLED_SETTING) != "true":
            return VectorCapability(
                enabled=False,
                reason="vector search is disabled",
                dimension=None,
            )
        dimension = self._configured_dimension()
        if dimension is None:
            return VectorCapability(
                enabled=False,
                reason="vector dimension is not configured",
                dimension=None,
            )
        return VectorCapability(
            enabled=True,
            reason="vector search enabled",
            dimension=dimension,
        )

    def _configured_dimension(self) -> int | None:
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select value from settings where key = ?",
                (DIMENSION_SETTING,),
            ).fetchone(),
        )
        if row is None:
            return None
        return int(text_cell(row, "value"))

    def _setting(self, key: str) -> str | None:
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select value from settings where key = ?",
                (key,),
            ).fetchone(),
        )
        if row is None:
            return None
        return text_cell(row, "value")

    def _set_setting(self, key: str, value: str) -> None:
        _ = self._connection.execute(
            """
            insert into settings(key, value, updated_at)
            values (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            on conflict(key) do update set
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (key, value),
        )

    def _embedding_exists(self, embedding_id: int) -> bool:
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                "select 1 as exists_flag from embeddings where id = ?",
                (embedding_id,),
            ).fetchone(),
        )
        if row is None:
            return False
        return optional_int_cell(require_row(row), "exists_flag") == 1

    def _vector_table_exists(self) -> bool:
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                """
                select 1 as exists_flag from sqlite_master
                where type = 'table' and name = ?
                """,
                ("embedding_vectors",),
            ).fetchone(),
        )
        if row is None:
            return False
        return optional_int_cell(require_row(row), "exists_flag") == 1


__all__ = [
    "StoredVector",
    "VectorBackend",
    "VectorBackendUnavailableError",
    "VectorCapability",
    "VectorMatch",
    "VectorQueryResult",
    "VectorStore",
    "VectorWriteResult",
]
