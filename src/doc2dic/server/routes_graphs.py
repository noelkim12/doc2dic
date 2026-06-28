"""Graph routes for the local API contract."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette import status

from doc2dic.domain import AppGraph, GraphSnapshot
from doc2dic.server.dependencies import DatabaseDep, ProjectSettingsDep
from doc2dic.server.errors import error_response
from doc2dic.services.graph_projection_service import (
    GraphProjectionError,
    GraphProjectionService,
)
from doc2dic.services.graphify_adapter import GraphifyProjection
from doc2dic.services.graphify_export_service import GraphifyExportService
from doc2dic.storage.repositories.graphs import GraphRepository

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
        return _graph_projection_error(error)
    return snapshot.graph


@router.post("/rebuild", status_code=status.HTTP_202_ACCEPTED, response_model=None)
def rebuild_graph(database: DatabaseDep) -> GraphSnapshot | JSONResponse:
    """Persist and return the current deterministic graph snapshot."""
    try:
        return GraphProjectionService(database).persist_current_snapshot()
    except GraphProjectionError as error:
        return _graph_projection_error(error)


@router.get("/snapshots")
def list_graph_snapshots(database: DatabaseDep) -> tuple[GraphSnapshot, ...]:
    """Return persisted graph snapshots."""
    return GraphRepository(database).list_snapshots()


@router.get("/snapshots/{snapshot_id}", response_model=None)
def get_graph_snapshot(
    database: DatabaseDep,
    snapshot_id: str,
) -> GraphSnapshot | JSONResponse:
    """Return one persisted graph snapshot by id."""
    snapshot = GraphRepository(database).get_snapshot(snapshot_id)
    if snapshot is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "graph_snapshot_not_found",
            f"Graph snapshot {snapshot_id} was not found.",
        )
    return snapshot


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
        return _graph_projection_error(error)
    return result.projection


def _graph_projection_error(error: GraphProjectionError) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_graph_relation",
        str(error),
    )
