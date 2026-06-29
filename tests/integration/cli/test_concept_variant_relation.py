from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

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
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")

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
    concept_id = _created_id(add_result.output, "Created concept")
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _table_count(connection, "embeddings") == 1
        assert _table_count(connection, "embedding_vectors") == 1
    list_result = runner.invoke(app, ["concept", "list", "--tag", "combat"])
    show_result = runner.invoke(app, ["concept", "show", concept_id])
    edit_result = runner.invoke(
        app,
        ["concept", "edit", concept_id, "--definition", "Action budget."],
    )
    deprecate_result = runner.invoke(app, ["concept", "deprecate", concept_id])

    assert init_result.exit_code == 0
    assert add_result.exit_code == 0
    assert concept_id.startswith("concept_")
    assert list_result.exit_code == 0
    assert f"{concept_id}\tactive\tStamina" in list_result.output
    assert show_result.exit_code == 0
    assert "Primary term: Stamina" in show_result.output
    assert edit_result.exit_code == 0
    assert deprecate_result.exit_code == 0
    assert f"Deprecated concept: {concept_id}" in deprecate_result.output


def test_variant_and_relation_commands_when_targets_exist_create_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")

    init_result = runner.invoke(app, ["init"])
    source_result = runner.invoke(
        app,
        ["concept", "add", "Health", "--definition", "Hit points."],
    )
    source_id = _created_id(source_result.output, "Created concept")
    target_result = runner.invoke(
        app,
        ["concept", "add", "Damage", "--definition", "Health reduction."],
    )
    target_id = _created_id(target_result.output, "Created concept")

    variant_result = runner.invoke(
        app,
        ["variant", "add", source_id, "HP", "--type", "abbreviation"],
    )
    relation_result = runner.invoke(
        app,
        [
            "concept",
            "relation",
            "add",
            source_id,
            target_id,
            "--type",
            "related_to",
        ],
    )

    assert init_result.exit_code == 0
    assert source_result.exit_code == 0
    assert target_result.exit_code == 0
    assert variant_result.exit_code == 0
    assert _created_id(variant_result.output, "Created variant").startswith("variant_")
    assert relation_result.exit_code == 0
    assert "Created relation: relation_" in relation_result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _table_count(connection, "embeddings") == 2
        assert _table_count(connection, "embedding_vectors") == 2


def test_relation_command_when_same_source_and_target_returns_concise_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")

    init_result = runner.invoke(app, ["init"])
    concept_result = runner.invoke(
        app,
        ["concept", "add", "Health", "--definition", "Hit points."],
    )
    concept_id = _created_id(concept_result.output, "Created concept")

    relation_result = runner.invoke(
        app,
        ["concept", "relation", "add", concept_id, concept_id],
    )

    assert init_result.exit_code == 0
    assert concept_result.exit_code == 0
    assert relation_result.exit_code != 0
    assert "Error: relation target must differ from source" in relation_result.output
    assert "Traceback" not in relation_result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _relation_count(connection) == 0


def test_concept_add_with_physical_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")

    runner.invoke(app, ["init"])
    add = runner.invoke(
        app,
        [
            "concept", "add", "체력",
            "-d", "생명 수치",
            "--type", "stat",
            "--physical", "hp",
        ],
    )
    assert add.exit_code == 0
    concept_id = add.stdout.strip().split()[-1]

    show = runner.invoke(app, ["concept", "show", concept_id])
    assert "hp" in show.stdout


def _relation_count(connection: "sqlite3.Connection") -> int:
    return _table_count(connection, "concept_relations")


def _table_count(
    connection: "sqlite3.Connection",
    table_name: Literal["concept_relations", "embeddings", "embedding_vectors"],
) -> int:
    match table_name:
        case "concept_relations":
            sql = "select count(*) as count from concept_relations"
        case "embeddings":
            sql = "select count(*) as count from embeddings"
        case "embedding_vectors":
            sql = "select count(*) as count from embedding_vectors"
    row = cast(
        "sqlite3.Row | None",
        connection.execute(sql).fetchone(),
    )
    return int_cell(require_row(row), "count")


def _created_id(output: str, label: str) -> str:
    return output.removeprefix(f"{label}: ").strip()
