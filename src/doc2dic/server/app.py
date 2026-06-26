"""FastAPI application factory for doc2dic."""

from pathlib import Path

from fastapi import FastAPI

from doc2dic.server.dependencies import (
    ProjectSettings,
    get_project_settings,
    make_project_settings,
)
from doc2dic.server.routes_concepts import router as concepts_router
from doc2dic.server.routes_documents import router as documents_router
from doc2dic.server.routes_graphs import router as graphs_router
from doc2dic.server.routes_health import router as health_router
from doc2dic.server.routes_issues import router as issues_router
from doc2dic.server.routes_search import router as search_router


def create_app(*, project_root: Path | None = None) -> FastAPI:
    """Create the root FastAPI application and wire route modules."""
    resolved_root = Path.cwd() if project_root is None else project_root
    settings = make_project_settings(resolved_root)

    def current_project_settings() -> ProjectSettings:
        return settings

    fastapi_app = FastAPI(title="doc2dic", version="0.1.0")
    fastapi_app.dependency_overrides[get_project_settings] = current_project_settings
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(concepts_router)
    fastapi_app.include_router(documents_router)
    fastapi_app.include_router(issues_router)
    fastapi_app.include_router(search_router)
    fastapi_app.include_router(graphs_router)
    return fastapi_app


app = create_app()
