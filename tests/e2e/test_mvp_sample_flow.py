from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from tests.e2e.mvp_sample_support import (
    ROOT,
    assert_api_surfaces_are_contract_safe,
    assert_graph_contains_split_path,
    assert_graphify_export_without_runtime,
    assert_review_effects_persisted,
    open_issue_ids,
    seed_sample_base_glossary,
)
from typer.testing import CliRunner

from doc2dic.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_mvp_sample_flow_when_run_with_mock_providers_is_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "mock")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")

    init_result = runner.invoke(app, ["init"])
    seed_sample_base_glossary(tmp_path)

    combat_check = runner.invoke(
        app,
        ["check", str(ROOT / "samples" / "docs" / "combat_core.md")],
    )
    dungeon_analyze = runner.invoke(
        app,
        ["analyze", str(ROOT / "samples" / "docs" / "dungeon_draft.md")],
    )

    assert init_result.exit_code == 0
    assert combat_check.exit_code == 0
    assert "Occurrences:" in combat_check.output
    assert dungeon_analyze.exit_code == 0
    assert "Provider: deterministic_mock" in dungeon_analyze.output
    assert "Issues written: yes" in dungeon_analyze.output

    issue_ids = open_issue_ids(tmp_path)
    split_result = runner.invoke(
        app,
        [
            "review",
            "resolve-as-relation",
            issue_ids.same_term,
            "--expected-version",
            "0",
            "--idempotency-key",
            "t25-split-stamina",
            "--source-concept-id",
            "concept_combat_stamina",
            "--target-concept-id",
            "concept_entry_resource",
            "--relation-type",
            "contradicts",
        ],
    )
    alias_result = runner.invoke(
        app,
        [
            "review",
            "resolve-as-alias",
            issue_ids.same_meaning,
            "--expected-version",
            "0",
            "--idempotency-key",
            "t25-entry-fatigue-alias",
            "--concept-id",
            "concept_entry_resource",
            "--variant",
            "입장 피로도",
        ],
    )
    concept_list = runner.invoke(app, ["concept", "list"])
    graph_current = runner.invoke(app, ["graph", "current", "--json"])

    assert split_result.exit_code == 0
    assert f"Review action applied: {issue_ids.same_term}" in split_result.output
    assert alias_result.exit_code == 0
    assert f"Review action applied: {issue_ids.same_meaning}" in alias_result.output
    assert concept_list.exit_code == 0
    assert "concept_entry_resource\tactive\t던전 입장 자원" in concept_list.output
    assert graph_current.exit_code == 0

    graph_body = cast("dict[str, object]", json.loads(graph_current.output))
    assert_graph_contains_split_path(graph_body)
    assert_api_surfaces_are_contract_safe(tmp_path)

    monkeypatch.setenv("PATH", "")
    graph_export = runner.invoke(app, ["graph", "export", "--format", "graphify"])

    assert graph_export.exit_code == 0
    assert "Graphify runtime: unavailable" in graph_export.output
    assert_graphify_export_without_runtime(tmp_path)
    assert_review_effects_persisted(tmp_path)
