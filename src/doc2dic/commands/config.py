"""Storage-backed project configuration commands."""

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.storage.connection import open_database
from doc2dic.storage.repositories import SettingsRepository

app = typer.Typer(help="Read and write project-local configuration settings.")


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
