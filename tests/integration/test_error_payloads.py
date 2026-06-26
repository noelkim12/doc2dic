"""API error payload privacy and consistency checks."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, TypedDict, cast

from tests.integration.server.test_app_contract import request_app

from doc2dic.server import routes_graphs, routes_issues
from doc2dic.server.app import create_app
from doc2dic.services.graph_projection_service import GraphProjectionError

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class ErrorPayload(TypedDict):
    """Typed API error payload for assertions."""

    code: str
    message: str


class ErrorEnvelope(TypedDict):
    """Typed API error envelope for assertions."""

    error: ErrorPayload


RAW_DOCUMENT_TEXT = "raw document text " + "경직 상태 원문 " * 90


class LockedReviewService:
    """Review service fake that simulates a locked SQLite writer."""

    def __init__(self, database: sqlite3.Connection) -> None:
        _ = database

    def list_issues(self, *, status: object = None) -> tuple[()]:
        _ = status
        message = f"database is locked: {RAW_DOCUMENT_TEXT}"
        raise sqlite3.OperationalError(message)


class BrokenGraphProjectionService:
    """Graph service fake that raises a raw-text projection failure."""

    def __init__(self, database: sqlite3.Connection) -> None:
        _ = database

    def persist_current_snapshot(self) -> object:
        message = f"bad graph relation: {RAW_DOCUMENT_TEXT}"
        raise GraphProjectionError(message)


def test_api_error_payload_when_sqlite_is_locked_is_friendly_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes_issues, "ReviewService", LockedReviewService)
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(fastapi_app, "get", "/api/issues")

    body = cast("ErrorEnvelope", cast("object", response.json()))

    assert response.status_code == 503
    assert body == {
        "error": {
            "code": "database_locked",
            "message": (
                "The local glossary database is busy. Retry the request shortly."
            ),
        },
    }
    assert "경직 상태 원문" not in response.body.decode("utf-8")


def test_api_error_payload_when_service_error_contains_raw_document_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes_graphs,
        "GraphProjectionService",
        BrokenGraphProjectionService,
    )
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(fastapi_app, "get", "/api/graphs/current")
    body = cast("ErrorEnvelope", cast("object", response.json()))
    forbidden_excerpt = "경직 상태 원문 경직 상태 원문 경직 상태 원문"

    assert response.status_code == 422
    assert body["error"]["code"] == "invalid_graph_relation"
    assert len(body["error"]["message"]) <= 240
    assert forbidden_excerpt not in body["error"]["message"]
