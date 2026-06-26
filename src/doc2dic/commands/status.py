"""Show project-local doc2dic status."""

from pathlib import Path

import typer

from doc2dic.commands import config
from doc2dic.commands.project_state import (
    ProjectNotFoundError,
    discover_project,
    read_storage_status,
)

app = typer.Typer(help="Show doc2dic project status.")
app.add_typer(config.app, name="config")


@app.callback(invoke_without_command=True)
def status(ctx: typer.Context) -> None:
    """Print project root, config, database, and storage readiness."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        state = discover_project(Path.cwd())
        storage_status = read_storage_status(state)
    except ProjectNotFoundError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1) from error

    typer.echo(f"Project root: {state.root}")
    typer.echo(f"Config: {state.config_path}")
    typer.echo("Database: ready")
    typer.echo(f"Database path: {state.db_path}")
    typer.echo(f"Schema version: {storage_status.schema_version}")
    typer.echo(f"Concepts: {storage_status.concept_count}")
    typer.echo(f"Open issues: {storage_status.issue_count}")
