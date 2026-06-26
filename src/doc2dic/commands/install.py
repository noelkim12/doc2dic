"""Install doc2dic integrations into local agent configs."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from doc2dic.installer.opencode import install_local_opencode

app = typer.Typer(help="Install local doc2dic agent integrations.")


class InstallTarget(StrEnum):
    """Supported installer targets."""

    OPENCODE = "opencode"


@app.callback(invoke_without_command=True)
def install(
    target: Annotated[
        InstallTarget,
        typer.Option("--target", help="Agent config target to install."),
    ] = InstallTarget.OPENCODE,
    local: Annotated[
        bool,
        typer.Option("--local", help="Write the current directory's local config."),
    ] = False,
) -> None:
    """Install doc2dic MCP into the requested local agent target."""
    if not local:
        message = "Only --local installs are supported."
        raise typer.BadParameter(message)

    project_root = Path.cwd()
    package_root = Path(__file__).resolve().parents[3]
    match target:
        case InstallTarget.OPENCODE:
            result = install_local_opencode(project_root, package_root)

    typer.echo(
        f"Installed doc2dic MCP into {result.config_path} ({result.action}).",
    )
    if result.backup_path is not None:
        typer.echo(f"Backup: {result.backup_path}")
