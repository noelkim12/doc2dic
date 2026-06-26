"""Document ingestion domain models."""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentMimeType(StrEnum):
    """Supported imported document MIME types."""

    MARKDOWN = "text/markdown"
    PLAIN = "text/plain"
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocumentStatus(StrEnum):
    """Document processing status."""

    IMPORTED = "imported"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class Document(BaseModel):
    """Imported source document metadata and extracted text."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^doc_[A-Za-z0-9_-]+$")
    path: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=240)
    content_hash: str = Field(min_length=16, max_length=128)
    mime_type: DocumentMimeType
    chunk_ids: tuple[str, ...] = Field(default_factory=tuple)
    analyzed_at: str
    raw_text: str = ""
    status: DocumentStatus = DocumentStatus.IMPORTED


class DocumentChunk(BaseModel):
    """A searchable chunk of an imported document."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^chunk_[A-Za-z0-9_-]+$")
    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9_-]+$")
    section_title: str = Field(min_length=1, max_length=240)
    ordinal: int = Field(ge=0)
    text_preview: str = Field(min_length=1, max_length=500)
    content_hash: str = Field(min_length=16, max_length=128)
    raw_text: str = ""


class TermOccurrence(BaseModel):
    """A detected term surface within a document chunk."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^occ_[A-Za-z0-9_-]+$")
    document_id: str = Field(pattern=r"^doc_[A-Za-z0-9_-]+$")
    chunk_id: str = Field(pattern=r"^chunk_[A-Za-z0-9_-]+$")
    surface: str = Field(min_length=1, max_length=160)
    offset_start: int = Field(ge=0)
    offset_end: int = Field(ge=1)
    confidence: float = Field(ge=0, le=1)
    concept_id: str | None = None

    @model_validator(mode="after")
    def offset_end_must_follow_start(self) -> "TermOccurrence":
        """Reject inverted occurrence spans."""
        if self.offset_end <= self.offset_start:
            msg = "offset_end must be greater than offset_start"
            raise ValueError(msg)
        return self
