# pyright: basic
"""Integration tests for the local FastAPI contract shell."""

import json
from dataclasses import dataclass
from pathlib import Path

import anyio
import yaml
from fastapi import FastAPI
from starlette.types import Message, Scope

from doc2dic.server.app import create_app

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Minimal ASGI response captured from the local app."""

    status_code: int
    body: bytes

    def json(self) -> dict[str, dict[str, str]] | dict[str, str]:
        return json.loads(self.body.decode("utf-8"))


def _contract_paths() -> set[str]:
    with (ROOT / "contracts" / "openapi.yaml").open(encoding="utf-8") as openapi_file:
        openapi = yaml.safe_load(openapi_file)
    return set(openapi["paths"])


async def _request_app(app: FastAPI, method: str, raw_path: str) -> ApiResponse:
    path, _, query = raw_path.partition("?")
    sent_request = False
    messages: list[Message] = []

    async def receive() -> Message:
        nonlocal sent_request
        if sent_request:
            return {"type": "http.disconnect"}
        sent_request = True
        return {"type": "http.request", "body": b"{}", "more_body": False}

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
    status_code = 500
    body_parts: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            body_parts.append(bytes(message.get("body", b"")))
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))


def request_app(app: FastAPI, method: str, path: str) -> ApiResponse:
    """Call the FastAPI app through its ASGI surface without httpx."""
    return anyio.run(_request_app, app, method, path)


def test_app_openapi_paths_match_contract_when_created(tmp_path: Path) -> None:
    """Given app factory, when app is created, then paths match OpenAPI."""
    fastapi_app = create_app(project_root=tmp_path)

    assert set(fastapi_app.openapi()["paths"]) == _contract_paths()
    assert "/api/graphs/graphify/import" not in fastapi_app.openapi()["paths"]


def test_health_returns_success_schema_when_called(tmp_path: Path) -> None:
    """Given local API app, when health is called, then success schema returns."""
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(fastapi_app, "get", "/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_issue_action_routes_require_body_in_app_openapi(tmp_path: Path) -> None:
    """Given app OpenAPI, when issue actions are inspected, then bodies are present."""
    fastapi_app = create_app(project_root=tmp_path)
    openapi = fastapi_app.openapi()

    for path in (
        "/api/issues/{issue_id}/accept",
        "/api/issues/{issue_id}/dismiss",
        "/api/issues/{issue_id}/resolve-as-new-concept",
        "/api/issues/{issue_id}/resolve-as-alias",
        "/api/issues/{issue_id}/resolve-as-forbidden",
    ):
        operation = openapi["paths"][path]["post"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        response_schema = operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert schema == {"$ref": "#/components/schemas/IssueActionBody"}
        assert response_schema == {"$ref": "#/components/schemas/IssueActionPayload"}


def test_graphify_export_returns_projection_schema_when_called(
    tmp_path: Path,
) -> None:
    """Given local API app, when Graphify export is called, then projection returns."""
    fastapi_app = create_app(project_root=tmp_path)

    response = request_app(fastapi_app, "post", "/api/graphs/graphify/export")

    assert response.status_code == 200
    assert response.json() == {"graph": {"nodes": [], "edges": []}, "documents": []}


def test_contract_routes_return_501_schema_when_called(tmp_path: Path) -> None:
    """Given contract stubs, when called, then explicit 501 schema returns."""
    fastapi_app = create_app(project_root=tmp_path)

    routes = (
        ("patch", "/api/variants/variant_dash"),
        ("delete", "/api/variants/variant_dash"),
        ("post", "/api/documents/analyze-path"),
        ("get", "/api/documents"),
        ("get", "/api/documents/doc_design"),
        ("get", "/api/documents/doc_design/occurrences"),
        ("get", "/api/search/concepts?q=dash"),
        ("get", "/api/search/similar-concepts?text=dash"),
        ("post", "/api/graphs/rebuild"),
        ("get", "/api/graphs/snapshots"),
        ("get", "/api/graphs/snapshots/snapshot_current"),
    )

    for method, path in routes:
        response = request_app(fastapi_app, method, path)
        assert response.status_code == 501, path
        assert response.json() == {
            "error": {
                "code": "not_implemented",
                "message": "Route stub is not implemented yet.",
            },
        }
