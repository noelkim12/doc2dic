"""Typed SQLite row extraction helpers."""

import sqlite3
from typing import cast

SqlCell = str | int | float | bytes | None


def text_cell(row: sqlite3.Row, key: str) -> str:
    """Read a non-null text cell from a SQLite row."""
    value = cast("SqlCell", row[key])
    if not isinstance(value, str):
        msg = f"expected text column {key}"
        raise TypeError(msg)
    return value


def optional_text_cell(row: sqlite3.Row, key: str) -> str | None:
    """Read a nullable text cell from a SQLite row."""
    value = cast("SqlCell", row[key])
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"expected nullable text column {key}"
        raise TypeError(msg)
    return value


def int_cell(row: sqlite3.Row, key: str) -> int:
    """Read an integer cell from a SQLite row."""
    value = cast("SqlCell", row[key])
    if not isinstance(value, int):
        msg = f"expected integer column {key}"
        raise TypeError(msg)
    return value


def optional_int_cell(row: sqlite3.Row, key: str) -> int | None:
    """Read a nullable integer cell from a SQLite row."""
    value = cast("SqlCell", row[key])
    if value is None:
        return None
    if not isinstance(value, int):
        msg = f"expected nullable integer column {key}"
        raise TypeError(msg)
    return value


def float_cell(row: sqlite3.Row, key: str) -> float:
    """Read a numeric cell from a SQLite row."""
    value = cast("SqlCell", row[key])
    if isinstance(value, (int, float)):
        return float(value)
    msg = f"expected numeric column {key}"
    raise TypeError(msg)


def require_row(row: sqlite3.Row | None) -> sqlite3.Row:
    """Return a row or raise when a required SQL result is missing."""
    if row is None:
        msg = "expected SQLite row"
        raise LookupError(msg)
    return row
