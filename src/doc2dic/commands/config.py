"""Storage-backed project configuration commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.config_embedding import (
    app as embedding_app,
)
from doc2dic.commands.config_embedding import (
    configure_embedding,
    prompt_config_target,
    show_embedding_config,
)
from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.storage.connection import open_database
from doc2dic.storage.repositories import SettingsRepository

app = typer.Typer(help="Read and write project-local configuration settings.")


@app.callback(invoke_without_command=True)
def config(ctx: typer.Context) -> None:
    """Prompt for common configuration when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    choice = prompt_config_target()
    match choice.strip().lower():
        case "embedding":
            configure_embedding()
        case "show":
            show_config()
        case unknown:
            typer.echo(f"Unknown config target: {unknown}", err=True)
            raise typer.Exit(code=2)


@app.command("show")
def show_config() -> None:
    """Show known project config values without exposing secrets."""
    show_embedding_config()


@app.command("get")
def get_config(
    key: Annotated[str, typer.Argument(help="Setting key to read.")],
) -> None:
    """Print a setting value from the project database."""
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1) from error

    with open_database(state.db_path) as connection:
        value = SettingsRepository(connection).get_value(key)
    if value is None:
        typer.echo(f"No config value found for `{key}`.")
        raise typer.Exit(code=1)
    typer.echo(value)


@app.command("set")
def set_config(
    key: Annotated[str, typer.Argument(help="Setting key to write.")],
    value: Annotated[str, typer.Argument(help="Setting value to persist.")],
) -> None:
    """Persist a setting value in the project database."""
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1) from error

    with open_database(state.db_path) as connection:
        SettingsRepository(connection).set_value(key, value)
    typer.echo(f"{key}={value}")


app.add_typer(embedding_app, name="embedding")
