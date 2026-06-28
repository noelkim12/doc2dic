"""Embedding provider contracts with deterministic offline mock vectors."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol, runtime_checkable

from doc2dic.services.auth_store import AuthFileError, load_auth_file
from doc2dic.services.embedding_mock import deterministic_vector

MOCK_EMBEDDING_PROVIDER_NAME: Final = "deterministic_mock_embedding"
DISABLED_EMBEDDING_PROVIDER_NAME: Final = "disabled_embedding_provider"
DEFAULT_EMBEDDING_DIMENSION: Final = 12
EMBEDDING_API_KEY_ENV: Final = "DOC2DIC_EMBEDDING_API_KEY"
EMBEDDING_PROVIDER_ENV: Final = "DOC2DIC_EMBEDDING_PROVIDER"


class EmbeddingFailureCode(StrEnum):
    """Safe embedding failure categories."""

    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_ERROR = "provider_error"
    INVALID_DIMENSION = "invalid_dimension"


class EmbeddingInputType(StrEnum):
    """Provider embedding mode for the input text role."""

    DOCUMENT = "document"
    QUERY = "query"


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """Embedding vector for one input text."""

    text: str
    model: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingSuccess:
    """Accepted embedding result."""

    provider: str
    model: str
    dimension: int
    embeddings: tuple[EmbeddingVector, ...]
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingFailure:
    """Safe embedding failure result."""

    code: EmbeddingFailureCode
    message: str
    provider: str


type EmbeddingResult = EmbeddingSuccess | EmbeddingFailure


class EmbeddingProvider(Protocol):
    """Provider seam for embedding generation."""

    @property
    def provider_name(self) -> str:
        """Stable provider identifier."""
        ...

    @property
    def model(self) -> str:
        """Embedding model identifier."""
        ...

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType, /,
    ) -> tuple[EmbeddingVector, ...]:
        """Return embeddings for each text in order."""
        ...


@runtime_checkable
class _EmbeddingUsageReporter(Protocol):
    @property
    def total_tokens(self) -> int | None:
        ...


@runtime_checkable
class _VoyageProviderFactory(Protocol):
    @classmethod
    def from_config(cls, config: EmbeddingProviderConfig) -> EmbeddingProvider:
        ...


@runtime_checkable
class _VoyagePublicModule(Protocol):
    VoyageEmbeddingProvider: type[_VoyageProviderFactory]
    VoyageEmbeddingProviderConfig: type[_VoyageProviderFactory]


@dataclass(frozen=True, slots=True)
class EmbeddingProviderConfig:
    """Resolved embedding provider metadata without exposing secrets."""

    provider_name: str
    model: str
    api_key: str | None = field(repr=False)


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


class EmbeddingProviderDisabledError(EmbeddingProviderError):
    """Raised by disabled real embedding adapters."""


class EmbeddingService:
    """Generate embeddings through a provider without network assumptions."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        """Store the provider dependency."""
        self._provider: EmbeddingProvider = provider

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> EmbeddingResult:
        """Return deterministic success or safe failure for input texts."""
        if self._provider.dimension <= 0:
            return EmbeddingFailure(
                code=EmbeddingFailureCode.INVALID_DIMENSION,
                message="embedding dimension must be positive",
                provider=self._provider.provider_name,
            )
        if not texts:
            return EmbeddingSuccess(
                self._provider.provider_name,
                self._provider.model,
                self._provider.dimension,
                embeddings=(), total_tokens=_provider_total_tokens(self._provider),
            )
        try:
            embeddings = self._provider.embed_texts(texts, input_type)
        except EmbeddingProviderDisabledError as exc:
            return EmbeddingFailure(
                code=EmbeddingFailureCode.PROVIDER_DISABLED,
                message=str(exc),
                provider=self._provider.provider_name,
            )
        except EmbeddingProviderError as exc:
            return EmbeddingFailure(
                code=EmbeddingFailureCode.PROVIDER_ERROR,
                message=str(exc),
                provider=self._provider.provider_name,
            )
        for embedding in embeddings:
            if len(embedding.values) != self._provider.dimension:
                return EmbeddingFailure(
                    code=EmbeddingFailureCode.INVALID_DIMENSION,
                    message="provider returned vector with unexpected dimension",
                    provider=self._provider.provider_name,
                )
        return EmbeddingSuccess(
            self._provider.provider_name,
            self._provider.model,
            self._provider.dimension,
            embeddings=embeddings, total_tokens=_provider_total_tokens(self._provider),
        )


@dataclass(frozen=True, slots=True)
class DeterministicMockEmbeddingProvider:
    """Hash-based embedding provider for repeatable tests."""

    dimension: int = DEFAULT_EMBEDDING_DIMENSION
    model: str = "mock-embedding-v1"
    provider_name: str = MOCK_EMBEDDING_PROVIDER_NAME

    def embed_texts(
        self,
        texts: tuple[str, ...],
        _input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        """Return stable vectors with no external calls."""
        return tuple(
            EmbeddingVector(
                text=text,
                model=self.model,
                values=deterministic_vector(text, self.model, self.dimension),
            )
            for text in texts
        )


@dataclass(frozen=True, slots=True)
class DisabledEmbeddingProvider:
    """Offline-safe stand-in for future real embedding adapters."""

    reason: str = "embedding provider is disabled; set a supported adapter later."
    dimension: int = DEFAULT_EMBEDDING_DIMENSION
    model: str = "disabled-embedding"
    provider_name: str = DISABLED_EMBEDDING_PROVIDER_NAME

    def embed_texts(
        self,
        texts: tuple[str, ...],
        _input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        """Reject embedding without making any network call."""
        _ = texts
        raise EmbeddingProviderDisabledError(self.reason)


class OpenAIEmbeddingProvider(DisabledEmbeddingProvider):
    """Skeletal real embedding adapter disabled in T16."""

    provider_name: str = "openai_embedding_disabled"
    model: str = "openai-disabled"

    @classmethod
    def from_api_key(
        cls,
        api_key: str | None,
    ) -> OpenAIEmbeddingProvider | DisabledEmbeddingProvider:
        """Return a disabled provider based on credential availability."""
        if api_key is None or api_key == "":
            return DisabledEmbeddingProvider(
                reason=f"{EMBEDDING_API_KEY_ENV} is not configured",
            )
        return cls(reason="real embedding network adapter is not implemented in T16")


def embedding_provider_from_environment() -> EmbeddingProvider:
    """Return configured embedding provider without network access."""
    try:
        config = _embedding_provider_config()
    except AuthFileError as exc:
        return DisabledEmbeddingProvider(reason=str(exc))
    match config.provider_name:
        case "mock" | "deterministic_mock":
            return DeterministicMockEmbeddingProvider()
        case "openai":
            return OpenAIEmbeddingProvider.from_api_key(config.api_key)
        case "voyage":
            return _voyage_provider_from_config(config)
        case "disabled":
            return DisabledEmbeddingProvider()
        case unknown:
            reason = f"unsupported embedding provider: {unknown}"
            return DisabledEmbeddingProvider(reason=reason)


def _embedding_provider_config() -> EmbeddingProviderConfig:
    env_provider = _non_empty_env(EMBEDDING_PROVIDER_ENV)
    if env_provider is not None:
        return EmbeddingProviderConfig(
            provider_name=env_provider,
            model="",
            api_key=_non_empty_env(EMBEDDING_API_KEY_ENV),
        )
    auth = load_auth_file()
    provider_name = auth.embedding.provider
    env_key = _non_empty_env(EMBEDDING_API_KEY_ENV)
    return EmbeddingProviderConfig(
        provider_name=provider_name,
        model=auth.embedding.model,
        api_key=env_key or auth.embedding.api_key_for(provider_name),
    )


def _non_empty_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value


def _voyage_provider_from_config(config: EmbeddingProviderConfig) -> EmbeddingProvider:
    return _voyage_module().VoyageEmbeddingProvider.from_config(config)


def __getattr__(
    name: str,
) -> type[_VoyageProviderFactory]:
    match name:
        case "VoyageEmbeddingProvider":
            return _voyage_module().VoyageEmbeddingProvider
        case "VoyageEmbeddingProviderConfig":
            return _voyage_module().VoyageEmbeddingProviderConfig
        case _:
            raise AttributeError(name)


def _voyage_module() -> _VoyagePublicModule:
    module = importlib.import_module("doc2dic.services.embedding_voyage")
    if isinstance(module, _VoyagePublicModule):
        return module
    raise AttributeError(module.__name__)


def _provider_total_tokens(provider: EmbeddingProvider) -> int | None:
    if isinstance(provider, _EmbeddingUsageReporter):
        return provider.total_tokens
    return None
