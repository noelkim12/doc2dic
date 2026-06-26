"""UTF-8 Markdown and plain text parser for document checks."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from doc2dic.domain import DocumentMimeType

MARKDOWN_SUFFIXES: Final = frozenset({".md", ".markdown"})
TEXT_SUFFIXES: Final = frozenset({".txt", ""})
UNSUPPORTED_SUFFIXES: Final = frozenset({".pdf", ".docx", ".bin"})


class DocumentFormat(StrEnum):
    """Supported parser input formats."""

    MARKDOWN = "markdown"
    TEXT = "text"


class UnsupportedDocumentFormatError(RuntimeError):
    """Raised when a path cannot be parsed by the MVP checker."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Parsed document text and metadata."""

    path: Path
    title: str
    text: str
    mime_type: DocumentMimeType
    document_format: DocumentFormat


def parse_document(path: Path) -> ParsedDocument:
    """Parse a UTF-8 Markdown or text document."""
    document_format = _document_format(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        message = f"Unsupported document format for {path}: expected UTF-8 text"
        raise UnsupportedDocumentFormatError(message) from error
    if text.strip() == "":
        message = f"Unsupported document format for {path}: document is empty"
        raise UnsupportedDocumentFormatError(message)
    return ParsedDocument(
        path=path,
        title=_title_for(document_format, path, text),
        text=text,
        mime_type=_mime_type(document_format),
        document_format=document_format,
    )


def _document_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.casefold()
    if suffix in MARKDOWN_SUFFIXES:
        return DocumentFormat.MARKDOWN
    if suffix in TEXT_SUFFIXES:
        return DocumentFormat.TEXT
    if suffix in UNSUPPORTED_SUFFIXES:
        message = f"Unsupported document format for {path}: {suffix} is not supported"
        raise UnsupportedDocumentFormatError(message)
    message = (
        f"Unsupported document format for {path}: "
        "only Markdown and TXT are supported"
    )
    raise UnsupportedDocumentFormatError(message)


def _mime_type(document_format: DocumentFormat) -> DocumentMimeType:
    match document_format:
        case DocumentFormat.MARKDOWN:
            return DocumentMimeType.MARKDOWN
        case DocumentFormat.TEXT:
            return DocumentMimeType.PLAIN


def _title_for(document_format: DocumentFormat, path: Path, text: str) -> str:
    match document_format:
        case DocumentFormat.MARKDOWN:
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    return stripped.lstrip("#").strip() or path.stem
            return path.stem
        case DocumentFormat.TEXT:
            return path.stem
