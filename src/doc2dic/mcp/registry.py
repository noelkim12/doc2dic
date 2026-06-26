"""Tool registry and allowlist handling for doc2dic MCP."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

DEFAULT_TOOL_NAME: Final = "doc2dic_explore"
STATUS_TOOL_NAME: Final = "doc2dic_status"
MCP_TOOLS_ENV: Final = "DOC2DIC_MCP_TOOLS"


class ToolAvailability(StrEnum):
    """Resolution state for a requested MCP tool."""

    AVAILABLE = "available"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Registered MCP tool metadata."""

    name: str
    description: str
    enabled_by_default: bool


@dataclass(frozen=True, slots=True)
class ToolResolution:
    """Defensive resolution result for a requested tool name."""

    name: str
    availability: ToolAvailability
    guidance: str


TOOL_DEFINITIONS: Final[Mapping[str, ToolDefinition]] = {
    DEFAULT_TOOL_NAME: ToolDefinition(
        name=DEFAULT_TOOL_NAME,
        description="Build bounded terminology context from a local doc2dic project.",
        enabled_by_default=True,
    ),
    STATUS_TOOL_NAME: ToolDefinition(
        name=STATUS_TOOL_NAME,
        description="Hidden diagnostic status for an explicitly allowlisted project.",
        enabled_by_default=False,
    ),
}

TOOL_ALIASES: Final[Mapping[str, str]] = {
    "explore": DEFAULT_TOOL_NAME,
    DEFAULT_TOOL_NAME: DEFAULT_TOOL_NAME,
    "status": STATUS_TOOL_NAME,
    STATUS_TOOL_NAME: STATUS_TOOL_NAME,
}


def active_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Return enabled tool definitions in stable listing order."""
    names = active_tool_names()
    return tuple(TOOL_DEFINITIONS[name] for name in names)


def active_tool_names() -> tuple[str, ...]:
    """Return default tools plus known allowlisted hidden tools."""
    allowed = _allowlisted_tool_names(os.environ.get(MCP_TOOLS_ENV))
    return tuple(
        definition.name
        for definition in TOOL_DEFINITIONS.values()
        if definition.enabled_by_default or definition.name in allowed
    )


def resolve_tool(name: str) -> ToolResolution:
    """Resolve a tool request without exposing unknown or disabled handlers."""
    canonical_name = TOOL_ALIASES.get(name, name)
    if canonical_name not in TOOL_DEFINITIONS:
        return ToolResolution(
            name=name,
            availability=ToolAvailability.REJECTED,
            guidance=f"Unknown doc2dic MCP tool `{name}`.",
        )
    if canonical_name not in active_tool_names():
        return ToolResolution(
            name=canonical_name,
            availability=ToolAvailability.REJECTED,
            guidance=(
                f"Tool `{canonical_name}` is known but not enabled. "
                f"Set {MCP_TOOLS_ENV} to opt into hidden tools."
            ),
        )
    return ToolResolution(
        name=canonical_name,
        availability=ToolAvailability.AVAILABLE,
        guidance="Tool is enabled.",
    )


def _allowlisted_tool_names(raw_value: str | None) -> frozenset[str]:
    if raw_value is None:
        return frozenset()
    names: set[str] = set()
    for raw_token in raw_value.replace(";", ",").split(","):
        token = raw_token.strip()
        canonical_name = TOOL_ALIASES.get(token)
        if canonical_name is not None:
            names.add(canonical_name)
    return frozenset(names)
