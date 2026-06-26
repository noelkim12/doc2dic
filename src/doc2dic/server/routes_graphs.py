"""Graph routes for the local API contract."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette import status

from doc2dic.domain import AppGraph
from doc2dic.server.dependencies import DatabaseDep, ProjectSettingsDep
from doc2dic.server.errors import error_response, not_implemented_response
from doc2dic.services.graph_projection_service import (
    GraphProjectionError,
    GraphProjectionService,
)
from doc2dic.services.graphify_adapter import GraphifyProjection
from doc2dic.services.graphify_export_service import GraphifyExportService

router = APIRouter(
    prefix="/api/graphs",
    tags=["graphs"],
)


@router.get("/current", response_model=None)
def get_current_graph(database: DatabaseDep) -> AppGraph | JSONResponse:
    """Return the current deterministic AppGraph projection."""
    try:
        snapshot = GraphProjectionService(database).persist_current_snapshot()
    except GraphProjectionError as error:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_graph_relation",
            str(error),
        )
    return snapshot.graph


@router.post("/rebuild")
def rebuild_graph() -> JSONResponse:
    """Return the pending graph rebuild stub."""
    return not_implemented_response()


@router.get("/snapshots")
def list_graph_snapshots() -> JSONResponse:
    """Return the pending graph snapshot list stub."""
    return not_implemented_response()


@router.get("/snapshots/{snapshot_id}")
def get_graph_snapshot(snapshot_id: str) -> JSONResponse:
    """Return the pending graph snapshot detail stub."""
    _ = snapshot_id
    return not_implemented_response()


@router.post("/graphify/export", response_model=None)
def export_graphify_projection(
    database: DatabaseDep,
    settings: ProjectSettingsDep,
) -> GraphifyProjection | JSONResponse:
    """Persist and return a deterministic Graphify projection export."""
    try:
        service = GraphifyExportService(database, settings.project_root)
        result = service.export_graphify()
    except GraphProjectionError as error:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_graph_relation",
            str(error),
        )
    return result.projection
