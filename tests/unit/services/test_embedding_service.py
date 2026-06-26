from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from doc2dic.services.embedding_service import (
    DeterministicMockEmbeddingProvider,
    DisabledEmbeddingProvider,
    EmbeddingFailure,
    EmbeddingFailureCode,
    EmbeddingProviderDisabledError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingSuccess,
    EmbeddingVector,
    embedding_provider_from_environment,
)

if TYPE_CHECKING:
    import pytest


@dataclass(frozen=True, slots=True)
class WrongDimensionProvider:
    provider_name: str = "wrong_dimension"
    model: str = "wrong-model"
    dimension: int = 3

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        return tuple(
            EmbeddingVector(text=text, model=self.model, values=(0.1, 0.2))
            for text in texts
        )


@dataclass(frozen=True, slots=True)
class DirectDisabledProvider:
    provider_name: str = "direct_disabled"
    model: str = "disabled"
    dimension: int = 3

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        _ = texts
        message = "disabled for test"
        raise EmbeddingProviderDisabledError(message)


def test_mock_embedding_provider_is_deterministic_and_dimensioned() -> None:
    service = EmbeddingService(DeterministicMockEmbeddingProvider(dimension=6))

    first = service.embed_texts(("스태미나", "경직"))
    second = service.embed_texts(("스태미나", "경직"))

    assert isinstance(first, EmbeddingSuccess)
    assert isinstance(second, EmbeddingSuccess)
    assert first.dimension == 6
    assert first.embeddings == second.embeddings
    assert len(first.embeddings[0].values) == 6
    assert first.embeddings[0].values != first.embeddings[1].values


def test_embedding_service_rejects_unexpected_provider_dimension() -> None:
    result = EmbeddingService(WrongDimensionProvider()).embed_texts(("스태미나",))

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.INVALID_DIMENSION
    assert result.message == "provider returned vector with unexpected dimension"


def test_embedding_service_returns_safe_disabled_failure() -> None:
    result = EmbeddingService(DirectDisabledProvider()).embed_texts(("스태미나",))

    assert isinstance(result, EmbeddingFailure)
    assert result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    assert result.provider == "direct_disabled"


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
