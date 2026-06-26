from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.storage.connection import open_database
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3


def test_concept_commands_when_used_through_cli_manage_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    add_result = runner.invoke(
        app,
        [
            "concept",
            "add",
            "Stamina",
            "--definition",
            "Resource spent to enter dungeons.",
            "--type",
            "resource",
            "--tag",
            "combat",
        ],
    )
    list_result = runner.invoke(app, ["concept", "list", "--tag", "combat"])
    show_result = runner.invoke(app, ["concept", "show", "concept_stamina"])
    edit_result = runner.invoke(
        app,
        ["concept", "edit", "concept_stamina", "--definition", "Action budget."],
    )
    deprecate_result = runner.invoke(app, ["concept", "deprecate", "concept_stamina"])

    assert init_result.exit_code == 0
    assert add_result.exit_code == 0
    assert "Created concept: concept_stamina" in add_result.output
    assert list_result.exit_code == 0
    assert "concept_stamina\tactive\tStamina" in list_result.output
    assert show_result.exit_code == 0
    assert "Primary term: Stamina" in show_result.output
    assert edit_result.exit_code == 0
    assert deprecate_result.exit_code == 0
    assert "Deprecated concept: concept_stamina" in deprecate_result.output


def test_variant_and_relation_commands_when_targets_exist_create_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    source_result = runner.invoke(
        app,
        ["concept", "add", "Health", "--definition", "Hit points."],
    )
    target_result = runner.invoke(
        app,
        ["concept", "add", "Damage", "--definition", "Health reduction."],
    )

    variant_result = runner.invoke(
        app,
        ["variant", "add", "concept_health", "HP", "--type", "abbreviation"],
    )
    relation_result = runner.invoke(
        app,
        [
            "concept",
            "relation",
            "add",
            "concept_health",
            "concept_damage",
            "--type",
            "related_to",
        ],
    )

    assert init_result.exit_code == 0
    assert source_result.exit_code == 0
    assert target_result.exit_code == 0
    assert variant_result.exit_code == 0
    assert "Created variant: variant_hp" in variant_result.output
    assert relation_result.exit_code == 0
    assert "Created relation: relation_" in relation_result.output


def test_relation_command_when_same_source_and_target_returns_concise_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init"])
    concept_result = runner.invoke(
        app,
        ["concept", "add", "Health", "--definition", "Hit points."],
    )

    relation_result = runner.invoke(
        app,
        ["concept", "relation", "add", "concept_health", "concept_health"],
    )

    assert init_result.exit_code == 0
    assert concept_result.exit_code == 0
    assert relation_result.exit_code != 0
    assert "Error: relation target must differ from source" in relation_result.output
    assert "Traceback" not in relation_result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _relation_count(connection) == 0


def _relation_count(connection: "sqlite3.Connection") -> int:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select count(*) as count from concept_relations",
        ).fetchone(),
    )
    return int_cell(require_row(row), "count")
