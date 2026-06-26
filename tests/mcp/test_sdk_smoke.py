import sys
from collections.abc import Callable

import pytest

from doc2dic.mcp.sdk_compat import (
    McpSdkUnavailableError,
    build_sdk_smoke_server,
    call_sdk_smoke_tool,
    register_sdk_smoke_tool,
    server_supports_stdio,
)


def test_registers_string_tool_without_running_stdio() -> None:
    # Given: a tiny SDK smoke server with no long-lived transport started.
    server = build_sdk_smoke_server()
    register_sdk_smoke_tool(server)

    # When: the registered smoke tool is invoked in-process through the SDK.
    result = call_sdk_smoke_tool(server)

    # Then: the tool returns the expected string and the selected server can run stdio.
    assert result == "doc2dic-mcp-smoke-ok"
    assert server_supports_stdio(server)


def test_missing_mcp_sdk_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the SDK import path is unavailable in a controlled test seam.
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", None)

    # When / Then: callers get an actionable dependency message.
    with pytest.raises(McpSdkUnavailableError, match="Install the 'mcp' package"):
        _ = build_sdk_smoke_server()


def test_register_function_uses_sdk_tool_decorator() -> None:
    # Given: a tiny fake that records whether the SDK tool decorator is used.
    calls: list[str] = []

    class FakeServer:
        def tool(
            self,
            *,
            name: str,
        ) -> Callable[[Callable[[], str]], Callable[[], str]]:
            calls.append(name)

            def decorate(func: Callable[[], str]) -> Callable[[], str]:
                return func

            return decorate

    # When: the smoke tool is registered.
    register_sdk_smoke_tool(FakeServer())

    # Then: registration went through the SDK-style tool decorator.
    assert calls == ["doc2dic_sdk_smoke"]
