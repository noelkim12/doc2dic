"""Canonical JSON helpers for SQLite text columns."""

import json
from collections.abc import Mapping, Sequence
from typing import cast

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | Sequence["JsonValue"] | Mapping[str, "JsonValue"]


def canonical_json(value: JsonValue) -> str:
    """Return deterministic JSON text for persisted JSON columns."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def tuple_from_json_text(text: str) -> tuple[str, ...]:
    """Parse a JSON string array into an immutable tuple."""
    parsed = cast("JsonValue", json.loads(text))
    if not isinstance(parsed, list):
        msg = "expected JSON array"
        raise TypeError(msg)
    items = cast("Sequence[JsonScalar]", parsed)
    return tuple(str(item) for item in items)
