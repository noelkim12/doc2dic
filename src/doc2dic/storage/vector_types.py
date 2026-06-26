"""Vector storage data contracts."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class VectorBackendUnavailableError(RuntimeError):
    """Raised when a vector backend cannot be loaded."""

    def __init__(self, *, reason: str) -> None:
        """Store the unavailable reason."""
        super().__init__(reason)
        self.reason: str
        self.reason = reason


@dataclass(frozen=True, slots=True)
class StoredVector:
    """Vector payload aligned to an embedding metadata row."""

    embedding_id: int
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class VectorCapability:
    """Capability check result for optional vector search."""

    enabled: bool
    reason: str
    dimension: int | None


@dataclass(frozen=True, slots=True)
class VectorWriteResult:
    """Result of writing a vector row."""

    enabled: bool
    reason: str


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """Top-k vector match."""

    embedding_id: int
    distance: float


@dataclass(frozen=True, slots=True)
class VectorQueryResult:
    """Result of a vector top-k query."""

    enabled: bool
    reason: str
    matches: tuple[VectorMatch, ...]


class VectorBackend(Protocol):
    """Backend contract used by VectorStore."""

    def load(self, connection: sqlite3.Connection) -> None:
        """Load backend support into the connection."""
        ...

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        """Create a dimension-configured vector table."""
        ...

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        """Persist a vector with rowid aligned to the embedding id."""
        ...

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        """Return rowid and distance pairs ordered by nearest match."""
        ...
