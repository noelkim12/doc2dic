"""Serve local doc2dic integration surfaces."""

from pathlib import Path
from typing import Annotated

import anyio
import typer

from doc2dic.mcp.server import build_doc2dic_mcp_server

app = typer.Typer(help="Run local doc2dic integration surfaces.")


@app.callback(invoke_without_command=True)
def serve(
    mcp: Annotated[
        bool,
        typer.Option(
            "--mcp",
            help="Run the doc2dic MCP server over stdio.",
        ),
    ] = False,
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            help="Project root used by the MCP server.",
        ),
    ] = None,
) -> None:
    """Run an explicitly selected local serve surface."""
    if not mcp:
        typer.echo("Web serving is not implemented. Use `doc2dic serve --mcp`.")
        raise typer.Exit(code=1)

    raw_project_root = Path.cwd() if path is None else path.expanduser()
    project_root = raw_project_root.resolve()
    command = "doc2dic serve --mcp --path <project>"
    path_usage = f"Run `{command}` with an existing project root."
    if not project_root.exists():
        message = f"Project path does not exist. {path_usage}"
        typer.echo(
            message,
        )
        raise typer.Exit(code=1)
    if not project_root.is_dir():
        message = f"Project path must be a directory. {path_usage}"
        typer.echo(
            message,
        )
        raise typer.Exit(code=1)

    server = build_doc2dic_mcp_server(project_root)
    anyio.run(server.run_stdio_async)
