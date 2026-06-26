"""Embedding provider contracts with deterministic offline mock vectors."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

MOCK_EMBEDDING_PROVIDER_NAME: Final = "deterministic_mock_embedding"
DISABLED_EMBEDDING_PROVIDER_NAME: Final = "disabled_embedding_provider"
DEFAULT_EMBEDDING_DIMENSION: Final = 12
EMBEDDING_API_KEY_ENV: Final = "DOC2DIC_EMBEDDING_API_KEY"


class EmbeddingFailureCode(StrEnum):
    """Safe embedding failure categories."""

    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_ERROR = "provider_error"
    INVALID_DIMENSION = "invalid_dimension"


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

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        """Return embeddings for each text in order."""
        ...


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


class EmbeddingProviderDisabledError(EmbeddingProviderError):
    """Raised by disabled real embedding adapters."""


class EmbeddingService:
    """Generate embeddings through a provider without network assumptions."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        """Store the provider dependency."""
        self._provider: EmbeddingProvider
        self._provider = provider

    def embed_texts(self, texts: tuple[str, ...]) -> EmbeddingResult:
        """Return deterministic success or safe failure for input texts."""
        if self._provider.dimension <= 0:
            return EmbeddingFailure(
                code=EmbeddingFailureCode.INVALID_DIMENSION,
                message="embedding dimension must be positive",
                provider=self._provider.provider_name,
            )
        try:
            embeddings = self._provider.embed_texts(texts)
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
            provider=self._provider.provider_name,
            model=self._provider.model,
            dimension=self._provider.dimension,
            embeddings=embeddings,
        )


@dataclass(frozen=True, slots=True)
class DeterministicMockEmbeddingProvider:
    """Hash-based embedding provider for repeatable tests."""

    dimension: int = DEFAULT_EMBEDDING_DIMENSION
    model: str = "mock-embedding-v1"
    provider_name: str = MOCK_EMBEDDING_PROVIDER_NAME

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        """Return stable vectors with no external calls."""
        return tuple(
            EmbeddingVector(
                text=text,
                model=self.model,
                values=_deterministic_vector(text, self.model, self.dimension),
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

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        """Reject embedding without making any network call."""
        _ = texts
        raise EmbeddingProviderDisabledError(self.reason)


class OpenAIEmbeddingProvider(DisabledEmbeddingProvider):
    """Skeletal real embedding adapter disabled in T16."""

    provider_name: str = "openai_embedding_disabled"
    model: str = "openai-disabled"
    @classmethod
    def from_environment(cls) -> OpenAIEmbeddingProvider | DisabledEmbeddingProvider:
        """Return a disabled provider without requiring SDKs or keys."""
        api_key = os.environ.get(EMBEDDING_API_KEY_ENV)
        if api_key is None or api_key == "":
            return DisabledEmbeddingProvider(
                reason=f"{EMBEDDING_API_KEY_ENV} is not configured",
            )
        return cls(reason="real embedding network adapter is not implemented in T16")


def embedding_provider_from_environment() -> EmbeddingProvider:
    """Return configured embedding provider without network access."""
    provider_name = os.environ.get("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    match provider_name:
        case "mock" | "deterministic_mock":
            return DeterministicMockEmbeddingProvider()
        case "openai":
            return OpenAIEmbeddingProvider.from_environment()
        case "disabled":
            return DisabledEmbeddingProvider()
        case unknown:
            return DisabledEmbeddingProvider(
                reason=f"unsupported embedding provider: {unknown}",
            )


def _deterministic_vector(text: str, model: str, dimension: int) -> tuple[float, ...]:
    seed = f"{model}\n{text}".encode()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for byte in digest:
            values.append(round((byte / 127.5) - 1.0, 6))
            if len(values) == dimension:
                break
        counter += 1
    return tuple(values)


__all__ = [
    "DeterministicMockEmbeddingProvider",
    "DisabledEmbeddingProvider",
    "EmbeddingFailure",
    "EmbeddingFailureCode",
    "EmbeddingProvider",
    "EmbeddingProviderDisabledError",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "EmbeddingService",
    "EmbeddingSuccess",
    "EmbeddingVector",
    "OpenAIEmbeddingProvider",
    "embedding_provider_from_environment",
]
