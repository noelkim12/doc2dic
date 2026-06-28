from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, Self, TypedDict

from pydantic import BaseModel, ConfigDict, ValidationError

from doc2dic.services.auth_store import AuthFileError, load_auth_file
from doc2dic.services.embedding_config import VOYAGE_API_KEY_ENV
from doc2dic.services.embedding_voyage import (
    DEFAULT_VOYAGE_MODEL,
    VOYAGE_EMBEDDINGS_URL,
)

if TYPE_CHECKING:
    from types import TracebackType

LIVE_VOYAGE_OPT_IN_ENV: Final = "DOC2DIC_RUN_LIVE_VOYAGE_TESTS"
FAKE_LIVE_VOYAGE_SECRET: Final = "sk-test-doc2dic-voyage-live-secret"  # noqa: S105
_LIVE_VOYAGE_TEXT: Final = "doc2dic live voyage smoke"
_LIVE_VOYAGE_TIMEOUT_SECONDS: Final = 30.0
_EMBEDDING_API_KEY_ENV: Final = "DOC2DIC_EMBEDDING_API_KEY"


class LiveVoyageSmokeError(RuntimeError):
    """Raised when the opt-in Voyage smoke call fails safely."""


@dataclass(frozen=True, slots=True)
class LiveVoyageSkip:
    reason: str


@dataclass(frozen=True, slots=True)
class LiveVoyageReady:
    api_key: str = field(repr=False)


type LiveVoyageGate = LiveVoyageReady | LiveVoyageSkip


@dataclass(frozen=True, slots=True)
class LiveVoyageMetadata:
    status: int
    model: str
    embedding_count: int
    vector_dimension: int
    total_tokens: int


class VoyageSmokeResponse(Protocol):
    status: int

    def read(self) -> bytes:
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        ...


class VoyageSmokeOpener(Protocol):
    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> VoyageSmokeResponse:
        ...


class VoyageSmokeRequestBody(TypedDict):
    input: tuple[str, ...]
    model: str
    input_type: str


class _VoyageSmokeItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    embedding: tuple[float, ...]
    index: int | None = None


class _VoyageSmokeUsage(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    total_tokens: int


class _VoyageSmokeResponseBody(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    data: tuple[_VoyageSmokeItem, ...]
    model: str
    usage: _VoyageSmokeUsage


urllib_live_voyage_opener: VoyageSmokeOpener = urllib.request.urlopen


def live_voyage_gate() -> LiveVoyageGate:
    if os.environ.get(LIVE_VOYAGE_OPT_IN_ENV) != "1":
        return LiveVoyageSkip(reason="reason=opt_in_required")
    api_key = _voyage_api_key()
    if api_key is None:
        return LiveVoyageSkip(reason="reason=no_key")
    return LiveVoyageReady(api_key=api_key)


def run_live_voyage_smoke(
    *,
    api_key: str,
    opener: VoyageSmokeOpener = urllib_live_voyage_opener,
) -> LiveVoyageMetadata:
    request = _live_voyage_request(api_key)
    try:
        with opener(request, timeout=_LIVE_VOYAGE_TIMEOUT_SECONDS) as response:
            status = response.status
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        response_bytes = len(exc.read())
        message = f"reason=http_error status={exc.code} response_bytes={response_bytes}"
        raise LiveVoyageSmokeError(message) from exc
    except urllib.error.URLError as exc:
        message = "reason=url_error"
        raise LiveVoyageSmokeError(message) from exc
    except TimeoutError as exc:
        message = "reason=timeout"
        raise LiveVoyageSmokeError(message) from exc
    return _metadata_from_response(status=status, response_body=response_body)


def format_live_voyage_metadata(metadata: LiveVoyageMetadata) -> str:
    return "\n".join(
        (
            f"status={metadata.status}",
            f"model={metadata.model}",
            f"embedding_count={metadata.embedding_count}",
            f"vector_dimension={metadata.vector_dimension}",
            f"total_tokens={metadata.total_tokens}",
        ),
    )


def _voyage_api_key() -> str | None:
    env_key = _non_empty_env(VOYAGE_API_KEY_ENV) or _non_empty_env(
        _EMBEDDING_API_KEY_ENV,
    )
    if env_key is not None:
        return env_key
    try:
        return load_auth_file().embedding.api_key_for("voyage")
    except AuthFileError:
        return None


def _live_voyage_request(api_key: str) -> urllib.request.Request:
    body = VoyageSmokeRequestBody(
        input=(_LIVE_VOYAGE_TEXT,),
        model=DEFAULT_VOYAGE_MODEL,
        input_type="document",
    )
    return urllib.request.Request(  # noqa: S310
        VOYAGE_EMBEDDINGS_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _metadata_from_response(
    *,
    status: int,
    response_body: bytes,
) -> LiveVoyageMetadata:
    try:
        parsed = _VoyageSmokeResponseBody.model_validate_json(response_body)
    except ValidationError as exc:
        message = "reason=malformed_response"
        raise LiveVoyageSmokeError(message) from exc
    if len(parsed.data) != 1:
        message = "reason=count_mismatch"
        raise LiveVoyageSmokeError(message)
    vector_dimension = len(parsed.data[0].embedding)
    if vector_dimension <= 0:
        message = "reason=empty_vector"
        raise LiveVoyageSmokeError(message)
    return LiveVoyageMetadata(
        status=status,
        model=parsed.model,
        embedding_count=len(parsed.data),
        vector_dimension=vector_dimension,
        total_tokens=parsed.usage.total_tokens,
    )


def _non_empty_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value
