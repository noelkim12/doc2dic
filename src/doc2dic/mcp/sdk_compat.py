"""Small MCP SDK compatibility spike for feature-level smoke tests."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Final, Protocol, cast, override

import anyio

SMOKE_TOOL_NAME: Final = "doc2dic_sdk_smoke"
SMOKE_TOOL_RESPONSE: Final = "doc2dic-mcp-smoke-ok"
SMOKE_SERVER_NAME: Final = "doc2dic MCP SDK Smoke"


class ToolRegisteringServer(Protocol):
    """SDK server capability required to register a tool."""

    def tool(
        self,
        *,
        name: str,
    ) -> Callable[[Callable[[], str]], Callable[[], str]]:
        """Return the SDK tool decorator."""
        ...


class TextResultContent(Protocol):
    """Text content shape returned by the SDK tool call path."""

    text: str


class SdkSmokeServer(ToolRegisteringServer, Protocol):
    """SDK server capabilities proved by the smoke gate."""

    def run_stdio_async(self) -> Awaitable[None]:
        """Run the MCP server over stdio."""
        ...

    def call_tool(
        self,
        name: str,
        arguments: dict[str, str],
    ) -> Awaitable[tuple[Sequence[TextResultContent], dict[str, str]]]:
        """Invoke a registered tool in-process."""
        ...


class SdkSmokeServerFactory(Protocol):
    """Callable shape for the installed SDK server constructor."""

    def __call__(self, name: str) -> SdkSmokeServer:
        """Create an SDK server instance."""
        ...


class McpSdkUnavailableError(RuntimeError):
    """Raised when the MCP SDK dependency is missing."""

    package_name: Final[str] = "mcp"

    def __init__(self) -> None:
        """Initialize the actionable SDK dependency error."""
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        """Return an actionable installation message."""
        return (
            "Install the 'mcp' package to enable doc2dic MCP support "
            "(for this project: `uv sync` after pyproject metadata is updated)."
        )


def _load_server_class() -> SdkSmokeServerFactory:
    """Load the installed MCP server class selected by this spike."""
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: PLC0415
    except ModuleNotFoundError as error:
        raise McpSdkUnavailableError from error

    return cast("SdkSmokeServerFactory", cast("object", FastMCP))


def build_sdk_smoke_server() -> SdkSmokeServer:
    """Create a tiny FastMCP server without starting any transport."""
    server_class = _load_server_class()
    return server_class(SMOKE_SERVER_NAME)


def register_sdk_smoke_tool(server: ToolRegisteringServer) -> None:
    """Register a string-returning smoke tool through the SDK decorator."""

    @server.tool(name=SMOKE_TOOL_NAME)
    def smoke() -> str:
        return SMOKE_TOOL_RESPONSE

    _ = smoke


async def _call_sdk_smoke_tool(server: SdkSmokeServer) -> str:
    """Invoke the smoke tool through the SDK's in-process call path."""
    _content, structured_result = await server.call_tool(SMOKE_TOOL_NAME, {})
    return structured_result["result"]


def call_sdk_smoke_tool(server: SdkSmokeServer) -> str:
    """Synchronously invoke the smoke tool without launching stdio."""
    return anyio.run(_call_sdk_smoke_tool, server)


def server_supports_stdio(server: SdkSmokeServer) -> bool:
    """Report whether the selected SDK server exposes stdio runtime support."""
    return callable(server.run_stdio_async)
