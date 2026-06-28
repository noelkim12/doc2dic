from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.storage.connection import open_database
from doc2dic.storage.repositories import SettingsRepository

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    import pytest

VOYAGE_SECRET_VALUE = "sk-test-doc2dic-voyage-secret"  # noqa: S105


def test_config_embedding_prompt_saves_auth_file_without_leaking_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    auth_file = tmp_path / "global-config" / "doc2dic" / "auth.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_file))
    init_result = runner.invoke(app, ["init"])

    result = runner.invoke(
        app,
        ["config", "embedding"],
        input=f"voyage\nvoyage-3-large\n{VOYAGE_SECRET_VALUE}\n",
    )

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Embedding provider: voyage" in result.output
    assert "Embedding model: voyage-3-large" in result.output
    assert "API key: saved" in result.output
    assert VOYAGE_SECRET_VALUE not in result.output
    assert auth_file.exists()
    assert VOYAGE_SECRET_VALUE in auth_file.read_text(encoding="utf-8")
    if os.name != "nt":
        assert stat.S_IMODE(auth_file.stat().st_mode) == 0o600

    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        settings = SettingsRepository(connection)
        assert settings.get_value("embedding.provider") == "voyage"
        assert settings.get_value("embedding.model") == "voyage-3-large"
        rows: list[sqlite3.Row] = connection.execute(
            "select key, value from settings",
        ).fetchall()
        assert all(
            VOYAGE_SECRET_VALUE not in f"{row['key']}={row['value']}"
            for row in rows
        )


def test_config_embedding_use_voyage_defaults_to_current_voyage_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    auth_file = tmp_path / "auth.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_file))
    init_result = runner.invoke(app, ["init"])

    result = runner.invoke(app, ["config", "embedding", "use", "voyage"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Embedding provider: voyage" in result.output
    assert "Embedding model: voyage-4-large" in result.output
    assert "API key: unchanged" in result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        settings = SettingsRepository(connection)
        assert settings.get_value("embedding.provider") == "voyage"
        assert settings.get_value("embedding.model") == "voyage-4-large"


def test_config_embedding_doctor_when_key_saved_redacts_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    auth_file = tmp_path / "auth.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_file))
    init_result = runner.invoke(app, ["init"])
    configure_result = runner.invoke(
        app,
        ["config", "embedding"],
        input=f"voyage\nvoyage-3-large\n{VOYAGE_SECRET_VALUE}\n",
    )

    doctor_result = runner.invoke(app, ["config", "embedding", "doctor"])
    show_result = runner.invoke(app, ["config", "show"])

    assert init_result.exit_code == 0
    assert configure_result.exit_code == 0
    assert doctor_result.exit_code == 0
    assert show_result.exit_code == 0
    assert "Embedding provider: voyage" in doctor_result.output
    assert "Embedding model: voyage-3-large" in doctor_result.output
    assert "API key stored: yes" in doctor_result.output
    assert str(auth_file) in doctor_result.output
    assert VOYAGE_SECRET_VALUE not in configure_result.output
    assert VOYAGE_SECRET_VALUE not in doctor_result.output
    assert VOYAGE_SECRET_VALUE not in show_result.output


def test_config_get_set_remain_available_at_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])

    set_result = runner.invoke(app, ["config", "set", "language", "ko"])
    get_result = runner.invoke(app, ["config", "get", "language"])

    assert init_result.exit_code == 0
    assert set_result.exit_code == 0
    assert "language=ko" in set_result.output
    assert get_result.exit_code == 0
    assert get_result.output.strip() == "ko"
