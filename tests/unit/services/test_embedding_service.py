from __future__ import annotations

import sqlite3
import urllib.request
from dataclasses import dataclass
from email.message import Message
from http import HTTPStatus
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar, Self
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict

from doc2dic.services.auth_store import AuthFile, save_auth_file
from doc2dic.services.embedding_config import (
    VOYAGE_API_KEY_ENV,
    embedding_provider_config_from_project,
    embedding_provider_from_project,
)
from doc2dic.services.embedding_service import (
    DeterministicMockEmbeddingProvider,
    DisabledEmbeddingProvider,
    EmbeddingFailure,
    EmbeddingFailureCode,
    EmbeddingInputType,
    EmbeddingProviderConfig,
    EmbeddingProviderDisabledError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingSuccess,
    EmbeddingVector,
    embedding_provider_from_environment,
)
from doc2dic.services.embedding_voyage import (
    VoyageEmbeddingProvider,
    VoyageEmbeddingProviderConfig,
)
from doc2dic.storage.repositories import SettingsRepository

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    import pytest


FAKE_VOYAGE_API_KEY = "fake-voyage-ci-key"
FAKE_VOYAGE_SECRET = "sk-test-doc2dic-voyage-secret"  # noqa: S105
SAFE_ERROR_FORBIDDEN_PARTS = (
    FAKE_VOYAGE_SECRET,
    "Authorization",
    "Bearer",
    "full-request-body",
)


@dataclass(frozen=True, slots=True)
class WrongDimensionProvider:
    provider_name: str = "wrong_dimension"
    model: str = "wrong-model"
    dimension: int = 3

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        _ = input_type
        return tuple(
            EmbeddingVector(text=text, model=self.model, values=(0.1, 0.2))
            for text in texts
        )


@dataclass(frozen=True, slots=True)
class DirectDisabledProvider:
    provider_name: str = "direct_disabled"
    model: str = "disabled"
    dimension: int = 3

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        _ = texts
        _ = input_type
        message = "disabled for test"
        raise EmbeddingProviderDisabledError(message)


class RecordingProvider:
    provider_name: str = "recording"
    model: str = "recording-model"
    dimension: int = 2

    def __init__(self) -> None:
        self.input_types: list[EmbeddingInputType] = []

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        self.input_types.append(input_type)
        return tuple(
            EmbeddingVector(text=text, model=self.model, values=(0.1, 0.2))
            for text in texts
        )


@dataclass(frozen=True, slots=True)
class FakeVoyageResponse:
    body: bytes

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type
        _ = exc
        _ = traceback


class FakeVoyageOpener:
    def __init__(self, response_body: bytes) -> None:
        self._response_body: bytes = response_body
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> FakeVoyageResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return FakeVoyageResponse(self._response_body)


@dataclass(frozen=True, slots=True)
class ErrorVoyageOpener:
    error: HTTPError | URLError | TimeoutError

    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> FakeVoyageResponse:
        _ = request
        _ = timeout
        raise self.error


def _voyage_response_body(data: str) -> bytes:
    return data.encode()


class CapturedVoyageRequestBody(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    input: tuple[str, ...]
    model: str
    input_type: str


def _captured_voyage_body(
    request: urllib.request.Request,
) -> CapturedVoyageRequestBody:
    data = request.data
    assert isinstance(data, bytes)
    return CapturedVoyageRequestBody.model_validate_json(data)


def _voyage_failure_for_response_body(response_body: str) -> EmbeddingFailure:
    opener = FakeVoyageOpener(_voyage_response_body(response_body))
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=opener,
    )

    result = EmbeddingService(provider).embed_texts(
        ("first", "second"),
        input_type=EmbeddingInputType.DOCUMENT,
    )

    assert isinstance(result, EmbeddingFailure)
    return result


def _assert_safe_voyage_failure(result: EmbeddingFailure) -> None:
    assert result.code is EmbeddingFailureCode.PROVIDER_ERROR
    assert result.provider == "voyage"
    joined = f"{result.message}\n{result.provider}"
    for forbidden in SAFE_ERROR_FORBIDDEN_PARTS:
        assert forbidden not in joined


def _http_headers(*, authorization: str | None = None) -> Message:
    headers = Message()
    if authorization is not None:
        headers["Authorization"] = authorization
    return headers


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


def _set_auth_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth: AuthFile,
) -> None:
    auth_path = tmp_path / "auth.json"
    _ = save_auth_file(auth, auth_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_path))


def _clear_embedding_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOC2DIC_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv(VOYAGE_API_KEY_ENV, raising=False)


def test_mock_embedding_provider_is_deterministic_and_dimensioned() -> None:
    service = EmbeddingService(DeterministicMockEmbeddingProvider(dimension=6))

    first = service.embed_texts(("스태미나", "경직"))
    second = service.embed_texts(("스태미나", "경직"))
    explicit_document = service.embed_texts(
        ("스태미나", "경직"),
        input_type=EmbeddingInputType.DOCUMENT,
    )

    assert isinstance(first, EmbeddingSuccess)
    assert isinstance(second, EmbeddingSuccess)
    assert isinstance(explicit_document, EmbeddingSuccess)
    assert first.dimension == 6
    assert first.embeddings == second.embeddings
    assert first.embeddings == explicit_document.embeddings
    assert len(first.embeddings[0].values) == 6
    assert first.embeddings[0].values != first.embeddings[1].values


def test_embedding_service_forwards_document_and_query_input_types() -> None:
    provider = RecordingProvider()
    service = EmbeddingService(provider)

    document_result = service.embed_texts(
        ("문서 텍스트",),
        input_type=EmbeddingInputType.DOCUMENT,
    )
    query_result = service.embed_texts(
        ("검색 질의",),
        input_type=EmbeddingInputType.QUERY,
    )

    assert isinstance(document_result, EmbeddingSuccess)
    assert isinstance(query_result, EmbeddingSuccess)
    assert provider.input_types == [
        EmbeddingInputType.DOCUMENT,
        EmbeddingInputType.QUERY,
    ]


def test_embedding_service_rejects_unexpected_provider_dimension() -> None:
    result = EmbeddingService(WrongDimensionProvider()).embed_texts(
        ("스태미나",),
        input_type=EmbeddingInputType.QUERY,
    )

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.INVALID_DIMENSION
    assert result.message == "provider returned vector with unexpected dimension"


def test_embedding_service_returns_safe_disabled_failure() -> None:
    result = EmbeddingService(DirectDisabledProvider()).embed_texts(
        ("스태미나",),
        input_type=EmbeddingInputType.QUERY,
    )

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.provider == "direct_disabled"


def test_embedding_service_empty_input_returns_success_without_provider_call() -> None:
    provider = RecordingProvider()

    result = EmbeddingService(provider).embed_texts(())

    assert isinstance(result, EmbeddingSuccess)
    assert result.embeddings == ()
    assert result.dimension == provider.dimension
    assert provider.input_types == []


def test_voyage_provider_posts_document_request_and_orders_indexed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def block_live_urlopen(
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> FakeVoyageResponse:
        _ = request
        _ = timeout
        message = "test must use fake opener, not urllib.request.urlopen"
        raise AssertionError(message)

    monkeypatch.setattr(urllib.request, "urlopen", block_live_urlopen)
    opener = FakeVoyageOpener(
        _voyage_response_body(
            """
            {
              "data": [
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2, 0.3]}
              ],
              "model": "voyage-4-large",
              "usage": {"total_tokens": 12}
            }
            """,
        ),
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_API_KEY),
        opener=opener,
    )

    result = EmbeddingService(provider).embed_texts(
        ("first document", "second document"),
        input_type=EmbeddingInputType.DOCUMENT,
    )

    assert isinstance(result, EmbeddingSuccess)
    assert result.model == "voyage-4-large"
    assert result.dimension == 3
    assert result.total_tokens == 12
    assert [embedding.text for embedding in result.embeddings] == [
        "first document",
        "second document",
    ]
    assert result.embeddings[0].values == (0.1, 0.2, 0.3)
    assert result.embeddings[1].values == (0.4, 0.5, 0.6)
    assert len(opener.requests) == 1
    assert opener.timeouts == [30.0]
    request = opener.requests[0]
    assert request.full_url == "https://api.voyageai.com/v1/embeddings"
    assert request.get_method() == "POST"
    headers = dict(request.header_items())
    assert headers["Content-type"] == "application/json"
    assert headers["Authorization"] == f"Bearer {FAKE_VOYAGE_API_KEY}"
    request_body = _captured_voyage_body(request)
    assert request_body.input == ("first document", "second document")
    assert request_body.model == "voyage-4-large"
    assert request_body.input_type == "document"


def test_voyage_provider_posts_query_request_with_explicit_model() -> None:
    opener = FakeVoyageOpener(
        _voyage_response_body(
            """
            {
              "data": [{"embedding": [0.7, 0.8]}],
              "model": "voyage-custom-model",
              "usage": {"total_tokens": 4}
            }
            """,
        ),
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(
            api_key=FAKE_VOYAGE_API_KEY,
            model="voyage-custom-model",
        ),
        opener=opener,
    )

    result = EmbeddingService(provider).embed_texts(
        ("search query",),
        input_type=EmbeddingInputType.QUERY,
    )

    assert isinstance(result, EmbeddingSuccess)
    assert result.dimension == 2
    assert result.total_tokens == 4
    assert result.embeddings[0].values == (0.7, 0.8)
    request = opener.requests[0]
    request_body = _captured_voyage_body(request)
    assert request_body.input == ("search query",)
    assert request_body.model == "voyage-custom-model"
    assert request_body.input_type == "query"


def test_voyage_provider_rejects_success_response_count_mismatch() -> None:
    opener = FakeVoyageOpener(
        _voyage_response_body(
            """
            {
              "data": [{"index": 0, "embedding": [0.1, 0.2]}],
              "model": "voyage-4-large"
            }
            """,
        ),
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_API_KEY),
        opener=opener,
    )

    result = EmbeddingService(provider).embed_texts(
        ("first", "second"),
        input_type=EmbeddingInputType.DOCUMENT,
    )

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_ERROR
    assert result.provider == "voyage"
    assert (
        result.message
        == "Voyage embeddings response count did not match input count"
    )
    assert FAKE_VOYAGE_API_KEY not in result.message


def test_voyage_provider_returns_disabled_failure_when_key_missing() -> None:
    provider = VoyageEmbeddingProvider.from_config(
        EmbeddingProviderConfig(provider_name="voyage", model="", api_key=None),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.message == "Voyage API key is not configured"


def test_voyage_provider_reports_401_without_leaking_secret() -> None:
    body = BytesIO(
        b'{"error":"bad key sk-test-doc2dic-voyage-secret Authorization Bearer"}',
    )
    error = HTTPError(
        url="https://api.voyageai.com/v1/embeddings",
        code=HTTPStatus.UNAUTHORIZED,
        msg="Unauthorized",
        hdrs=_http_headers(authorization=f"Bearer {FAKE_VOYAGE_SECRET}"),
        fp=body,
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=ErrorVoyageOpener(error),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    _assert_safe_voyage_failure(result)
    assert "status=401" in result.message


def test_voyage_provider_reports_429_without_leaking_secret() -> None:
    body = BytesIO(b'{"detail":"rate limit sk-test-doc2dic-voyage-secret"}')
    error = HTTPError(
        url="https://api.voyageai.com/v1/embeddings",
        code=HTTPStatus.TOO_MANY_REQUESTS,
        msg="Too Many Requests",
        hdrs=_http_headers(),
        fp=body,
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=ErrorVoyageOpener(error),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    _assert_safe_voyage_failure(result)
    assert "status=429" in result.message


def test_voyage_provider_reports_500_without_leaking_secret() -> None:
    body = BytesIO(b'{"trace":"full-request-body sk-test-doc2dic-voyage-secret"}')
    error = HTTPError(
        url="https://api.voyageai.com/v1/embeddings",
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        msg="Internal Server Error",
        hdrs=_http_headers(),
        fp=body,
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=ErrorVoyageOpener(error),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    _assert_safe_voyage_failure(result)
    assert "status=500" in result.message


def test_voyage_provider_reports_timeout_without_leaking_secret() -> None:
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=ErrorVoyageOpener(TimeoutError("sk-test-doc2dic-voyage-secret")),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    _assert_safe_voyage_failure(result)
    assert "timeout" in result.message.lower()


def test_voyage_provider_reports_url_error_without_leaking_secret() -> None:
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=ErrorVoyageOpener(URLError("sk-test-doc2dic-voyage-secret")),
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingFailure)
    _assert_safe_voyage_failure(result)
    assert "url_error" in result.message


def test_voyage_provider_rejects_invalid_json_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        '{"data": [sk-test-doc2dic-voyage-secret',
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_missing_data_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        '{"model":"voyage-4-large","error":"sk-test-doc2dic-voyage-secret"}',
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_non_list_data_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        """
        {
          "data": {"embedding": [0.1, 0.2]},
          "model": "voyage-4-large"
        }
        """,
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_missing_embedding_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        """
        {
          "data": [
            {"index": 0},
            {"index": 1, "embedding": [0.1, 0.2]}
          ],
          "model": "voyage-4-large"
        }
        """,
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_non_list_embedding_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        """
        {
          "data": [
            {"index": 0, "embedding": "sk-test-doc2dic-voyage-secret"},
            {"index": 1, "embedding": [0.1, 0.2]}
          ],
          "model": "voyage-4-large"
        }
        """,
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_non_numeric_embedding_without_leaking_secret() -> None:
    result = _voyage_failure_for_response_body(
        """
        {
          "data": [
            {"index": 0, "embedding": ["sk-test-doc2dic-voyage-secret", 0.2]},
            {"index": 1, "embedding": [0.1, 0.2]}
          ],
          "model": "voyage-4-large"
        }
        """,
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response is malformed"


def test_voyage_provider_rejects_inconsistent_dimensions_safely() -> None:
    result = _voyage_failure_for_response_body(
        """
        {
          "data": [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.1, 0.2, 0.3]}
          ],
          "model": "voyage-4-large"
        }
        """,
    )

    _assert_safe_voyage_failure(result)
    assert result.message == "Voyage embeddings response dimensions were inconsistent"


def test_voyage_provider_ignores_malformed_usage_without_leaking_secret() -> None:
    opener = FakeVoyageOpener(
        _voyage_response_body(
            """
            {
              "data": [{"embedding": [0.7, 0.8]}],
              "model": "voyage-4-large",
              "usage": {"total_tokens": "sk-test-doc2dic-voyage-secret"}
            }
            """,
        ),
    )
    provider = VoyageEmbeddingProvider(
        config=VoyageEmbeddingProviderConfig(api_key=FAKE_VOYAGE_SECRET),
        opener=opener,
    )

    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(result, EmbeddingSuccess)
    assert result.total_tokens is None
    assert result.embeddings[0].values == (0.7, 0.8)


def test_real_embedding_provider_selection_is_disabled_without_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "openai")
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    provider = embedding_provider_from_environment()

    result: EmbeddingResult = EmbeddingService(provider).embed_texts(("스태미나",))

    assert isinstance(provider, DisabledEmbeddingProvider)
    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert "DOC2DIC_EMBEDDING_API_KEY" in result.message


def test_real_embedding_provider_selection_stays_offline_with_fake_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_API_KEY", "fake-non-empty-ci-key")
    provider = embedding_provider_from_environment()

    result: EmbeddingResult = EmbeddingService(provider).embed_texts(("스태미나",))

    assert isinstance(provider, DisabledEmbeddingProvider)
    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.message == "real embedding network adapter is not implemented in T16"


def test_project_embedding_resolver_uses_project_provider_model_and_auth_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    settings = SettingsRepository(connection)
    settings.set_value("embedding.provider", "voyage")
    settings.set_value("embedding.model", "project-voyage-model")
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-voyage-model",
            api_key=FAKE_VOYAGE_SECRET,
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.model == "project-voyage-model"
    assert config.api_key == FAKE_VOYAGE_SECRET
    rows: list[sqlite3.Row] = connection.execute(
        "select key, value from settings",
    ).fetchall()
    assert all(FAKE_VOYAGE_SECRET not in f"{row['key']}={row['value']}" for row in rows)


def test_project_embedding_resolver_provider_env_overrides_project_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    settings = SettingsRepository(connection)
    settings.set_value("embedding.provider", "mock")
    settings.set_value("embedding.model", "project-model")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "voyage")
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-model",
            api_key=FAKE_VOYAGE_API_KEY,
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.model == "project-model"
    assert config.api_key == FAKE_VOYAGE_API_KEY


def test_project_embedding_resolver_falls_back_to_auth_provider_model_and_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-voyage-model",
            api_key=FAKE_VOYAGE_API_KEY,
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.model == "auth-voyage-model"
    assert config.api_key == FAKE_VOYAGE_API_KEY


def test_project_embedding_resolver_voyage_api_key_overrides_generic_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    SettingsRepository(connection).set_value("embedding.provider", "voyage")
    monkeypatch.setenv(VOYAGE_API_KEY_ENV, "voyage-env-key")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_API_KEY", "generic-env-key")
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-model",
            api_key="auth-file-key",
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.api_key == "voyage-env-key"


def test_project_embedding_resolver_generic_api_key_overrides_auth_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    SettingsRepository(connection).set_value("embedding.provider", "voyage")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_API_KEY", "generic-env-key")
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="voyage",
            model="auth-model",
            api_key="auth-file-key",
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.api_key == "generic-env-key"


def test_project_embedding_resolver_uses_voyage_default_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    SettingsRepository(connection).set_value("embedding.provider", "voyage")
    _set_auth_file(
        tmp_path,
        monkeypatch,
        AuthFile().with_embedding(
            provider="mock",
            model="mock-embedding-v1",
            api_key=None,
        ),
    )

    config = embedding_provider_config_from_project(connection)

    assert config.provider_name == "voyage"
    assert config.model == "voyage-4-large"


def test_project_embedding_provider_returns_disabled_when_voyage_key_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    SettingsRepository(connection).set_value("embedding.provider", "voyage")
    _set_auth_file(tmp_path, monkeypatch, AuthFile())

    provider = embedding_provider_from_project(connection)
    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(provider, DisabledEmbeddingProvider)
    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.message == "Voyage API key is not configured"


def test_project_embedding_provider_returns_disabled_for_unknown_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_environment(monkeypatch)
    connection = _settings_connection()
    SettingsRepository(connection).set_value("embedding.provider", "unsupported")
    _set_auth_file(tmp_path, monkeypatch, AuthFile())

    provider = embedding_provider_from_project(connection)
    result = EmbeddingService(provider).embed_texts(("document",))

    assert isinstance(provider, DisabledEmbeddingProvider)
    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.message == "unsupported embedding provider: unsupported"


def test_embedding_provider_selection_reads_auth_file_without_leaking_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth = AuthFile().with_embedding(
        provider="voyage",
        model="voyage-3-large",
        api_key="fake-voyage-ci-key",
    )
    _ = save_auth_file(auth, auth_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_path))
    monkeypatch.delenv("DOC2DIC_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)

    provider = embedding_provider_from_environment()

    assert isinstance(provider, VoyageEmbeddingProvider)
    assert provider.model == "voyage-3-large"
    assert "fake-voyage-ci-key" not in repr(provider)
