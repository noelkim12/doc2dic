"""Security regression tests for bounded errors and privacy surfaces."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from email.message import Message
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.domain import IssueEvidence, IssueEvidenceKind
from doc2dic.server.errors import safe_error_message
from doc2dic.services.auth_store import AuthFile, save_auth_file
from doc2dic.services.document_context_cards import DocumentContextInput
from doc2dic.services.embedding_config import (
    embedding_provider_config_from_project,
    embedding_provider_from_project,
)
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingFailureCode,
    EmbeddingInputType,
    EmbeddingService,
    embedding_provider_from_environment,
)
from doc2dic.services.embedding_voyage import (
    VoyageEmbeddingProvider,
    VoyageEmbeddingProviderConfig,
)
from doc2dic.services.llm_service import (
    AnalysisFailure,
    AnalysisFailureCode,
    LLMTermExtractionService,
    llm_provider_from_environment,
)
from doc2dic.storage.repositories import SettingsRepository

if TYPE_CHECKING:
    import urllib.request
    from collections.abc import Iterable


RAW_DOCUMENT_TEXT = "raw-document-start " + "전투 원문 누출 방지 " * 80
SECRET_VALUE = "sk-test-doc2dic-secret-1234567890"  # noqa: S105
VOYAGE_SECRET_VALUE = "sk-test-doc2dic-voyage-secret"  # noqa: S105
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class SecretHttpErrorOpener:
    error: HTTPError

    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> NoReturn:
        _ = request
        _ = timeout
        raise self.error


def test_safe_error_message_redacts_raw_document_and_secret() -> None:
    message = f"provider failed with {SECRET_VALUE}: {RAW_DOCUMENT_TEXT}"

    safe_message = safe_error_message(message)
    forbidden_excerpt = "전투 원문 누출 방지 전투 원문 누출 방지 전투 원문 누출 방지"

    assert SECRET_VALUE not in safe_message
    assert forbidden_excerpt not in safe_message
    assert "[redacted-secret]" in safe_message
    assert len(safe_message) <= 240


def test_issue_evidence_contract_rejects_unbounded_quote_and_context() -> None:
    with pytest.raises(ValidationError):
        _ = IssueEvidence(
            id="evidence_too_long",
            kind=IssueEvidenceKind.QUOTE,
            source_document_id="doc_security",
            quote="q" * 601,
            context_before="before",
            context_after="after",
            confidence=1.0,
        )

    with pytest.raises(ValidationError):
        _ = IssueEvidence(
            id="evidence_context_too_long",
            kind=IssueEvidenceKind.QUOTE,
            source_document_id="doc_security",
            quote="bounded quote",
            context_before="b" * 241,
            context_after="after",
            confidence=1.0,
        )


def test_provider_failures_when_fake_api_keys_are_set_do_not_echo_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_LLM_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_API_KEY", SECRET_VALUE)

    llm_result = LLMTermExtractionService(
        llm_provider_from_environment(),
    ).extract_terms(_sample_document())
    embedding_result = EmbeddingService(
        embedding_provider_from_environment(),
    ).embed_texts(("스태미나",))

    assert isinstance(llm_result, AnalysisFailure)
    assert llm_result.code is AnalysisFailureCode.PROVIDER_DISABLED
    assert isinstance(embedding_result, EmbeddingFailure)
    assert embedding_result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    messages = (llm_result.message, embedding_result.message)
    assert SECRET_VALUE not in _joined_messages(messages)


def test_voyage_http_error_body_and_headers_do_not_echo_secret_values() -> None:
    headers = Message()
    headers["Authorization"] = f"Bearer {VOYAGE_SECRET_VALUE}"
    error = HTTPError(
        url="https://api.voyageai.com/v1/embeddings",
        code=HTTPStatus.TOO_MANY_REQUESTS,
        msg="Too Many Requests",
        hdrs=headers,
        fp=BytesIO(
            b'{"error":"sk-test-doc2dic-voyage-secret Authorization Bearer"}',
        ),
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=VOYAGE_SECRET_VALUE),
        opener=SecretHttpErrorOpener(error),
    )

    result = EmbeddingService(provider).embed_texts(
        ("스태미나",),
        input_type=EmbeddingInputType.QUERY,
    )

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_ERROR
    message = result.message
    assert "status=429" in message
    assert VOYAGE_SECRET_VALUE not in message
    assert "Authorization" not in message
    assert "Bearer" not in message


def test_voyage_resolver_repr_and_sqlite_settings_do_not_echo_secret_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _settings_connection()
    settings = SettingsRepository(connection)
    settings.set_value("embedding.provider", "voyage")
    settings.set_value("embedding.model", "voyage-security-model")
    auth_path = tmp_path / "auth.json"
    _ = save_auth_file(
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-voyage-model",
            api_key=VOYAGE_SECRET_VALUE,
        ),
        auth_path,
    )
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_path))
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_PROVIDER", raising=False)

    config = embedding_provider_config_from_project(connection)
    provider = embedding_provider_from_project(connection)

    assert config.api_key == VOYAGE_SECRET_VALUE
    _assert_secret_absent(repr(config), str(config), repr(provider))
    _assert_sqlite_settings_do_not_contain_secret(connection)


def test_analyze_failure_cli_output_does_not_echo_voyage_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_LLM_API_KEY", VOYAGE_SECRET_VALUE)
    init_result = runner.invoke(app, ["init"])
    analyze_result = runner.invoke(
        app,
        ["analyze", str(ROOT / "samples" / "docs" / "combat_core.md")],
    )

    assert init_result.exit_code == 0
    assert analyze_result.exit_code == 0
    assert "Analysis failure: provider_disabled" in analyze_result.output
    _assert_secret_absent(
        init_result.output,
        analyze_result.output,
        str(analyze_result.exception),
    )


def _joined_messages(messages: Iterable[str]) -> str:
    return "\n".join(messages)


def _assert_secret_absent(*surfaces: str) -> None:
    for surface in surfaces:
        assert VOYAGE_SECRET_VALUE not in surface


def _assert_sqlite_settings_do_not_contain_secret(
    connection: sqlite3.Connection,
) -> None:
    rows: list[sqlite3.Row] = connection.execute(
        "select key, value from settings",
    ).fetchall()
    for row in rows:
        assert VOYAGE_SECRET_VALUE not in f"{row['key']}={row['value']}"


def _settings_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    _ = connection.execute(
        """
        create table settings(
          key text primary key,
          value text not null,
          updated_at text not null
        )
        """,
    )
    return connection


def _sample_document() -> DocumentContextInput:
    path = ROOT / "samples" / "docs" / "combat_core.md"
    text = path.read_text(encoding="utf-8")
    return DocumentContextInput(
        document_id="combat_core",
        path="samples/docs/combat_core.md",
        title=text.splitlines()[0].removeprefix("# "),
        text=text,
    )
