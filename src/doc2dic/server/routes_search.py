"""Search route stubs for the local API contract."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from doc2dic.server.dependencies import get_database
from doc2dic.server.errors import not_implemented_response

router = APIRouter(
    prefix="/api/search",
    tags=["search"],
    dependencies=[Depends(get_database)],
)


@router.get("/concepts")
def search_concepts(q: str) -> JSONResponse:
    """Return the pending concept search stub."""
    _ = q
    return not_implemented_response()


@router.get("/similar-concepts")
def search_similar_concepts(text: str) -> JSONResponse:
    """Return the pending similar concept search stub."""
    _ = text
    return not_implemented_response()
