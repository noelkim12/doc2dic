"""MCP server factory for doc2dic."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

from doc2dic.mcp.instructions import SERVER_INSTRUCTIONS, SERVER_NAME
from doc2dic.mcp.registry import DEFAULT_TOOL_NAME, STATUS_TOOL_NAME, active_tool_names
from doc2dic.mcp.tools import run_doc2dic_explore, run_doc2dic_status


class ListedTool(Protocol):
    """List-tools item shape used by doc2dic tests."""

    name: str


class ToolTextContent(Protocol):
    """Text content shape returned by FastMCP tool calls."""

    text: str


class ToolRegisteringServer(Protocol):
    """MCP server capability required for registering tools."""

    def tool(
        self,
        *,
        name: str,
        description: str,
    ) -> Callable[[Callable[..., str]], Callable[..., str]]:
        """Return an MCP tool decorator."""
        ...


class Doc2DicMcpServer(Protocol):
    """MCP server capabilities used by tests and CLI wiring."""

    instructions: str | None


    async def list_tools(self) -> list[ListedTool]:
        """List registered tools."""
        ...


    async def call_tool(
        self,
        name: str,
        arguments: dict[str, str],
    ) -> tuple[Sequence[ToolTextContent], dict[str, str]]:
        """Call a registered tool."""
        ...


    async def run_stdio_async(self) -> None:
        """Run the MCP server over stdio."""
        ...


def build_doc2dic_mcp_server(
    default_project_root: Path | None = None,
) -> Doc2DicMcpServer:
    """Build a FastMCP server without starting a transport."""
    from mcp.server.fastmcp import FastMCP  # noqa: PLC0415

    project_root = Path.cwd() if default_project_root is None else default_project_root
    server = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    _register_enabled_tools(server, project_root)
    return cast("Doc2DicMcpServer", cast("object", server))


def _register_enabled_tools(
    server: ToolRegisteringServer,
    default_project_root: Path,
) -> None:
    enabled_names = active_tool_names()
    if DEFAULT_TOOL_NAME in enabled_names:

        @server.tool(
            name=DEFAULT_TOOL_NAME,
            description=(
                "Build bounded terminology context from a local doc2dic project."
            ),
        )
        def doc2dic_explore(query: str, project_path: str | None = None) -> str:
            return run_doc2dic_explore(query, project_path or default_project_root)

        _ = doc2dic_explore

    if STATUS_TOOL_NAME in enabled_names:

        @server.tool(
            name=STATUS_TOOL_NAME,
            description=(
                "Hidden diagnostic status for an explicitly allowlisted project."
            ),
        )
        def doc2dic_status(project_path: str | None = None) -> str:
            return run_doc2dic_status(project_path or default_project_root)

        _ = doc2dic_status
