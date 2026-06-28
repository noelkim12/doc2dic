"""Serve local doc2dic integration surfaces."""

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final

import anyio
import typer

from doc2dic.mcp.server import build_doc2dic_mcp_server

app = typer.Typer(help="Run local doc2dic integration surfaces.")
API_HOST: Final = "127.0.0.1"
API_PORT: Final = 8765
WEB_HOST: Final = "127.0.0.1"
DEFAULT_WEB_PORT: Final = 5173
PROCESS_POLL_SECONDS: Final = 0.25


@dataclass(frozen=True, slots=True)
class WebServeConfig:
    """Resolved inputs for serving the local API and frontend together."""

    project_root: Path
    web_port: int = DEFAULT_WEB_PORT


@dataclass(frozen=True, slots=True)
class WebServePlan:
    """Subprocess launch plan for the local API and frontend."""

    api_command: tuple[str, ...]
    api_cwd: Path
    web_command: tuple[str, ...]
    web_cwd: Path


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
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
    if ctx.invoked_subcommand is not None:
        return
    if not mcp:
        typer.echo("Choose `doc2dic serve web` or `doc2dic serve --mcp`.")
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


@app.command("web")
def serve_web(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            help="Project root containing .doc2dic/glossary.sqlite3.",
        ),
    ] = None,
    web_port: Annotated[
        int,
        typer.Option("--web-port", help="Vite frontend port."),
    ] = DEFAULT_WEB_PORT,
) -> None:
    """Run the FastAPI server and Vite frontend for one local project."""
    project_root = resolve_project_root(path, "doc2dic serve web --path <project>")
    exit_code = run_web_server(
        WebServeConfig(project_root=project_root, web_port=web_port),
    )
    raise typer.Exit(code=exit_code)


def resolve_project_root(path: Path | None, command: str) -> Path:
    """Resolve and validate a CLI project-root option."""
    raw_project_root = Path.cwd() if path is None else path.expanduser()
    project_root = raw_project_root.resolve()
    path_usage = f"Run `{command}` with an existing project root."
    if not project_root.exists():
        message = f"Project path does not exist. {path_usage}"
        typer.echo(message)
        raise typer.Exit(code=1)
    if not project_root.is_dir():
        message = f"Project path must be a directory. {path_usage}"
        typer.echo(message)
        raise typer.Exit(code=1)
    return project_root


def run_web_server(config: WebServeConfig) -> int:
    """Run API and frontend processes until one exits or the user interrupts."""
    plan = build_web_serve_plan(config)
    typer.echo(f"API: http://{API_HOST}:{API_PORT}")
    typer.echo(f"Web: http://{WEB_HOST}:{config.web_port}")
    typer.echo("Press Ctrl+C to stop both processes.")

    api_process = subprocess.Popen(plan.api_command, cwd=plan.api_cwd)  # noqa: S603
    web_process = subprocess.Popen(plan.web_command, cwd=plan.web_cwd)  # noqa: S603
    try:
        return wait_for_first_exit(api_process, web_process)
    except KeyboardInterrupt:
        return 130
    finally:
        stop_process(api_process)
        stop_process(web_process)


def build_web_serve_plan(config: WebServeConfig) -> WebServePlan:
    """Build subprocess commands for local API and frontend serving."""
    npm_command = shutil.which("npm")
    if npm_command is None:
        typer.echo("npm is required to run the frontend dev server.")
        raise typer.Exit(code=1)

    web_cwd = Path(__file__).resolve().parents[3] / "web"
    package_json = web_cwd / "package.json"
    if not package_json.exists():
        typer.echo(f"Frontend package not found: {package_json}")
        raise typer.Exit(code=1)

    return WebServePlan(
        api_command=(
            sys.executable,
            "-m",
            "uvicorn",
            "doc2dic.server.app:app",
            "--host",
            API_HOST,
            "--port",
            str(API_PORT),
        ),
        api_cwd=config.project_root,
        web_command=(
            npm_command,
            "run",
            "dev",
            "--",
            "--host",
            WEB_HOST,
            "--port",
            str(config.web_port),
        ),
        web_cwd=web_cwd,
    )


def wait_for_first_exit(
    first_process: subprocess.Popen[bytes],
    second_process: subprocess.Popen[bytes],
) -> int:
    """Return when either managed process exits."""
    while True:
        first_code = first_process.poll()
        if first_code is not None:
            return first_code
        second_code = second_process.poll()
        if second_code is not None:
            return second_code
        time.sleep(PROCESS_POLL_SECONDS)


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate a still-running child process."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        _ = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        _ = process.wait(timeout=5)
