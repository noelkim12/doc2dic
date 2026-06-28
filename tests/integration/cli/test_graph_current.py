import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from tests.unit.services.test_graph_projection_service import seed_graph_fixture
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.storage import open_database
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3


def test_graph_current_when_json_requested_outputs_contract_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        seed_graph_fixture(connection)

    result = runner.invoke(app, ["graph", "current", "--json"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    body = cast("dict[str, object]", json.loads(result.output))
    assert [node["id"] for node in cast("list[dict[str, str]]", body["nodes"])] == [
        "concept_combat_stamina",
        "concept_dodge_roll",
        "concept_entry_stamina",
    ]
    edge_relations = [
        edge["relation"] for edge in cast("list[dict[str, str]]", body["edges"])
    ]
    assert edge_relations == [
        "alias_of",
        "contradicts",
        "depends_on",
        "derives_from",
        "value_of",
    ]
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select count(*) as count from graph_snapshots",
            ).fetchone(),
        )
    assert int_cell(require_row(row), "count") == 1
