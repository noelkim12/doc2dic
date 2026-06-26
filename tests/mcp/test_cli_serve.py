from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.commands import serve as serve_command
from doc2dic.mcp.server import ToolTextContent


@dataclass(frozen=True, slots=True)
class _FakeTool:
    name: str


@dataclass(slots=True)
class _FakeTextContent:
    text: str


class _FakeMcpServer:
    instructions: str | None = None

    def __init__(self, call_events: list[str]) -> None:
        self._call_events: list[str] = call_events

    async def list_tools(self) -> list[_FakeTool]:
        return [_FakeTool(name="doc2dic_explore")]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, str],
    ) -> tuple[Sequence[ToolTextContent], dict[str, str]]:
        _ = name
        _ = arguments
        return ([_FakeTextContent(text="ok")], {"result": "ok"})

    async def run_stdio_async(self) -> None:
        self._call_events.append("stdio")


def test_serve_help_exposes_mcp_and_path_options() -> None:
    # Given: the root CLI has the serve command registered.
    runner = CliRunner()

    # When: a user asks for serve help.
    result = runner.invoke(app, ["serve", "--help"])

    # Then: the MCP launch flags are visible.
    assert result.exit_code == 0
    assert "--mcp" in result.output
    assert "--path" in result.output


def test_serve_mcp_when_path_missing_returns_actionable_error(tmp_path: Path) -> None:
    # Given: a path argument points at no project directory.
    missing_path = tmp_path / "missing"
    runner = CliRunner()

    # When: MCP serving is requested for that path.
    result = runner.invoke(app, ["serve", "--mcp", "--path", str(missing_path)])

    # Then: the CLI exits quickly with a doc2dic-specific correction.
    assert result.exit_code == 1
    assert "Project path does not exist" in result.output
    assert "doc2dic serve --mcp --path" in result.output


def test_serve_mcp_launches_stdio_server_for_project_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a bounded fake server factory records the project root and stdio launch.
    runner = CliRunner()
    call_events: list[str] = []
    project_roots: list[Path] = []

    def build_fake_server(default_project_root: Path | None = None) -> _FakeMcpServer:
        assert default_project_root is not None
        project_roots.append(default_project_root)
        return _FakeMcpServer(call_events)

    monkeypatch.setattr(
        serve_command,
        "build_doc2dic_mcp_server",
        build_fake_server,
    )

    # When: the CLI launch path is invoked.
    result = runner.invoke(app, ["serve", "--mcp", "--path", str(tmp_path)])

    # Then: the command reaches the MCP stdio path without starting web hosting.
    assert result.exit_code == 0
    assert project_roots == [tmp_path.resolve()]
    assert call_events == ["stdio"]
