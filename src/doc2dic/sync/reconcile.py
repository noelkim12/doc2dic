"""Content-hash reconcile for Markdown/TXT evidence files."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

from doc2dic.domain import Document, DocumentStatus
from doc2dic.services.document_chunking import chunk_document
from doc2dic.services.document_parser import ParsedDocument
from doc2dic.storage.repositories.documents import DocumentRepository
from doc2dic.storage.repositories.search import SearchIndexRepository
from doc2dic.storage.sqlite_rows import text_cell
from doc2dic.sync.models import (
    FreshnessReport,
    MissingFile,
    PendingFile,
    ReconcileResult,
    SourceFile,
    StaleFile,
)
from doc2dic.sync.scanner import scan_project

DOC_ID_HASH_CHARS = 16


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """Stored document fields needed for freshness checks."""

    id: str
    path: str
    content_hash: str


def freshness_report(
    connection: sqlite3.Connection,
    project_root: Path,
) -> FreshnessReport:
    """Compare safe project scan hashes against stored documents."""
    root = project_root.resolve(strict=False)
    scan = scan_project(root)
    stored = _stored_documents(connection)
    indexed = _indexed_documents(stored, root)
    pending: list[PendingFile] = []
    stale: list[StaleFile] = []
    seen_ids: set[str] = set()
    for source in scan.supported:
        document = indexed.get(source.path.as_posix())
        if document is None:
            document = indexed.get(str(source.absolute_path))
        if document is None:
            pending.append(PendingFile(source.path))
            continue
        seen_ids.add(document.id)
        if document.content_hash != source.content_hash:
            stale.append(StaleFile(source.path, "content differs from stored hash"))
    missing = tuple(
        MissingFile(_display_path(document, root))
        for document in stored
        if document.id not in seen_ids and _is_project_document(document, root)
    )
    return FreshnessReport(tuple(pending), tuple(stale), missing, scan.unsupported)


def reconcile_project(
    connection: sqlite3.Connection,
    project_root: Path,
) -> ReconcileResult:
    """Ingest supported Markdown/TXT files and rebuild search rows."""
    root = project_root.resolve(strict=False)
    scan = scan_project(root)
    stored = _stored_documents(connection)
    indexed = _indexed_documents(stored, root)
    repository = DocumentRepository(connection)
    for source in scan.supported:
        document_id = _document_id_for(source, indexed)
        _replace_document_chunks(connection, document_id)
        chunks = chunk_document(document_id, _parsed_document(source))
        document = Document(
            id=document_id,
            path=source.path.as_posix(),
            title=source.title,
            content_hash=source.content_hash,
            mime_type=source.mime_type,
            chunk_ids=tuple(chunk.id for chunk in chunks),
            analyzed_at=_timestamp(),
            raw_text=source.text,
            status=DocumentStatus.ANALYZED,
        )
        repository.upsert_document(document)
        for chunk in chunks:
            repository.upsert_chunk(chunk)
    SearchIndexRepository(connection).rebuild()
    return ReconcileResult(
        scanned=len(scan.supported) + len(scan.unsupported),
        ingested=len(scan.supported),
        unsupported=scan.unsupported,
    )


def catch_up_pending_files(
    connection: sqlite3.Connection,
    project_root: Path,
) -> ReconcileResult | None:
    """Reconcile first-call pending files when no stale stored files exist."""
    report = freshness_report(connection, project_root)
    if not report.pending or report.stale or report.missing:
        return None
    return reconcile_project(connection, project_root)


def _stored_documents(connection: sqlite3.Connection) -> tuple[StoredDocument, ...]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute("select id, path, content_hash from documents").fetchall(),
    )
    return tuple(
        StoredDocument(
            id=text_cell(row, "id"),
            path=text_cell(row, "path"),
            content_hash=text_cell(row, "content_hash"),
        )
        for row in rows
    )


def _indexed_documents(
    documents: tuple[StoredDocument, ...],
    project_root: Path,
) -> dict[str, StoredDocument]:
    indexed: dict[str, StoredDocument] = {}
    for document in documents:
        indexed[document.path] = document
        display_path = _display_path(document, project_root).as_posix()
        indexed[display_path] = document
    return indexed


def _document_id_for(
    source: SourceFile,
    indexed: dict[str, StoredDocument],
) -> str:
    stored = indexed.get(source.path.as_posix())
    if stored is None:
        stored = indexed.get(str(source.absolute_path))
    if stored is not None:
        return stored.id
    digest = sha256(str(source.absolute_path).encode()).hexdigest()[:DOC_ID_HASH_CHARS]
    return f"doc_{digest}"


def _replace_document_chunks(connection: sqlite3.Connection, document_id: str) -> None:
    with connection:
        _ = connection.execute(
            "delete from term_occurrences where document_id = ?",
            (document_id,),
        )
        _ = connection.execute(
            "delete from document_chunks where document_id = ?",
            (document_id,),
        )


def _parsed_document(source: SourceFile) -> ParsedDocument:
    return ParsedDocument(
        path=source.absolute_path,
        title=source.title,
        text=source.text,
        mime_type=source.mime_type,
        document_format=source.document_format,
    )


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_project_document(document: StoredDocument, project_root: Path) -> bool:
    path = Path(document.path)
    if not path.is_absolute():
        return True
    try:
        _ = path.relative_to(project_root)
    except ValueError:
        return False
    return True


def _display_path(document: StoredDocument, project_root: Path) -> Path:
    path = Path(document.path)
    if not path.is_absolute():
        return path
    try:
        return path.relative_to(project_root)
    except ValueError:
        return path
