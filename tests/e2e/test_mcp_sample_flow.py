from __future__ import annotations

from shutil import copyfile
from typing import TYPE_CHECKING

import anyio
from tests.e2e.mvp_sample_support import ROOT, seed_sample_base_glossary
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.mcp.registry import DEFAULT_TOOL_NAME
from doc2dic.mcp.server import Doc2DicMcpServer, build_doc2dic_mcp_server
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.search import SearchIndexRepository

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_mcp_sample_flow_when_mock_providers_run_returns_conflict_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "mock")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    combat_doc = docs_dir / "combat_core.md"
    dungeon_doc = docs_dir / "dungeon_draft.md"
    _ = copyfile(ROOT / "samples" / "docs" / "combat_core.md", combat_doc)
    _ = copyfile(ROOT / "samples" / "docs" / "dungeon_draft.md", dungeon_doc)

    init_result = runner.invoke(app, ["init"])
    seed_sample_base_glossary(tmp_path)
    combat_check = runner.invoke(app, ["check", str(combat_doc.relative_to(tmp_path))])
    dungeon_analyze = runner.invoke(
        app,
        ["analyze", str(dungeon_doc.relative_to(tmp_path))],
    )
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        SearchIndexRepository(connection).rebuild()

    server = build_doc2dic_mcp_server(tmp_path)
    fresh_context = anyio.run(
        _call_tool_text,
        server,
        {"query": "스태미나 행동력", "project_path": str(tmp_path)},
    )

    assert init_result.exit_code == 0
    assert combat_check.exit_code == 0
    assert "Occurrences:" in combat_check.output
    assert dungeon_analyze.exit_code == 0
    assert "Provider: deterministic_mock" in dungeon_analyze.output
    assert "Issues written: yes" in dungeon_analyze.output
    assert len(fresh_context) <= 6000
    assert "Stale/degraded" not in fresh_context
    assert "# doc2dic terminology context" in fresh_context
    assert "## Evidence" in fresh_context
    assert "## Open issues" in fresh_context
    assert "## Suggested actions" in fresh_context
    assert "스태미나" in fresh_context
    assert "행동력" in fresh_context
    assert "던전 입장 자원" in fresh_context
    assert "same_term_different_meaning" in fresh_context
    assert (
        "Review open issue candidates before editing approved glossary facts"
        in fresh_context
    )
    assert "스태미나는 던전에 입장할 때 1 소모" in fresh_context

    _ = dungeon_doc.write_text(
        "# 던전 입장 규칙 초안\n\n행동력은 던전 입장에 소모된다.\n",
        encoding="utf-8",
    )
    stale_context = anyio.run(
        _call_tool_text,
        server,
        {"query": "스태미나 행동력", "project_path": str(tmp_path)},
    )
    assert "Stale/degraded" in stale_context
    assert "docs/dungeon_draft.md" in stale_context
    assert "content differs from stored hash" in stale_context


def test_mcp_sample_flow_when_index_is_missing_returns_success_guidance(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    server = build_doc2dic_mcp_server(tmp_path)

    guidance = anyio.run(
        _call_tool_text,
        server,
        {"query": "스태미나 행동력", "project_path": str(tmp_path)},
    )

    assert "# doc2dic terminology context" in guidance
    assert "metadata missing; search may be degraded or not rebuilt" in guidance
    assert "No indexed terminology matches were found" in guidance
    assert "Use repo search/read tools or ask a human to seed doc2dic data" in guidance


async def _call_tool_text(
    server: Doc2DicMcpServer,
    arguments: dict[str, str],
) -> str:
    content, structured = await server.call_tool(DEFAULT_TOOL_NAME, arguments)
    assert content[0].text == structured["result"]
    return structured["result"]
