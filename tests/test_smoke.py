"""Smoke tests for the T1 scaffold."""

from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.server.app import create_app


def test_cli_help_lists_command_groups() -> None:
    """Given the root CLI, when help runs, then command groups are listed."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command_name in (
        "init",
        "status",
        "concept",
        "variant",
        "review",
        "check",
        "analyze",
        "graph",
        "serve",
    ):
        assert command_name in result.output


def test_fastapi_app_exposes_health_placeholder() -> None:
    """Given the app factory, when app is created, then health route is wired."""
    fastapi_app = create_app()

    assert "/api/health" in fastapi_app.openapi()["paths"]
