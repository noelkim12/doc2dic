# pyright: basic
"""Integration tests for document and graph API routes."""

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

import anyio
from fastapi import FastAPI
from starlette.types import Message, Scope

from doc2dic.server.app import create_app

ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DB = ROOT / "tests" / "s2s_testdb" / "glossary.sqlite3"


class GraphEdgePayload(TypedDict):
    """Graph edge payload fields used by route assertions."""

    relation: str


class GraphPayload(TypedDict):
    """Graph payload fields used by route assertions."""

    edges: list[GraphEdgePayload]


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Minimal ASGI response captured from the local app."""

    status_code: int
    body: bytes

    def json(self) -> dict[str, object] | list[dict[str, object]]:
        """Decode the JSON response body."""
        return cast(
            "dict[str, object] | list[dict[str, object]]",
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


def test_document_routes_when_reference_db_is_copied_return_real_rows(
    tmp_path: Path,
) -> None:
    _copy_reference_database(tmp_path)
    fastapi_app = create_app(project_root=tmp_path)

    list_response = request_app(fastapi_app, "get", "/api/documents")
    list_body = cast("list[dict[str, object]]", list_response.json())
    document_id = cast("str", list_body[0]["id"])
    show_response = request_app(fastapi_app, "get", f"/api/documents/{document_id}")
    missing_response = request_app(fastapi_app, "get", "/api/documents/doc_missing")

    assert list_response.status_code == 200
    assert list_body[0]["path"] == "docs/00-core-combat-contract.md"
    assert list_body[0]["contentHash"] == (
        "8b0545673125e88ea8517c3e880a7c929029c2a7cda9924cbd99c1b58da88db0"
    )
    assert list_body[0]["mimeType"] == "text/markdown"
    assert len(cast("list[str]", list_body[0]["chunkIds"])) == 16
    assert show_response.status_code == 200
    assert show_response.json() == list_body[0]
    assert missing_response.status_code == 404
    assert cast("dict[str, object]", missing_response.json())["error"] == {
        "code": "document_not_found",
        "message": "Document doc_missing was not found.",
    }


def test_document_occurrences_when_rows_exist_returns_term_occurrences(
    tmp_path: Path,
) -> None:
    _copy_reference_database(tmp_path)
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    _insert_occurrence(db_path)
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(
        fastapi_app,
        "get",
        "/api/documents/doc_d0f5897825debb76/occurrences",
    )
    body = cast("list[dict[str, object]]", response.json())

    assert response.status_code == 200
    assert body == [
        {
            "id": "occ_reference_stamina",
            "documentId": "doc_d0f5897825debb76",
            "chunkId": "chunk_1d7c944c5aef990f",
            "conceptId": "concept_max_stamina",
            "surface": "Stamina",
            "offsetStart": 10,
            "offsetEnd": 17,
            "confidence": 0.99,
        },
    ]


def test_graph_routes_when_snapshot_exists_return_persisted_snapshots(
    tmp_path: Path,
) -> None:
    _copy_reference_database(tmp_path)
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    _insert_snapshot(db_path)
    fastapi_app = create_app(project_root=tmp_path)

    list_response = request_app(fastapi_app, "get", "/api/graphs/snapshots")
    show_response = request_app(
        fastapi_app,
        "get",
        "/api/graphs/snapshots/snapshot_reference",
    )
    missing_response = request_app(
        fastapi_app,
        "get",
        "/api/graphs/snapshots/snapshot_missing",
    )

    list_body = cast("list[dict[str, object]]", list_response.json())

    assert list_response.status_code == 200
    assert list_body[0]["id"] == "snapshot_reference"
    assert show_response.status_code == 200
    assert show_response.json() == list_body[0]
    assert missing_response.status_code == 404
    assert cast("dict[str, object]", missing_response.json())["error"] == {
        "code": "graph_snapshot_not_found",
        "message": "Graph snapshot snapshot_missing was not found.",
    }


def test_graph_routes_when_reference_db_has_supported_relations_return_graph(
    tmp_path: Path,
) -> None:
    _copy_reference_database(tmp_path)
    fastapi_app = create_app(project_root=tmp_path)

    current_response = request_app(fastapi_app, "get", "/api/graphs/current")
    rebuild_response = request_app(fastapi_app, "post", "/api/graphs/rebuild")

    current_body = cast("dict[str, object]", current_response.json())
    rebuild_body = cast("dict[str, object]", rebuild_response.json())
    current_graph = _graph_payload(current_body)
    rebuild_graph = _graph_payload(cast("dict[str, object]", rebuild_body["graph"]))
    current_relations = _relations(current_graph)
    rebuild_relations = _relations(rebuild_graph)

    assert current_response.status_code == 200
    assert rebuild_response.status_code == 202
    assert {"derives_from", "value_of"}.issubset(current_relations)
    assert current_relations == rebuild_relations
    assert cast("str", rebuild_body["id"]).startswith("snapshot_")

    snapshots_response = request_app(fastapi_app, "get", "/api/graphs/snapshots")
    snapshots = cast("list[dict[str, object]]", snapshots_response.json())

    assert snapshots_response.status_code == 200
    assert snapshots[0]["id"] == rebuild_body["id"]


def test_analyze_path_when_document_is_missing_returns_bounded_404(
    tmp_path: Path,
) -> None:
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(
        fastapi_app,
        "post",
        "/api/documents/analyze-path",
        {"path": "docs/missing.md"},
    )
    body = cast("dict[str, object]", response.json())

    assert response.status_code == 404
    assert body["error"] == {
        "code": "document_path_not_found",
        "message": "Document path docs/missing.md was not found.",
    }


def _copy_reference_database(project_root: Path) -> None:
    storage_dir = project_root / ".doc2dic"
    storage_dir.mkdir(parents=True)
    shutil.copy2(REFERENCE_DB, storage_dir / "glossary.sqlite3")


def _insert_occurrence(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            """
            insert into term_occurrences(
              id, document_id, chunk_id, concept_id, surface,
              offset_start, offset_end, confidence
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "occ_reference_stamina",
                "doc_d0f5897825debb76",
                "chunk_1d7c944c5aef990f",
                "concept_max_stamina",
                "Stamina",
                10,
                17,
                0.99,
            ),
        )


def _insert_snapshot(db_path: Path) -> None:
    graph_json = json.dumps(
        {
            "nodes": [
                {
                    "id": "concept_max_stamina",
                    "label": "Max Stamina",
                    "nodeType": "concept",
                    "termType": "stat",
                },
            ],
            "edges": [],
        },
    )
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            """
            insert into graph_snapshots(id, created_at, graph_json)
            values (?, ?, ?)
            """,
            ("snapshot_reference", "2026-06-25T00:00:00Z", graph_json),
        )


def _graph_payload(body: dict[str, object]) -> GraphPayload:
    return cast("GraphPayload", body)


def _relations(graph: GraphPayload) -> set[str]:
    return {edge["relation"] for edge in graph["edges"]}


def _response_from_messages(messages: list[Message]) -> ApiResponse:
    status_code = 500
    body_parts: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            body_parts.append(bytes(message.get("body", b"")))
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))
