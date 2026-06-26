"""Embedding metadata domain models."""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingOwnerType(StrEnum):
    """Supported embedding owner categories."""

    CONCEPT = "concept"
    TERM_CANDIDATE = "term_candidate"
    DOCUMENT_CHUNK = "document_chunk"
    ISSUE = "issue"


class Embedding(BaseModel):
    """Embedding metadata without requiring sqlite-vec at migration time."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: int = Field(ge=1)
    owner_type: EmbeddingOwnerType
    owner_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    dimension: int = Field(gt=0)
    content_hash: str = Field(min_length=16, max_length=128)
    created_at: str
