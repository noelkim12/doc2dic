# pyright: basic
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import anyio
from fastapi import FastAPI
from starlette.types import Message, Scope

from doc2dic.domain import (
    ConceptTermType,
    IssueEvidence,
    IssueEvidenceKind,
    TermIssue,
    TermIssueType,
)
from doc2dic.server.app import create_app
from doc2dic.services.glossary_service import CreateConceptInput, GlossaryService
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage import open_database
from doc2dic.storage.repositories.issues import IssueRepository


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status_code: int
    body: bytes


def test_issue_api_when_resolve_new_concept_replayed_has_no_duplicates(
    tmp_path: Path,
) -> None:
    fastapi_app = create_app(project_root=tmp_path)
    _seed_issue(tmp_path, "issue_energy", "Energy")
    body = {
        "expectedVersion": 0,
        "idempotencyKey": "api-new-1",
        "term": "Energy",
        "definition": "Resource spent on actions.",
    }

    list_response = request_app(fastapi_app, "get", "/api/issues?status=open")
    show_response = request_app(fastapi_app, "get", "/api/issues/issue_energy")
    first_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_energy/resolve-as-new-concept",
        body,
    )
    replay_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_energy/resolve-as-new-concept",
        body,
    )

    first_body = cast("dict[str, object]", json.loads(first_response.body))
    replay_body = cast("dict[str, object]", json.loads(replay_response.body))
    list_body = cast("list[dict[str, object]]", json.loads(list_response.body))
    show_body = cast("dict[str, object]", json.loads(show_response.body))

    assert list_response.status_code == 200
    assert list_body[0]["id"] == "issue_energy"
    assert show_response.status_code == 200
    assert show_body["version"] == 0
    assert first_response.status_code == 200
    assert first_body["outcome"] == "applied"
    assert first_body["conceptId"] == "concept_energy"
    assert cast("dict[str, object]", first_body["issue"])["version"] == 1
    assert (
        cast("dict[str, object]", first_body["issue"])["appliedIdempotencyKey"]
        == "api-new-1"
    )
    assert replay_response.status_code == 200
    assert replay_body["outcome"] == "already_applied"
    assert cast("dict[str, object]", replay_body["issue"])["version"] == 1
    assert _count_rows(tmp_path, "concepts") == 1
    assert _count_rows(tmp_path, "term_variants") == 1


def test_issue_api_when_alias_forbidden_and_dismiss_run_return_action_payloads(
    tmp_path: Path,
) -> None:
    fastapi_app = create_app(project_root=tmp_path)
    _seed_concept(tmp_path, "Health", "Hit points.")
    _seed_issue(tmp_path, "issue_hp", "HP")
    _seed_issue(tmp_path, "issue_life", "Life")
    _seed_issue(tmp_path, "issue_noise", "Noise")

    alias_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_hp/resolve-as-alias",
        {
            "expectedVersion": 0,
            "idempotencyKey": "api-alias-1",
            "conceptId": "concept_health",
            "variant": "HP",
        },
    )
    forbidden_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_life/resolve-as-forbidden",
        {
            "expectedVersion": 0,
            "idempotencyKey": "api-forbidden-1",
            "conceptId": "concept_health",
            "variant": "Life",
        },
    )
    dismiss_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_noise/dismiss",
        {
            "expectedVersion": 0,
            "idempotencyKey": "api-dismiss-1",
            "reason": "not relevant",
        },
    )

    alias_body = cast("dict[str, object]", json.loads(alias_response.body))
    forbidden_body = cast("dict[str, object]", json.loads(forbidden_response.body))
    dismiss_body = cast("dict[str, object]", json.loads(dismiss_response.body))

    assert alias_response.status_code == 200
    assert alias_body["variantId"] == "variant_hp"
    assert alias_body["outcome"] == "applied"
    assert forbidden_response.status_code == 200
    assert forbidden_body["variantId"] == "variant_life"
    assert forbidden_body["outcome"] == "applied"
    assert dismiss_response.status_code == 200
    assert dismiss_body["outcome"] == "applied"


def test_issue_api_when_stale_or_closed_returns_conflict(tmp_path: Path) -> None:
    fastapi_app = create_app(project_root=tmp_path)
    _seed_issue(tmp_path, "issue_stale", "Stale")

    stale_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_stale/dismiss",
        {"expectedVersion": 4, "idempotencyKey": "api-stale", "reason": "old"},
    )
    _ = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_stale/dismiss",
        {"expectedVersion": 0, "idempotencyKey": "api-close", "reason": "done"},
    )
    closed_response = request_app(
        fastapi_app,
        "post",
        "/api/issues/issue_stale/dismiss",
        {"expectedVersion": 1, "idempotencyKey": "api-closed", "reason": "again"},
    )

    stale_body = cast("dict[str, dict[str, str]]", json.loads(stale_response.body))
    closed_body = cast("dict[str, dict[str, str]]", json.loads(closed_response.body))
    assert stale_response.status_code == 409
    assert stale_body["error"]["code"] == "stale_version"
    assert closed_response.status_code == 409
    assert closed_body["error"]["code"] == "issue_closed"


async def _request_app(
    app: FastAPI,
    method: str,
    raw_path: str,
    body: dict[str, object] | None = None,
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
    body: dict[str, object] | None = None,
) -> ApiResponse:
    return anyio.run(_request_app, app, method, path, body)


def _response_from_messages(messages: list[Message]) -> ApiResponse:
    status_code = 500
    body_parts: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            body_parts.append(bytes(message.get("body", b"")))
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))


def _seed_concept(tmp_path: Path, term: str, definition: str) -> None:
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        _ = GlossaryService(connection).create_concept(
            CreateConceptInput(term, definition, ConceptTermType.UNKNOWN),
        )


def _seed_issue(tmp_path: Path, issue_id: str, surface: str) -> None:
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        issue = TermIssue(
                id=issue_id,
                issue_type=TermIssueType.UNKNOWN_TERM,
                status=IssueStatus.OPEN,
                surface=surface,
                evidence=(
                    IssueEvidence(
                        id=f"evidence_{issue_id.removeprefix('issue_')}",
                        kind=IssueEvidenceKind.QUOTE,
                        source_document_id="doc_api_seed",
                        quote=surface,
                        confidence=0.8,
                    ),
                ),
                created_at="2026-06-25T00:00:00Z",
            )
        with connection:
            _ = connection.execute(
                """
                insert or ignore into documents(
                  id, path, title, content_hash, mime_type, chunk_ids_json, raw_text,
                  status, analyzed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "doc_api_seed",
                    "seed.md",
                    "Seed",
                    "hash",
                    "text/markdown",
                    "[]",
                    "",
                    "analyzed",
                    "2026-06-25T00:00:00Z",
                ),
            )
            IssueRepository(connection).upsert_issue(issue)


def _count_rows(
    tmp_path: Path,
    table_name: Literal["concepts", "term_variants"],
) -> int:
    match table_name:
        case "concepts":
            sql = "select count(*) from concepts"
        case "term_variants":
            sql = "select count(*) from term_variants"
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        row = connection.execute(sql).fetchone()
    if row is None:
        message = "count row missing"
        raise AssertionError(message)
    return int(row[0])
