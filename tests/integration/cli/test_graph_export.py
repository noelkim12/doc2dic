import json
from pathlib import Path
from typing import cast

import pytest
from tests.unit.services.test_graph_projection_service import seed_graph_fixture
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.storage import open_database


def test_graph_export_when_graphify_runtime_missing_still_writes_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    init_result = runner.invoke(app, ["init"])
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        seed_graph_fixture(connection)

    result = runner.invoke(app, ["graph", "export", "--format", "graphify"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Graphify runtime: unavailable" in result.output
    assert "graphify executable not found on PATH" in result.output
    snapshot_dirs = sorted((tmp_path / ".doc2dic" / "graph_snapshots").iterdir())
    assert len(snapshot_dirs) == 1
    projection_path = snapshot_dirs[0] / "graphify_projection.json"
    projection = cast("dict[str, object]", json.loads(projection_path.read_text()))
    assert [
        document["path"]
        for document in cast("list[dict[str, str]]", projection["documents"])
    ] == [
        "glossary_export/concepts/concept_combat_stamina.md",
        "glossary_export/concepts/concept_dodge_roll.md",
        "glossary_export/concepts/concept_entry_stamina.md",
    ]
    assert (
        snapshot_dirs[0]
        / "glossary_export"
        / "concepts"
        / "concept_combat_stamina.md"
    ).exists()
