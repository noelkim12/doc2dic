# pyright: basic
"""Integration tests for concept API behavior."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import anyio
import pytest
from fastapi import FastAPI
from starlette.types import Message, Scope

from doc2dic.server.app import create_app
from doc2dic.storage import open_database
from doc2dic.storage.sqlite_rows import int_cell, require_row


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Minimal ASGI response captured from the local app."""

    status_code: int
    body: bytes

    def json(self) -> dict[str, str] | dict[str, dict[str, str]] | list[dict[str, str]]:
        """Decode the JSON response body."""
        return cast(
            "dict[str, str] | dict[str, dict[str, str]] | list[dict[str, str]]",
            json.loads(self.body.decode("utf-8")),
        )


async def _request_app(
    app: FastAPI,
    method: str,
    raw_path: str,
    body: dict[str, str] | None = None,
) -> ApiResponse:
    path, _, query = raw_path.partition("?")
    sent_request = False
    messages: list[Message] = []
    body_bytes = json.dumps(body or {}).encode("utf-8")

    async def receive() -> Message:
        nonlocal sent_request
        if sent_request:
            return {"type": "http.disconnect"}
        sent_request = True
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query.encode("ascii"),
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    await app(scope, receive, send)
    return _response_from_messages(messages)


def request_app(
    app: FastAPI,
    method: str,
    path: str,
    body: dict[str, str] | None = None,
) -> ApiResponse:
    """Call the FastAPI app through its ASGI surface without httpx."""
    return anyio.run(_request_app, app, method, path, body)


def test_concept_api_when_crud_flow_runs_returns_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    fastapi_app = create_app(project_root=tmp_path)

    create_response = request_app(
        fastapi_app,
        "post",
        "/api/concepts",
        {
            "primaryTerm": "Stamina",
            "definition": "Resource spent to enter dungeons.",
            "termType": "resource",
        },
    )
    create_body = cast("dict[str, str]", create_response.json())
    concept_id = create_body["id"]
    list_response = request_app(fastapi_app, "get", "/api/concepts?status=active")
    show_response = request_app(fastapi_app, "get", f"/api/concepts/{concept_id}")
    patch_response = request_app(
        fastapi_app,
        "patch",
        f"/api/concepts/{concept_id}",
        {"definition": "Action budget."},
    )
    variant_response = request_app(
        fastapi_app,
        "post",
        f"/api/concepts/{concept_id}/variants",
        {"label": "STA", "variantType": "abbreviation"},
    )
    delete_response = request_app(
        fastapi_app,
        "delete",
        f"/api/concepts/{concept_id}",
    )
    list_body = cast("list[dict[str, str]]", list_response.json())
    show_body = cast("dict[str, str]", show_response.json())
    patch_body = cast("dict[str, str]", patch_response.json())
    variant_body = cast("dict[str, str]", variant_response.json())

    assert create_response.status_code == 201
    assert concept_id.startswith("concept_")
    assert list_response.status_code == 200
    assert list_body[0]["primaryTerm"] == "Stamina"
    assert show_response.status_code == 200
    assert show_body["termType"] == "resource"
    assert patch_response.status_code == 200
    assert patch_body["definition"] == "Action budget."
    assert variant_response.status_code == 201
    assert variant_body["id"].startswith("variant_")
    assert delete_response.status_code == 204
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _table_count(connection, "embeddings") >= 1
        assert _table_count(connection, "embedding_vectors") >= 1


def test_concept_api_when_duplicate_variant_returns_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    fastapi_app = create_app(project_root=tmp_path)
    create_response = request_app(
        fastapi_app,
        "post",
        "/api/concepts",
        {"primaryTerm": "Health", "definition": "Hit points."},
    )
    create_body = cast("dict[str, str]", create_response.json())

    response = request_app(
        fastapi_app,
        "post",
        f"/api/concepts/{create_body['id']}/variants",
        {"label": "Health", "variantType": "alias"},
    )

    body = cast("dict[str, dict[str, str]]", response.json())

    assert response.status_code == 409
    assert body["error"]["code"] == "duplicate_term"


def _response_from_messages(messages: list[Message]) -> ApiResponse:
    status_code = 500
    body_parts: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            body_parts.append(bytes(message.get("body", b"")))
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))


def _table_count(
    connection: sqlite3.Connection,
    table_name: Literal["embeddings", "embedding_vectors"],
) -> int:
    match table_name:
        case "embeddings":
            sql = "select count(*) as count from embeddings"
        case "embedding_vectors":
            sql = "select count(*) as count from embedding_vectors"
    row = cast("sqlite3.Row | None", connection.execute(sql).fetchone())
    return int_cell(require_row(row), "count")
