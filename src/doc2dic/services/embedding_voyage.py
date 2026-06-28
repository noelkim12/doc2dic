"""Voyage embeddings REST client using Python stdlib HTTP."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    Protocol,
    Self,
    TypedDict,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, ValidationError

from doc2dic.services.embedding_service import (
    DEFAULT_EMBEDDING_DIMENSION,
    DisabledEmbeddingProvider,
    EmbeddingInputType,
    EmbeddingProviderConfig,
    EmbeddingProviderError,
    EmbeddingVector,
)
from doc2dic.services.embedding_voyage_usage import parse_total_tokens

if TYPE_CHECKING:
    from types import TracebackType

VOYAGE_EMBEDDINGS_URL: Final = "https://api.voyageai.com/v1/embeddings"
DEFAULT_VOYAGE_MODEL: Final = "voyage-4-large"
DEFAULT_VOYAGE_TIMEOUT_SECONDS: Final = 30.0


class VoyageRestError(RuntimeError):
    """Raised when a Voyage success response cannot be accepted."""


@runtime_checkable
class VoyageResponse(Protocol):
    """Readable context-managed Voyage HTTP response."""

    def read(self) -> bytes:
        """Return response bytes."""
        ...

    def __enter__(self) -> Self:
        """Enter response context."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit response context."""
        ...


class VoyageOpener(Protocol):
    """Minimal urllib opener seam for fake-network tests."""

    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> VoyageResponse:
        """Open a request and return a readable response."""
        ...


class VoyageEmbeddingRequestBody(TypedDict):
    """Voyage embeddings request body."""

    input: tuple[str, ...]
    model: str
    input_type: str


class VoyageEmbeddingItem(BaseModel):
    """One item from Voyage's direct REST `data` array."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    embedding: tuple[float, ...]
    index: int | None = None


class VoyageEmbeddingResponseBody(BaseModel):
    """Voyage direct REST embedding response."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    data: tuple[VoyageEmbeddingItem, ...]
    model: str


@dataclass(frozen=True, slots=True)
class VoyageRestConfig:
    """Voyage REST settings without exposing the credential in repr."""

    api_key: str = field(repr=False)
    model: str = DEFAULT_VOYAGE_MODEL
    timeout_seconds: float = DEFAULT_VOYAGE_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class VoyageEmbeddingProviderConfig:
    """Voyage provider settings without exposing credentials in repr."""

    api_key: str = field(repr=False)
    model: str = DEFAULT_VOYAGE_MODEL
    timeout_seconds: float = DEFAULT_VOYAGE_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class VoyageEmbeddingBatch:
    """Parsed Voyage response vectors in input order."""

    model: str
    dimension: int
    values: tuple[tuple[float, ...], ...]
    total_tokens: int | None = None


urllib_voyage_opener: VoyageOpener = urllib.request.urlopen


@dataclass(frozen=True, slots=True)
class VoyageEmbeddingRestClient:
    """Low-level Voyage embeddings REST client."""

    config: VoyageRestConfig
    opener: VoyageOpener = urllib_voyage_opener

    def embed(self, texts: tuple[str, ...], input_type: str) -> VoyageEmbeddingBatch:
        """POST to Voyage and parse the direct REST success body."""
        body = VoyageEmbeddingRequestBody(
            input=texts,
            model=self.config.model,
            input_type=input_type,
        )
        request = urllib.request.Request(  # noqa: S310
            VOYAGE_EMBEDDINGS_URL,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.config.timeout_seconds) as response:
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            raise VoyageRestError(_http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            message = "Voyage embeddings request failed url_error"
            raise VoyageRestError(message) from exc
        except TimeoutError as exc:
            message = "Voyage embeddings request failed timeout"
            raise VoyageRestError(message) from exc
        return _parse_voyage_success(response_body, len(texts))


class VoyageEmbeddingProvider:
    """Voyage text embedding provider using the stdlib REST client."""

    provider_name: str = "voyage"

    def __init__(
        self,
        config: VoyageEmbeddingProviderConfig,
        opener: VoyageOpener | None = None,
    ) -> None:
        """Store the low-level Voyage REST client."""
        self._model: str = config.model
        self._dimension: int = DEFAULT_EMBEDDING_DIMENSION
        self._total_tokens: int | None = None
        rest_config = VoyageRestConfig(
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )
        self._client: VoyageEmbeddingRestClient = (
            VoyageEmbeddingRestClient(rest_config)
            if opener is None
            else VoyageEmbeddingRestClient(rest_config, opener)
        )

    @property
    def model(self) -> str:
        """Most recent Voyage response model, or configured request model."""
        return self._model

    @property
    def dimension(self) -> int:
        """Most recent inferred vector dimension."""
        return self._dimension

    @property
    def total_tokens(self) -> int | None:
        """Most recent Voyage usage total token count, when reported."""
        return self._total_tokens

    @classmethod
    def from_config(
        cls,
        config: EmbeddingProviderConfig,
    ) -> VoyageEmbeddingProvider | DisabledEmbeddingProvider:
        """Return a live Voyage provider when credentials are configured."""
        if config.api_key is None or config.api_key == "":
            return DisabledEmbeddingProvider(reason="Voyage API key is not configured")
        model = config.model or DEFAULT_VOYAGE_MODEL
        return cls(VoyageEmbeddingProviderConfig(api_key=config.api_key, model=model))

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        """Request Voyage embeddings and return vectors in input order."""
        try:
            batch = self._client.embed(texts, input_type.value)
        except VoyageRestError as exc:
            raise EmbeddingProviderError(str(exc)) from exc
        self._model = batch.model
        self._dimension = batch.dimension
        self._total_tokens = batch.total_tokens
        return tuple(
            EmbeddingVector(text=text, model=batch.model, values=values)
            for text, values in zip(texts, batch.values, strict=True)
        )


def _parse_voyage_success(
    response_body: bytes,
    input_count: int,
) -> VoyageEmbeddingBatch:
    try:
        parsed = VoyageEmbeddingResponseBody.model_validate_json(response_body)
    except ValidationError as exc:
        message = "Voyage embeddings response is malformed"
        raise VoyageRestError(message) from exc
    if len(parsed.data) != input_count:
        message = "Voyage embeddings response count did not match input count"
        raise VoyageRestError(message)
    ordered_items = _order_voyage_items(parsed.data, input_count)
    values = tuple(item.embedding for item in ordered_items)
    dimension = _infer_dimension(values)
    return VoyageEmbeddingBatch(
        model=parsed.model,
        dimension=dimension,
        values=values,
        total_tokens=parse_total_tokens(response_body),
    )


def _http_error_message(error: urllib.error.HTTPError) -> str:
    body_size = len(error.read())
    return (
        "Voyage embeddings request failed "
        f"status={error.code} response_bytes={body_size}"
    )


def _order_voyage_items(
    items: tuple[VoyageEmbeddingItem, ...],
    input_count: int,
) -> tuple[VoyageEmbeddingItem, ...]:
    indexed = tuple(item for item in items if item.index is not None)
    if len(indexed) == 0:
        return items
    if len(indexed) != len(items):
        message = "Voyage embeddings response mixed indexed and unindexed items"
        raise VoyageRestError(message)
    ordered = tuple(sorted(indexed, key=lambda item: item.index or 0))
    expected_indices = tuple(range(input_count))
    actual_indices = tuple(item.index for item in ordered)
    if actual_indices != expected_indices:
        message = "Voyage embeddings response indices did not match input order"
        raise VoyageRestError(message)
    return ordered


def _infer_dimension(values: tuple[tuple[float, ...], ...]) -> int:
    if len(values) == 0:
        return 0
    dimension = len(values[0])
    if dimension == 0:
        message = "Voyage embeddings response contained empty vector"
        raise VoyageRestError(message)
    for vector in values:
        if len(vector) != dimension:
            message = "Voyage embeddings response dimensions were inconsistent"
            raise VoyageRestError(message)
    return dimension
