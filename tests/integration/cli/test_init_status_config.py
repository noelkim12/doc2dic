from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.commands import check as check_command
from doc2dic.storage.migrations import LATEST_SCHEMA_VERSION

if TYPE_CHECKING:
    import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_init_when_run_in_empty_directory_creates_config_and_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / ".doc2dic" / "config.toml").exists()
    assert (tmp_path / ".doc2dic" / "glossary.sqlite3").exists()
    assert "Initialized doc2dic project" in result.output


def test_status_when_run_in_initialized_child_directory_discovers_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = tmp_path / "docs" / "nested"
    child.mkdir(parents=True)
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    monkeypatch.chdir(child)

    result = runner.invoke(app, ["status"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert f"Project root: {tmp_path}" in result.output
    assert "Database: ready" in result.output
    assert f"Schema version: {LATEST_SCHEMA_VERSION}" in result.output


def test_status_when_run_outside_project_returns_actionable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["status"])

    assert result.exit_code != 0
    assert "Run `doc2dic init`" in result.output


def test_status_config_when_setting_value_persists_to_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])

    set_result = runner.invoke(app, ["status", "config", "set", "language", "ko"])
    get_result = runner.invoke(app, ["status", "config", "get", "language"])

    assert init_result.exit_code == 0
    assert set_result.exit_code == 0
    assert "language=ko" in set_result.output
    assert get_result.exit_code == 0
    assert get_result.output.strip() == "ko"


def test_check_without_write_issues_remains_offline_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_command, "analyze_document", None)
    init_result = runner.invoke(app, ["init"])

    first_result = runner.invoke(
        app,
        ["check", str(ROOT / "samples" / "docs" / "dungeon_draft.md")],
    )
    second_result = runner.invoke(
        app,
        ["check", str(ROOT / "samples" / "docs" / "dungeon_draft.md")],
    )

    assert init_result.exit_code == 0
    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert first_result.output == second_result.output
    assert "Issues written: no" in first_result.output
    assert "Provider:" not in first_result.output


def test_write_issue_commands_when_voyage_key_missing_degrade_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    auth_file = tmp_path / "auth.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_file))
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    init_result = runner.invoke(app, ["init"])
    config_result = runner.invoke(
        app,
        ["config", "embedding", "use", "voyage", "--model", "voyage-test-model"],
    )

    analyze_result = runner.invoke(
        app,
        ["analyze", str(ROOT / "samples" / "docs" / "dungeon_draft.md")],
    )
    check_result = runner.invoke(
        app,
        [
            "check",
            str(ROOT / "samples" / "docs" / "dungeon_draft.md"),
            "--write-issues",
        ],
    )

    assert init_result.exit_code == 0
    assert config_result.exit_code == 0
    assert analyze_result.exit_code == 0
    assert check_result.exit_code == 0
    assert "Provider: deterministic_mock" in analyze_result.output
    assert "Vector candidates enabled: false" in analyze_result.output
    assert "Issues written: yes" in check_result.output
    assert "Voyage API key is not configured" not in analyze_result.output
