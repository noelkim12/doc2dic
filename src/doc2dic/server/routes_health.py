"""Health route for the local API."""

from typing import TypedDict

from fastapi import APIRouter, Depends

from doc2dic.server.dependencies import get_project_settings


class HealthResponse(TypedDict):
    """Health endpoint response shape."""

    status: str


router = APIRouter(
    prefix="/api",
    tags=["health"],
    dependencies=[Depends(get_project_settings)],
)


@router.get("/health")
def health() -> HealthResponse:
    """Return local service health."""
    return {"status": "ok"}
