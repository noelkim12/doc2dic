"""Shared API error response helpers."""

import re
import sqlite3
from typing import Final, TypedDict

from fastapi.responses import JSONResponse
from starlette import status

NOT_IMPLEMENTED_CODE: Final = "not_implemented"
NOT_IMPLEMENTED_MESSAGE: Final = "Route stub is not implemented yet."
DATABASE_LOCKED_CODE: Final = "database_locked"
DATABASE_LOCKED_MESSAGE: Final = (
    "The local glossary database is busy. Retry the request shortly."
)
MAX_ERROR_MESSAGE_CHARS: Final = 240
TRUNCATION_MARKER: Final = "..."
SECRET_PATTERN: Final = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{8,}|[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,})",
)
SQLITE_LOCK_MARKERS: Final = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
)


class ErrorBody(TypedDict):
    """API error body."""

    code: str
    message: str


class ErrorEnvelope(TypedDict):
    """Consistent API error envelope."""

    error: ErrorBody


def not_implemented_response() -> JSONResponse:
    """Return the uniform 501 response for contract stubs."""
    content = error_envelope(NOT_IMPLEMENTED_CODE, NOT_IMPLEMENTED_MESSAGE)
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=content,
    )


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Return a bounded, redacted API error envelope."""
    return JSONResponse(
        status_code=status_code,
        content=error_envelope(code, message),
    )


def error_envelope(code: str, message: str) -> ErrorEnvelope:
    """Build one consistent safe error envelope."""
    return {"error": {"code": code, "message": safe_error_message(message)}}


def safe_error_message(message: str) -> str:
    """Redact secret-like tokens and bound user-visible error text."""
    redacted = SECRET_PATTERN.sub("[redacted-secret]", message.strip())
    if len(redacted) <= MAX_ERROR_MESSAGE_CHARS:
        return redacted
    if ":" in redacted:
        prefix = redacted.split(":", maxsplit=1)[0].strip()
        return f"{prefix}: [truncated]"
    visible_chars = MAX_ERROR_MESSAGE_CHARS - len(TRUNCATION_MARKER)
    return f"{redacted[:visible_chars].rstrip()}{TRUNCATION_MARKER}"


def is_sqlite_lock_error(error: sqlite3.OperationalError) -> bool:
    """Return whether an OperationalError is SQLite lock contention."""
    lowered = str(error).lower()
    return any(marker in lowered for marker in SQLITE_LOCK_MARKERS)


def sqlite_lock_response() -> JSONResponse:
    """Return the friendly local database lock response."""
    return error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        DATABASE_LOCKED_CODE,
        DATABASE_LOCKED_MESSAGE,
    )
