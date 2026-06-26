"""Document route stubs for the local API contract."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from doc2dic.server.dependencies import get_database
from doc2dic.server.errors import not_implemented_response

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(get_database)],
)


@router.post("/analyze-path")
def analyze_document_path() -> JSONResponse:
    """Return the pending document analysis stub."""
    return not_implemented_response()


@router.get("")
def list_documents() -> JSONResponse:
    """Return the pending document list stub."""
    return not_implemented_response()


@router.get("/{document_id}")
def get_document(document_id: str) -> JSONResponse:
    """Return the pending document detail stub."""
    _ = document_id
    return not_implemented_response()


@router.get("/{document_id}/occurrences")
def list_document_occurrences(document_id: str) -> JSONResponse:
    """Return the pending document occurrences stub."""
    _ = document_id
    return not_implemented_response()
