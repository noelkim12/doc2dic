"""Local opencode installer for the doc2dic MCP server."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, cast

if TYPE_CHECKING:
    from pathlib import Path

CONFIG_SCHEMA: Final = "https://opencode.ai/config.json"
SERVER_NAME: Final = "doc2dic"
TOOLS_ENV: Final = "DOC2DIC_MCP_TOOLS"
CATCHUP_TIMEOUT_ENV: Final = "DOC2DIC_CATCHUP_GATE_TIMEOUT_MS"
CATCHUP_TIMEOUT_MS: Final = "3000"

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
type InstallAction = Literal["created", "updated", "unchanged"]
type UninstallAction = Literal["removed", "not-found"]


@dataclass(frozen=True, slots=True)
class InstallerResult:
    """Result of a local opencode config mutation."""

    config_path: Path
    action: InstallAction | UninstallAction
    backup_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ReadConfig:
    """Parsed opencode config plus rewrite safety metadata."""

    config: JsonObject
    needs_backup: bool


@dataclass(frozen=True, slots=True)
class NormalizedJsonc:
    """JSONC text normalized enough for Python's JSON parser."""

    text: str
    had_lossy_syntax: bool


def install_local_opencode(project_root: Path, package_root: Path) -> InstallerResult:
    """Create or update the local `mcp.doc2dic` opencode entry."""
    config_path = local_config_path(project_root)
    existed = config_path.exists()
    read_config = read_jsonc_config(config_path)
    config = dict(read_config.config)
    if config.get("$schema") != CONFIG_SCHEMA:
        config["$schema"] = CONFIG_SCHEMA

    mcp = _json_object_value(config.get("mcp"))
    desired_entry = _doc2dic_entry(project_root, package_root)
    if mcp.get(SERVER_NAME) == desired_entry and config.get("mcp") == mcp:
        return InstallerResult(config_path=config_path, action="unchanged")

    mcp[SERVER_NAME] = desired_entry
    config["mcp"] = mcp
    backup_path = _backup_for_rewrite(config_path, read_config.needs_backup)
    _write_json(config_path, config)
    action: InstallAction = "updated" if existed else "created"
    return InstallerResult(
        config_path=config_path,
        action=action,
        backup_path=backup_path,
    )


def uninstall_local_opencode(project_root: Path) -> InstallerResult:
    """Remove only the local `mcp.doc2dic` opencode entry."""
    config_path = local_config_path(project_root)
    if not config_path.exists():
        return InstallerResult(config_path=config_path, action="not-found")

    read_config = read_jsonc_config(config_path)
    config = dict(read_config.config)
    mcp = _json_object_value(config.get("mcp"))
    if SERVER_NAME not in mcp:
        return InstallerResult(config_path=config_path, action="not-found")

    del mcp[SERVER_NAME]
    if mcp:
        config["mcp"] = mcp
    elif "mcp" in config:
        del config["mcp"]

    backup_path = _backup_for_rewrite(config_path, read_config.needs_backup)
    _write_json(config_path, config)
    return InstallerResult(
        config_path=config_path,
        action="removed",
        backup_path=backup_path,
    )


def local_config_path(project_root: Path) -> Path:
    """Choose the local opencode config path using opencode's preference order."""
    jsonc_path = project_root / "opencode.jsonc"
    json_path = project_root / "opencode.json"
    if jsonc_path.exists():
        return jsonc_path
    if json_path.exists():
        return json_path
    return jsonc_path


def read_jsonc_config(config_path: Path) -> ReadConfig:
    """Read an opencode JSON/JSONC object, backing up before lossy rewrites."""
    if not config_path.exists():
        return ReadConfig(config={}, needs_backup=False)

    raw_text = config_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        return ReadConfig(config={}, needs_backup=False)

    normalized = _normalize_jsonc(raw_text)
    try:
        parsed = cast("JsonValue", json.loads(normalized.text))
    except json.JSONDecodeError:
        return ReadConfig(config={}, needs_backup=True)
    if not isinstance(parsed, dict):
        return ReadConfig(config={}, needs_backup=True)
    return ReadConfig(config=parsed, needs_backup=normalized.had_lossy_syntax)


def _doc2dic_entry(project_root: Path, package_root: Path) -> JsonObject:
    return {
        "type": "local",
        "command": [
            "uv",
            "--directory",
            str(package_root.resolve()),
            "run",
            "doc2dic",
            "serve",
            "--mcp",
            "--path",
            str(project_root.resolve()),
        ],
        "enabled": True,
        "environment": {
            TOOLS_ENV: "explore",
            CATCHUP_TIMEOUT_ENV: CATCHUP_TIMEOUT_MS,
        },
    }


def _json_object_value(value: JsonValue | None) -> JsonObject:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _backup_for_rewrite(config_path: Path, needs_backup: bool) -> Path | None:
    if not needs_backup or not config_path.exists():
        return None
    backup_path = config_path.with_name(f"{config_path.name}.backup")
    _ = shutil.copy2(config_path, backup_path)
    return backup_path


def _write_json(config_path: Path, config: JsonObject) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(f"{config_path.name}.tmp")
    _ = temp_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    _ = temp_path.replace(config_path)


def _normalize_jsonc(raw_text: str) -> NormalizedJsonc:
    stripped, had_comments = _strip_jsonc_comments(raw_text)
    without_trailing_commas = re.sub(r",(?=\s*[}\]])", "", stripped)
    return NormalizedJsonc(
        text=without_trailing_commas,
        had_lossy_syntax=had_comments or stripped != without_trailing_commas,
    )


def _strip_jsonc_comments(raw_text: str) -> tuple[str, bool]:  # noqa: C901
    chars: list[str] = []
    index = 0
    in_string = False
    escaped = False
    had_comments = False
    while index < len(raw_text):
        char = raw_text[index]
        next_char = raw_text[index + 1] if index + 1 < len(raw_text) else ""
        if in_string:
            chars.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            chars.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            had_comments = True
            index += 2
            while index < len(raw_text) and raw_text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            had_comments = True
            index += 2
            while index + 1 < len(raw_text) and raw_text[index : index + 2] != "*/":
                if raw_text[index] in "\r\n":
                    chars.append(raw_text[index])
                index += 1
            index += 2
            continue
        chars.append(char)
        index += 1
    return "".join(chars), had_comments
