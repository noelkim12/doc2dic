"""Uninstall doc2dic integrations from local agent configs."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from doc2dic.installer.opencode import uninstall_local_opencode

app = typer.Typer(help="Uninstall local doc2dic agent integrations.")


class UninstallTarget(StrEnum):
    """Supported uninstaller targets."""

    OPENCODE = "opencode"


@app.callback(invoke_without_command=True)
def uninstall(
    target: Annotated[
        UninstallTarget,
        typer.Option("--target", help="Agent config target to uninstall."),
    ] = UninstallTarget.OPENCODE,
    local: Annotated[
        bool,
        typer.Option("--local", help="Update the current directory's local config."),
    ] = False,
) -> None:
    """Remove doc2dic MCP from the requested local agent target."""
    if not local:
        message = "Only --local uninstalls are supported."
        raise typer.BadParameter(message)

    match target:
        case UninstallTarget.OPENCODE:
            result = uninstall_local_opencode(Path.cwd())

    typer.echo(
        f"Uninstalled doc2dic MCP from {result.config_path} ({result.action}).",
    )
    if result.backup_path is not None:
        typer.echo(f"Backup: {result.backup_path}")
