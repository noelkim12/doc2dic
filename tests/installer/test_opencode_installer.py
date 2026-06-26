"""Focused tests for local opencode installer config edits."""

import json
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.installer.opencode import (
    JsonObject,
    JsonValue,
    install_local_opencode,
    read_jsonc_config,
    uninstall_local_opencode,
)


def test_install_creates_greenfield_opencode_jsonc(tmp_path: Path) -> None:
    """Given no config, when installing locally, then doc2dic MCP is created."""
    package_root = tmp_path / "package"
    project_root = tmp_path / "project"
    package_root.mkdir()
    project_root.mkdir()

    result = install_local_opencode(project_root, package_root)

    config_path = project_root / "opencode.jsonc"
    config = _read_config(config_path)
    assert result.action == "created"
    assert config["$schema"] == "https://opencode.ai/config.json"
    assert _server(config, "doc2dic") == {
        "type": "local",
        "command": [
            "uv",
            "--directory",
            str(package_root),
            "run",
            "doc2dic",
            "serve",
            "--mcp",
            "--path",
            str(project_root),
        ],
        "enabled": True,
        "environment": {
            "DOC2DIC_MCP_TOOLS": "explore",
            "DOC2DIC_CATCHUP_GATE_TIMEOUT_MS": "3000",
        },
    }


def test_install_is_idempotent_and_preserves_sibling_mcp(tmp_path: Path) -> None:
    """Given sibling MCP config, when installing twice, then only doc2dic changes."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    config_path = tmp_path / "opencode.jsonc"
    _ = config_path.write_text(
        json.dumps(
            {
                "mcp": {
                    "codegraph": {
                        "type": "local",
                        "command": ["codegraph", "serve", "--mcp"],
                        "enabled": True,
                        "environment": {"SECRET_TOKEN": "kept"},
                    }
                },
                "references": {"codegraph-ref": {"path": "../codegraph"}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    first = install_local_opencode(tmp_path, package_root)
    second = install_local_opencode(tmp_path, package_root)

    config = _read_config(config_path)
    assert first.action == "updated"
    assert second.action == "unchanged"
    assert _server(config, "codegraph")["environment"] == {"SECRET_TOKEN": "kept"}
    assert config["references"] == {"codegraph-ref": {"path": "../codegraph"}}


def test_install_backs_up_jsonc_comments_before_rewrite(tmp_path: Path) -> None:
    """Given commented JSONC, when installing, then a backup precedes rewrite."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    config_path = tmp_path / "opencode.jsonc"
    _ = config_path.write_text(
        """
{
  // user comment that MVP rewrite cannot preserve
  "mcp": {
    "other": {"type": "local", "command": ["other"], "enabled": true}
  }
}
""".lstrip(),
        encoding="utf-8",
    )

    result = install_local_opencode(tmp_path, package_root)

    config = _read_config(config_path)
    assert result.backup_path == tmp_path / "opencode.jsonc.backup"
    backup_path = result.backup_path
    assert backup_path is not None
    assert backup_path.read_text(encoding="utf-8").startswith("{")
    assert _server(config, "other")["command"] == ["other"]
    assert "doc2dic" in _mcp(config)


def test_uninstall_removes_only_doc2dic(tmp_path: Path) -> None:
    """Given multiple MCP servers, when uninstalling, then siblings remain."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    _ = install_local_opencode(tmp_path, package_root)
    config_path = tmp_path / "opencode.jsonc"
    config = _read_config(config_path)
    _mcp(config)["other"] = {
        "type": "local",
        "command": ["other", "serve"],
        "enabled": True,
    }
    _ = config_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )

    result = uninstall_local_opencode(tmp_path)

    updated = _read_config(config_path)
    assert result.action == "removed"
    assert "doc2dic" not in _mcp(updated)
    assert _server(updated, "other")["command"] == ["other", "serve"]


def test_cli_install_and_uninstall_local_opencode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Given the root CLI, when install/uninstall run, then config changes."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    install_result = runner.invoke(
        app,
        ["install", "--target", "opencode", "--local"],
    )
    config = _read_config(tmp_path / "opencode.jsonc")

    uninstall_result = runner.invoke(
        app,
        ["uninstall", "--target", "opencode", "--local"],
    )
    updated = _read_config(tmp_path / "opencode.jsonc")

    assert install_result.exit_code == 0
    assert "Installed doc2dic MCP" in install_result.output
    assert _command(config, "doc2dic")[0] == "uv"
    assert uninstall_result.exit_code == 0
    assert "Uninstalled doc2dic MCP" in uninstall_result.output
    assert "mcp" not in updated


def _read_config(config_path: Path) -> JsonObject:
    return read_jsonc_config(config_path).config


def _mcp(config: JsonObject) -> dict[str, JsonValue]:
    return cast("dict[str, JsonValue]", config["mcp"])


def _server(config: JsonObject, name: str) -> dict[str, JsonValue]:
    return cast("dict[str, JsonValue]", _mcp(config)[name])


def _command(config: JsonObject, name: str) -> list[JsonValue]:
    return cast("list[JsonValue]", _server(config, name)["command"])
