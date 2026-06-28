"""Voyage REST usage metadata parsing."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError


class VoyageUsageBody(BaseModel):
    """Voyage usage metadata when the REST response includes it."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    total_tokens: int | None = None


class VoyageUsageResponseBody(BaseModel):
    """Voyage response usage envelope parsed separately from embeddings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    usage: VoyageUsageBody | None = None


def parse_total_tokens(response_body: bytes) -> int | None:
    """Return Voyage total token usage, ignoring malformed usage metadata."""
    try:
        parsed = VoyageUsageResponseBody.model_validate_json(response_body)
    except ValidationError:
        return None
    if parsed.usage is None:
        return None
    return parsed.usage.total_tokens
