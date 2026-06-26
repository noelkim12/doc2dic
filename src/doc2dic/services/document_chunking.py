"""Section-aware document chunking for deterministic checks."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from doc2dic.domain import DocumentChunk
from doc2dic.services.document_parser import DocumentFormat, ParsedDocument

MAX_CHUNK_CHARS: Final = 1200
PREVIEW_CHARS: Final = 500


@dataclass(frozen=True, slots=True)
class TextSection:
    """A titled section extracted from a parsed document."""

    title: str
    text: str


def chunk_document(
    document_id: str,
    parsed: ParsedDocument,
) -> tuple[DocumentChunk, ...]:
    """Split a parsed document into stable, section-aware chunks."""
    chunks: list[DocumentChunk] = []
    for section in _sections(parsed):
        for part in _split_long_section(section.text):
            chunk_id = _chunk_id(document_id, len(chunks), part)
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    section_title=section.title,
                    ordinal=len(chunks),
                    text_preview=part[:PREVIEW_CHARS],
                    content_hash=sha256(part.encode()).hexdigest(),
                    raw_text=part,
                ),
            )
    return tuple(chunks)


def _sections(parsed: ParsedDocument) -> tuple[TextSection, ...]:
    if parsed.document_format is DocumentFormat.TEXT:
        return (TextSection(title=parsed.title, text=parsed.text.strip()),)

    sections: list[TextSection] = []
    current_title = parsed.title
    current_lines: list[str] = []
    for line in parsed.text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            _append_section(sections, current_title, current_lines)
            current_title = stripped.lstrip("#").strip() or parsed.title
            current_lines = []
            continue
        current_lines.append(line)
    _append_section(sections, current_title, current_lines)
    if len(sections) == 0:
        return (TextSection(title=parsed.title, text=parsed.text.strip()),)
    return tuple(sections)


def _append_section(
    sections: list[TextSection],
    title: str,
    lines: list[str],
) -> None:
    text = "\n".join(lines).strip()
    if text != "":
        sections.append(TextSection(title=title, text=text))


def _split_long_section(text: str) -> tuple[str, ...]:
    if len(text) <= MAX_CHUNK_CHARS:
        return (text,)
    paragraphs = tuple(
        part.strip() for part in text.split("\n\n") if part.strip() != ""
    )
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if current == "" else f"{current}\n\n{paragraph}"
        if len(candidate) <= MAX_CHUNK_CHARS:
            current = candidate
            continue
        if current != "":
            parts.append(current)
        current = paragraph
    if current != "":
        parts.append(current)
    return tuple(parts)


def _chunk_id(document_id: str, ordinal: int, text: str) -> str:
    digest = sha256(f"{document_id}:{ordinal}:{text}".encode()).hexdigest()[:16]
    return f"chunk_{digest}"
