"""Persist Graphify-compatible derived graph export snapshots."""

import sqlite3
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import which
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict

from doc2dic.services.graph_projection_service import GraphProjectionService
from doc2dic.services.graphify_adapter import (
    GRAPHIFY_EXECUTABLE_NAME,
    GRAPHIFY_PACKAGE_NAME,
    PINNED_GRAPHIFY_VERSION,
    GraphifyAdapter,
    GraphifyExtraction,
    GraphifyProjection,
)
from doc2dic.storage.connection import DB_DIR_NAME

GRAPH_SNAPSHOTS_DIR: Final = "graph_snapshots"


class GraphifyRuntimeStatus(BaseModel):
    """Observed optional Graphify runtime capability."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    package_name: str
    executable_name: str
    executable_path: str | None
    version: str | None
    pinned_version: str
    schema_supported: bool
    available: bool
    reason: str


class GraphifyRuntime:
    """Detect optional Graphify executable/version/schema capability."""

    def __init__(self, executable_name: str = GRAPHIFY_EXECUTABLE_NAME) -> None:
        """Store the executable name used for capability checks."""
        self._executable_name: str
        self._executable_name = executable_name

    def detect(self) -> GraphifyRuntimeStatus:
        """Return availability without raising when Graphify is missing."""
        executable_path = which(self._executable_name)
        if executable_path is None:
            return self._status(
                None,
                None,
                schema_supported=False,
                reason="graphify executable not found on PATH",
            )
        version = _runtime_version(Path(executable_path))
        if version != PINNED_GRAPHIFY_VERSION:
            observed = version or "unknown"
            reason = f"graphifyy version {observed} does not match pinned 0.4.29"
            return self._status(
                executable_path,
                version,
                schema_supported=False,
                reason=reason,
            )
        schema_supported = _runtime_schema_supported(Path(executable_path))
        if not schema_supported:
            return self._status(
                executable_path,
                version,
                schema_supported=False,
                reason="graphify schema capability unavailable",
            )
        return self._status(
            executable_path,
            version,
            schema_supported=True,
            reason="available",
        )

    def _status(
        self,
        executable_path: str | None,
        version: str | None,
        *,
        schema_supported: bool,
        reason: str,
    ) -> GraphifyRuntimeStatus:
        return GraphifyRuntimeStatus(
            package_name=GRAPHIFY_PACKAGE_NAME,
            executable_name=self._executable_name,
            executable_path=executable_path,
            version=version,
            pinned_version=PINNED_GRAPHIFY_VERSION,
            schema_supported=schema_supported,
            available=schema_supported and version == PINNED_GRAPHIFY_VERSION,
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class GraphifyExportResult:
    """File paths and payloads produced by a graphify export."""

    snapshot_dir: Path
    app_graph_path: Path
    projection_path: Path
    extraction_path: Path
    corpus_dir: Path
    runtime_status_path: Path
    projection: GraphifyProjection
    extraction: GraphifyExtraction
    runtime_status: GraphifyRuntimeStatus


class GraphifyExportService:
    """Write deterministic graphify projection and Markdown corpus snapshots."""

    def __init__(self, connection: sqlite3.Connection, project_root: Path) -> None:
        """Store the database connection and project root."""
        self._connection: sqlite3.Connection
        self._connection = connection
        self._project_root: Path
        self._project_root = project_root

    def export_graphify(self) -> GraphifyExportResult:
        """Persist a content-addressed graphify export snapshot."""
        snapshot = GraphProjectionService(self._connection).persist_current_snapshot()
        adapter = GraphifyAdapter(self._connection)
        projection = adapter.projection_for_graph(snapshot.graph)
        extraction = adapter.extraction_for_graph(snapshot.graph)
        runtime_status = GraphifyRuntime().detect()
        snapshot_dir = self._snapshot_dir(projection, extraction)
        corpus_dir = snapshot_dir / "glossary_export"
        app_graph_path = snapshot_dir / "app_graph.json"
        projection_path = snapshot_dir / "graphify_projection.json"
        extraction_path = snapshot_dir / "graphify_extraction.json"
        runtime_status_path = snapshot_dir / "runtime_status.json"

        snapshot_dir.mkdir(parents=True, exist_ok=True)
        _ = app_graph_path.write_text(
            snapshot.graph.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        _ = projection_path.write_text(
            projection.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        _ = extraction_path.write_text(
            extraction.model_dump_json(),
            encoding="utf-8",
        )
        _ = runtime_status_path.write_text(
            runtime_status.model_dump_json(),
            encoding="utf-8",
        )
        _write_corpus(snapshot_dir, projection)
        return GraphifyExportResult(
            snapshot_dir=snapshot_dir,
            app_graph_path=app_graph_path,
            projection_path=projection_path,
            extraction_path=extraction_path,
            corpus_dir=corpus_dir,
            runtime_status_path=runtime_status_path,
            projection=projection,
            extraction=extraction,
            runtime_status=runtime_status,
        )

    def _snapshot_dir(
        self,
        projection: GraphifyProjection,
        extraction: GraphifyExtraction,
    ) -> Path:
        digest = _export_id(projection, extraction)
        return self._project_root / DB_DIR_NAME / GRAPH_SNAPSHOTS_DIR / digest


def _export_id(
    projection: GraphifyProjection,
    extraction: GraphifyExtraction,
) -> str:
    raw = projection.model_dump_json(by_alias=True) + extraction.model_dump_json()
    return f"graphify_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _write_corpus(snapshot_dir: Path, projection: GraphifyProjection) -> None:
    for document in projection.documents:
        document_path = snapshot_dir / document.path
        document_path.parent.mkdir(parents=True, exist_ok=True)
        _ = document_path.write_text(document.body, encoding="utf-8")


def _runtime_version(executable_path: Path) -> str | None:
    python_path = _python_from_executable(executable_path)
    if python_path is None:
        return None
    result = subprocess.run(  # noqa: S603
        [
            python_path.as_posix(),
            "-c",
            "from importlib import metadata; print(metadata.version('graphifyy'))",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _runtime_schema_supported(executable_path: Path) -> bool:
    python_path = _python_from_executable(executable_path)
    if python_path is None:
        return False
    schema_probe = (
        "from graphify.validate import REQUIRED_EDGE_FIELDS, REQUIRED_NODE_FIELDS;"
        "print(','.join(sorted(REQUIRED_NODE_FIELDS)));"
        "print(','.join(sorted(REQUIRED_EDGE_FIELDS)))"
    )
    result = subprocess.run(  # noqa: S603
        [python_path.as_posix(), "-c", schema_probe],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    return result.stdout.splitlines() == [
        "file_type,id,label,source_file",
        "confidence,relation,source,source_file,target",
    ]


def _python_from_executable(executable_path: Path) -> Path | None:
    try:
        first_line = executable_path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    raw_path = first_line.removeprefix("#!").strip()
    if " " in raw_path:
        return None
    return Path(raw_path)
