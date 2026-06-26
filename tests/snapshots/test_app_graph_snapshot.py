# pyright: basic
"""Snapshot-style tests for AppGraph JSON surfaces."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import anyio
from fastapi import FastAPI
from starlette.types import Message, Scope
from tests.unit.services.test_graph_projection_service import seed_graph_fixture

from doc2dic.server.app import create_app
from doc2dic.services.graph_projection_service import GraphProjectionService
from doc2dic.storage import open_database
from doc2dic.storage.repositories.graphs import GraphRepository


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status_code: int
    body: bytes

    def json(self) -> dict[str, object]:
        return cast("dict[str, object]", json.loads(self.body.decode("utf-8")))


async def _request_app(app: FastAPI, raw_path: str) -> ApiResponse:
    sent_request = False
    messages: list[Message] = []

    async def receive() -> Message:
        nonlocal sent_request
        if sent_request:
            return {"type": "http.disconnect"}
        sent_request = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": raw_path,
        "raw_path": raw_path.encode("ascii"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    await app(scope, receive, send)
    return _response_from_messages(messages)


def test_graph_snapshot_when_exported_repeatedly_has_stable_contract_json(
    tmp_path: Path,
) -> None:
    fastapi_app = create_app(project_root=tmp_path)
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        seed_graph_fixture(connection)
        snapshot = GraphProjectionService(connection).persist_current_snapshot()
        loaded = GraphRepository(connection).get_snapshot(snapshot.id)

    assert loaded == snapshot
    assert json.loads(snapshot.model_dump_json(by_alias=True)) == {
        "id": snapshot.id,
        "createdAt": "2026-06-25T00:00:00Z",
        "graph": _expected_graph_body(),
    }
    response = anyio.run(_request_app, fastapi_app, "/api/graphs/current")
    assert response.status_code == 200
    assert response.json() == _expected_graph_body()


def _expected_graph_body() -> dict[str, object]:
    return {
        "nodes": [
            {
                "id": "concept_combat_stamina",
                "label": "combat.stamina",
                "nodeType": "concept",
                "termType": "resource",
            },
            {
                "id": "concept_dodge_roll",
                "label": "Dodge Roll",
                "nodeType": "concept",
                "termType": "action",
            },
            {
                "id": "concept_entry_stamina",
                "label": "Entry Stamina",
                "nodeType": "concept",
                "termType": "resource",
            },
        ],
        "edges": [
            {
                "id": "edge_57fd1a699b04e044",
                "source": "concept_combat_stamina",
                "target": "concept_combat_stamina",
                "relation": "alias_of",
            },
            {
                "id": "edge_05cf9aad12334eed",
                "source": "concept_combat_stamina",
                "target": "concept_entry_stamina",
                "relation": "contradicts",
            },
            {
                "id": "edge_2344f86414a866c6",
                "source": "concept_combat_stamina",
                "target": "concept_dodge_roll",
                "relation": "depends_on",
            },
        ],
    }


def _response_from_messages(messages: list[Message]) -> ApiResponse:
    status_code = 500
    body_parts: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            body_parts.append(bytes(message.get("body", b"")))
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))
