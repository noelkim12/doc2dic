"""Graph command group."""

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.graph_projection_service import GraphProjectionService
from doc2dic.services.graphify_export_service import GraphifyExportService
from doc2dic.storage import open_database

app = typer.Typer(help="Inspect glossary graph projections.")


@app.callback()
def graph() -> None:
    """Show graph command group help."""


@app.command("current")
def current_graph(
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the current graph as contract JSON."),
    ] = False,
) -> None:
    """Print the current deterministic AppGraph projection."""
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    with open_database(state.db_path) as connection:
        graph_projection = GraphProjectionService(connection).persist_current_snapshot()
    if as_json:
        typer.echo(graph_projection.graph.model_dump_json(by_alias=True))
        return
    typer.echo(f"Nodes: {len(graph_projection.graph.nodes)}")
    typer.echo(f"Edges: {len(graph_projection.graph.edges)}")
    typer.echo(f"Snapshot: {graph_projection.id}")


@app.command("export")
def export_graph(
    export_format: Annotated[
        str,
        typer.Option("--format", help="Export format. Currently supports graphify."),
    ] = "graphify",
) -> None:
    """Export a deterministic graph snapshot for external graph tooling."""
    if export_format != "graphify":
        typer.echo("Unsupported graph export format. Use --format graphify.", err=True)
        raise typer.Exit(code=2)
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    with open_database(state.db_path) as connection:
        result = GraphifyExportService(connection, state.root).export_graphify()
    typer.echo(f"Snapshot: {result.snapshot_dir}")
    typer.echo(f"Projection: {result.projection_path}")
    typer.echo(f"Markdown corpus: {result.corpus_dir}")
    typer.echo(f"Graphify extraction: {result.extraction_path}")
    if result.runtime_status.available:
        typer.echo(f"Graphify runtime: available {result.runtime_status.version}")
        return
    typer.echo(f"Graphify runtime: unavailable - {result.runtime_status.reason}")
