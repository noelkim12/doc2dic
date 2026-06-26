from pathlib import Path

import pytest
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.storage.migrations import LATEST_SCHEMA_VERSION


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
