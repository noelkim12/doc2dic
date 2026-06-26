"""Initialize project-local doc2dic state."""

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.project_state import ensure_config_file, state_for_root
from doc2dic.storage import initialize_project_storage

app = typer.Typer(help="Initialize doc2dic project state.")


@app.callback(invoke_without_command=True)
def init(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Rewrite .doc2dic/config.toml if it already exists.",
        ),
    ] = False,
) -> None:
    """Create `.doc2dic/config.toml` and migrate the local glossary database."""
    state = state_for_root(Path.cwd())
    ensure_config_file(state, force=force)
    db_path = initialize_project_storage(state.root)
    typer.echo(f"Initialized doc2dic project at {state.root}")
    typer.echo(f"Config: {state.config_path}")
    typer.echo(f"Database: {db_path}")
