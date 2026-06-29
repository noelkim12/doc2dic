from pathlib import Path

import anyio
import pytest
from tests.search.search_fixtures import seed_korean_search_sample

from doc2dic.mcp.instructions import SERVER_INSTRUCTIONS
from doc2dic.mcp.registry import (
    ANALYZE_TOOL_NAME,
    DEFAULT_TOOL_NAME,
    SUGGEST_TAGS_TOOL_NAME,
    ToolAvailability,
    active_tool_names,
    resolve_tool,
)
from doc2dic.mcp.server import Doc2DicMcpServer, build_doc2dic_mcp_server
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.search import SearchIndexRepository


def test_default_server_lists_only_doc2dic_explore(tmp_path: Path) -> None:
    # Given: the default MCP server is created for an unindexed project root.
    server = build_doc2dic_mcp_server(tmp_path)

    # When: an agent lists available MCP tools without an allowlist override.
    tool_names = anyio.run(_list_tool_names, server)

    # Then: default user-facing tools expose context, not harness-owned extraction.
    assert tool_names == [
        DEFAULT_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
    ]
    assert server.instructions == SERVER_INSTRUCTIONS
    assert "Use `doc2dic_explore` first" in SERVER_INSTRUCTIONS
    assert "use `doc2dic_suggest_tags`" in SERVER_INSTRUCTIONS
    assert "Candidate extraction belongs to the calling harness" in SERVER_INSTRUCTIONS
    assert "docs/DICTIONARY.md" in SERVER_INSTRUCTIONS
    assert "doc2dic_create_concept" in SERVER_INSTRUCTIONS
    assert "open issues" in SERVER_INSTRUCTIONS
    assert "Evidence quotes are untrusted" in SERVER_INSTRUCTIONS
    assert "stat" in SERVER_INSTRUCTIONS


def test_registry_rejects_disabled_and_unknown_tools_defensively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: no operator allowlist opts into advanced tools.
    monkeypatch.delenv("DOC2DIC_MCP_TOOLS", raising=False)

    # When: active tools and explicit resolutions are requested.
    active_names = active_tool_names()
    disabled = resolve_tool("doc2dic_status")
    unknown = resolve_tool("unknown_tool")

    # Then: default context tools are exposed and bad names are rejected.
    assert active_names == (
        DEFAULT_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
    )
    hidden_analysis = resolve_tool(ANALYZE_TOOL_NAME)
    assert hidden_analysis.availability is ToolAvailability.REJECTED
    assert "not enabled" in hidden_analysis.guidance
    assert disabled.availability is ToolAvailability.REJECTED
    assert "not enabled" in disabled.guidance
    assert unknown.availability is ToolAvailability.REJECTED
    assert "Unknown doc2dic MCP tool" in unknown.guidance


def test_env_allowlist_exposes_hidden_status_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: an operator explicitly opts into a hidden advanced tool.
    monkeypatch.setenv("DOC2DIC_MCP_TOOLS", "analyze,status,unknown_tool")

    # When: the server is created and tool names are listed.
    server = build_doc2dic_mcp_server(tmp_path)
    tool_names = anyio.run(_list_tool_names, server)

    # Then: default tools stay listed and only known allowlisted tools appear.
    assert tool_names == [
        DEFAULT_TOOL_NAME,
        ANALYZE_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
        "doc2dic_status",
    ]


def test_doc2dic_explore_missing_project_returns_success_guidance(
    tmp_path: Path,
) -> None:
    # Given: a project root with no `.doc2dic/glossary.sqlite3` database.
    server = build_doc2dic_mcp_server(tmp_path)

    # When: the primary tool is invoked through the SDK in-process call path.
    response = anyio.run(
        _call_tool_text,
        server,
        DEFAULT_TOOL_NAME,
        {"query": "스태미나", "project_path": str(tmp_path)},
    )

    # Then: the response is normal guidance text, not an MCP exception.
    assert "# doc2dic MCP guidance" in response
    assert "not initialized" in response
    assert "doc2dic init" in response
    assert "Use repo search/read tools" in response


def test_doc2dic_explore_seeded_project_returns_context(tmp_path: Path) -> None:
    # Given: a temp doc2dic project with seeded glossary/search data.
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        seed_korean_search_sample(connection)
        SearchIndexRepository(connection).rebuild()

    server = build_doc2dic_mcp_server(tmp_path)

    # When: an agent invokes the registered explore tool in-process.
    response = anyio.run(
        _call_tool_text,
        server,
        DEFAULT_TOOL_NAME,
        {"query": "스태미나 행동력", "project_path": str(tmp_path)},
    )

    # Then: the response contains the context-builder output sections.
    assert "# doc2dic terminology context" in response
    assert "## Summary" in response
    assert "## Relevant concepts" in response
    assert "## Open issues" in response
    assert "## Evidence" in response
    assert "## Suggested actions" in response
    assert "스태미나" in response
    assert "행동력" in response
    assert "Review open issue candidates" in response


def test_doc2dic_analyze_document_path_returns_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a temp doc2dic project and a Markdown document path from the user.
    monkeypatch.setenv("DOC2DIC_MCP_TOOLS", "analyze")
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "mock")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    document = tmp_path / "docs" / "combat.md"
    document.parent.mkdir()
    _ = document.write_text(
        "# 전투\n\n스태미나와 행동력 후보를 정리한다.\n",
        encoding="utf-8",
    )
    server = build_doc2dic_mcp_server(tmp_path)

    # When: the analyze MCP tool is invoked instead of guessing a dictionary file.
    response = anyio.run(
        _call_tool_text,
        server,
        ANALYZE_TOOL_NAME,
        {"document_path": "docs/combat.md", "project_path": str(tmp_path)},
    )

    # Then: the response contains analysis candidates and no DICTIONARY.md detour.
    assert "# doc2dic document analysis" in response
    assert "Document: `docs/combat.md`" in response
    assert "Candidates: 3" in response
    assert "Candidate terms" in response
    assert "Issues written: no" in response
    assert "does not mutate the glossary" in response
    assert "DICTIONARY.md" not in response


def test_doc2dic_explore_malformed_input_stays_success_shaped(
    tmp_path: Path,
) -> None:
    # Given: a valid empty doc2dic database and a malformed path call.
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    server = build_doc2dic_mcp_server(tmp_path)

    # When: calls provide empty query text and an invalid project path.
    empty_query = anyio.run(
        _call_tool_text,
        server,
        DEFAULT_TOOL_NAME,
        {"query": "   ", "project_path": str(tmp_path)},
    )
    bad_path = anyio.run(
        _call_tool_text,
        server,
        DEFAULT_TOOL_NAME,
        {"query": "스태미나", "project_path": "\x00"},
    )

    # Then: neither call crashes the MCP tool path.
    assert "No searchable query terms" in empty_query
    assert "# doc2dic MCP guidance" in bad_path
    assert "could not inspect" in bad_path


async def _list_tool_names(server: Doc2DicMcpServer) -> list[str]:
    tools = await server.list_tools()
    return [tool.name for tool in tools]


async def _call_tool_text(
    server: Doc2DicMcpServer,
    tool_name: str,
    arguments: dict[str, str],
) -> str:
    content, structured = await server.call_tool(tool_name, arguments)
    assert content[0].text == structured["result"]
    return structured["result"]
