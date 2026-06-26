"""Document check orchestration for parser, chunker, and issue services."""

import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from doc2dic.domain import (
    Document,
    DocumentChunk,
    DocumentStatus,
    TermIssue,
    TermOccurrence,
)
from doc2dic.services.document_chunking import chunk_document
from doc2dic.services.document_glossary import load_glossary_terms
from doc2dic.services.document_issue_detection import CREATED_AT, detect_issues
from doc2dic.services.document_occurrences import detect_occurrences, term_occurrences
from doc2dic.services.document_parser import parse_document
from doc2dic.storage.repositories.documents import DocumentRepository
from doc2dic.storage.repositories.issues import IssueRepository

DOC_ID_HASH_CHARS: Final = 16


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Document check result written by the CLI boundary."""

    document: Document
    chunks: tuple[DocumentChunk, ...]
    occurrences: tuple[TermOccurrence, ...]
    issues: tuple[TermIssue, ...]


def check_document(
    connection: sqlite3.Connection,
    path: Path,
    *,
    write_issues: bool,
) -> CheckResult:
    """Parse, chunk, persist occurrences, and optionally write issues."""
    parsed = parse_document(path)
    document_id = _document_id(path)
    chunks = chunk_document(document_id, parsed)
    document = Document(
        id=document_id,
        path=str(path),
        title=parsed.title,
        content_hash=sha256(parsed.text.encode()).hexdigest(),
        mime_type=parsed.mime_type,
        chunk_ids=tuple(chunk.id for chunk in chunks),
        analyzed_at=CREATED_AT,
        raw_text=parsed.text,
        status=DocumentStatus.ANALYZED,
    )
    terms = load_glossary_terms(connection)
    detections = detect_occurrences(chunks, terms)
    occurrences = term_occurrences(document_id, detections)
    issues = detect_issues(document_id, detections, terms)
    result = CheckResult(document, chunks, occurrences, issues)
    _persist_check_result(connection, result, write_issues)
    return result


def _persist_check_result(
    connection: sqlite3.Connection,
    result: CheckResult,
    write_issues: bool,
) -> None:
    with connection:
        document_repository = DocumentRepository(connection)
        document_repository.upsert_document(result.document)
        for chunk in result.chunks:
            document_repository.upsert_chunk(chunk)
        for occurrence in result.occurrences:
            document_repository.upsert_occurrence(occurrence)
        if write_issues:
            issue_repository = IssueRepository(connection)
            for issue in result.issues:
                issue_repository.upsert_issue(issue)


def _document_id(path: Path) -> str:
    digest = sha256(str(path.resolve()).encode()).hexdigest()[:DOC_ID_HASH_CHARS]
    return f"doc_{digest}"
