"""Document routes for the local API contract."""

import sqlite3
from pathlib import Path
from typing import ClassVar

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette import status

from doc2dic.domain import Document, TermOccurrence
from doc2dic.server.dependencies import DatabaseDep, ProjectSettingsDep
from doc2dic.server.errors import (
    error_response,
    is_sqlite_lock_error,
    sqlite_lock_response,
)
from doc2dic.services.conflict_detector import analyze_document
from doc2dic.services.document_parser import UnsupportedDocumentFormatError
from doc2dic.storage.repositories.documents import DocumentRepository

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


class AnalyzePathBody(BaseModel):
    """Accepted document path analysis request body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1000)


class DocumentPayload(BaseModel):
    """Document response payload matching the frozen public contract."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    path: str
    title: str
    content_hash: str = Field(alias="contentHash")
    mime_type: str = Field(alias="mimeType")
    chunk_ids: tuple[str, ...] = Field(alias="chunkIds")
    analyzed_at: str = Field(alias="analyzedAt")


class TermOccurrencePayload(BaseModel):
    """Term occurrence payload matching the frozen public contract."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    id: str
    document_id: str = Field(alias="documentId")
    chunk_id: str = Field(alias="chunkId")
    surface: str
    offset_start: int = Field(alias="offsetStart")
    offset_end: int = Field(alias="offsetEnd")
    confidence: float
    concept_id: str | None = Field(default=None, alias="conceptId")


@router.post("/analyze-path", status_code=status.HTTP_202_ACCEPTED, response_model=None)
def analyze_document_path(
    database: DatabaseDep,
    settings: ProjectSettingsDep,
    body: AnalyzePathBody,
) -> Response | JSONResponse:
    """Analyze a Markdown/TXT document path and persist review issues."""
    document_path = _resolve_document_path(settings.project_root, body.path)
    if not document_path.exists():
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "document_path_not_found",
            f"Document path {body.path} was not found.",
        )
    try:
        _ = analyze_document(database, document_path, write_issues=True)
    except UnsupportedDocumentFormatError as error:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_document_format",
            str(error),
        )
    except sqlite3.OperationalError as error:
        if is_sqlite_lock_error(error):
            return sqlite_lock_response()
        raise
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("")
def list_documents(database: DatabaseDep) -> tuple[DocumentPayload, ...]:
    """Return documents from the project glossary database."""
    return tuple(
        _document_payload(document)
        for document in DocumentRepository(database).list_documents()
    )


@router.get("/{document_id}", response_model=None)
def get_document(
    database: DatabaseDep,
    document_id: str,
) -> DocumentPayload | JSONResponse:
    """Return one document by id."""
    document = DocumentRepository(database).get_document(document_id)
    if document is None:
        return _document_not_found(document_id)
    return _document_payload(document)


@router.get("/{document_id}/occurrences", response_model=None)
def list_document_occurrences(
    database: DatabaseDep,
    document_id: str,
) -> tuple[TermOccurrencePayload, ...] | JSONResponse:
    """Return term occurrences for one document."""
    repository = DocumentRepository(database)
    if repository.get_document(document_id) is None:
        return _document_not_found(document_id)
    return tuple(
        _occurrence_payload(occurrence)
        for occurrence in repository.list_occurrences(document_id)
    )


def _resolve_document_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (project_root / path).resolve(strict=False)


def _document_payload(document: Document) -> DocumentPayload:
    return DocumentPayload(
        id=document.id,
        path=document.path,
        title=document.title,
        contentHash=document.content_hash,
        mimeType=document.mime_type.value,
        chunkIds=document.chunk_ids,
        analyzedAt=document.analyzed_at,
    )


def _occurrence_payload(occurrence: TermOccurrence) -> TermOccurrencePayload:
    return TermOccurrencePayload(
        id=occurrence.id,
        documentId=occurrence.document_id,
        chunkId=occurrence.chunk_id,
        conceptId=occurrence.concept_id,
        surface=occurrence.surface,
        offsetStart=occurrence.offset_start,
        offsetEnd=occurrence.offset_end,
        confidence=occurrence.confidence,
    )


def _document_not_found(document_id: str) -> JSONResponse:
    return error_response(
        status.HTTP_404_NOT_FOUND,
        "document_not_found",
        f"Document {document_id} was not found.",
    )
