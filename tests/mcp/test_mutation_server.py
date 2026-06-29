from pathlib import Path

import anyio

from doc2dic.mcp.registry import active_tool_names
from doc2dic.mcp.server import Doc2DicMcpServer, build_doc2dic_mcp_server
from doc2dic.storage.migrations import migrate_database


def test_mutation_tools_are_default_on() -> None:
    names = active_tool_names()

    assert "doc2dic_create_concept" in names
    assert "doc2dic_update_concept" in names
    assert "doc2dic_delete_concept" in names


def test_create_concept_tool_round_trips_through_server(tmp_path: Path) -> None:
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    server = build_doc2dic_mcp_server(tmp_path)

    response = anyio.run(
        _call_tool_text,
        server,
        "doc2dic_create_concept",
        {
            "primary_term": "체력",
            "definition": "플레이어 생존 수치",
            "physical_name": "hp",
            "project_path": str(tmp_path),
        },
    )

    assert "# doc2dic concept created" in response
    assert "hp" in response


async def _call_tool_text(
    server: Doc2DicMcpServer,
    tool_name: str,
    arguments: dict[str, object],
) -> str:
    content, structured = await server.call_tool(tool_name, arguments)
    assert content[0].text == structured["result"]
    return structured["result"]
