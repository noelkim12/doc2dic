"""Deterministic offline embedding helpers."""

from __future__ import annotations

import hashlib


def deterministic_vector(text: str, model: str, dimension: int) -> tuple[float, ...]:
    """Return a repeatable pseudo-embedding vector for tests and offline mode."""
    seed = f"{model}\n{text}".encode()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for byte in digest:
            values.append(round((byte / 127.5) - 1.0, 6))
            if len(values) == dimension:
                break
        counter += 1
    return tuple(values)
