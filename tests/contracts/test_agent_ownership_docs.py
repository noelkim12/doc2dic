from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / ".opencode" / "agents"
REQUIRED_AGENTS = frozenset(
    {
        "contract-freeze",
        "api-server",
        "storage",
        "glossary",
        "analysis",
        "review",
        "graph",
        "web",
        "qa",
        "docs-handoff",
    }
)
REQUIRED_SECTIONS = (
    "## Allowed paths",
    "## Forbidden paths",
    "## Test expectations",
    "## Handoff target",
)
ROOT_CLI = "src/doc2dic/cli.py"
GRAPHIFY_IMPORT_SERVICE = "src/doc2dic/services/graphify_import_service.py"
MCP_LAYER_ALLOWED_PATHS = (
    "src/doc2dic/mcp/**",
    "src/doc2dic/context/**",
    "src/doc2dic/sync/**",
    "src/doc2dic/installer/**",
    "tests/mcp/**",
    "tests/context/**",
    "tests/sync/**",
    "tests/installer/**",
    "tests/contracts/test_agent_ownership_docs.py",
    "docs/**",
    "handoff/**",
    ".omo/evidence/**",
)
MCP_LAYER_GUARDRAILS = (
    "doc2dic serve --mcp --path <project>",
    "install/uninstall wiring",
    "No `backend/`",
    "No `.doc2dic/doc2dic.db`",
    "No Graphify import ownership",
    "No broad root CLI or API ownership",
)
FORBIDDEN_CLI_GRANTS = (
    f"- `{ROOT_CLI}`",
    f"- {ROOT_CLI}",
    f"- `{ROOT_CLI}` after Wave 0",
)
FORBIDDEN_GRAPHIFY_IMPORT_GRANTS = (
    "graphify import",
    "graphify_import",
    "import service",
    "graphify_*.py",
)


def agent_docs() -> dict[str, str]:
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in AGENT_DIR.glob("*.md")
    }


def test_all_declared_agents_have_ownership_docs() -> None:
    docs = agent_docs()

    assert set(docs) == REQUIRED_AGENTS


def test_agent_docs_define_required_contract_sections() -> None:
    docs = agent_docs()

    for agent, content in docs.items():
        for section in REQUIRED_SECTIONS:
            assert section in content, f"{agent} missing {section}"
        assert f"handoff/{agent}.md" in content


def test_agent_docs_define_allowed_paths_for_each_agent() -> None:
    docs = agent_docs()

    for agent, content in docs.items():
        allowed = content.split("## Allowed paths", maxsplit=1)[1].split(
            "## Forbidden paths", maxsplit=1
        )[0]
        path_lines = [line for line in allowed.splitlines() if line.startswith("- ")]
        assert path_lines, f"{agent} has no allowed path entries"


def test_agent_docs_reject_root_cli_write_ownership_after_wave_0() -> None:
    docs = agent_docs()
    negative_fixture = "## Allowed paths\n\n- `src/doc2dic/cli.py`\n"

    assert grants_root_cli_ownership(negative_fixture)
    for agent, content in docs.items():
        assert not grants_root_cli_ownership(content), agent


def test_root_agents_doc_and_handoff_readme_encode_project_rules() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    handoff = (ROOT / "handoff" / "README.md").read_text(encoding="utf-8")

    for required in (
        "Root Wiring Gate",
        ROOT_CLI,
        "Don't hardcode external",
        "Don't add auto approval",
        "Handoff Format",
    ):
        assert required in agents
    for required in (
        "Task",
        "Scope",
        "Files changed",
        "Commands run",
        "Evidence path",
        "Risks",
        "Follow-up",
    ):
        assert required in handoff


def test_mcp_layer_ownership_and_guardrails_are_frozen() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs" / "opencode-workflow.md").read_text(encoding="utf-8")
    contract_text = f"{agents}\n{workflow}"

    for required in MCP_LAYER_ALLOWED_PATHS:
        assert required in contract_text
    for required in MCP_LAYER_GUARDRAILS:
        assert required in contract_text


def test_graph_agent_defers_graphify_observation_import() -> None:
    graph_doc = (AGENT_DIR / "graph.md").read_text(encoding="utf-8")
    root_doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    forbidden = graph_doc.split("## Forbidden paths", maxsplit=1)[1].split(
        "## Test expectations", maxsplit=1
    )[0]

    assert "Graphify observation import is deferred" in graph_doc
    assert "Graphify observation import is deferred post-MVP" in root_doc
    assert GRAPHIFY_IMPORT_SERVICE in forbidden
    assert not grants_graphify_import_ownership(graph_doc)


def test_graphify_import_ownership_fixture_is_rejected() -> None:
    negative_fixture = (
        "## Allowed paths\n\n"
        "- `src/doc2dic/services/graphify_import_service.py`\n\n"
        "## Forbidden paths\n\n"
        "- None\n\n"
        "## Test expectations\n\n"
        "- graphify import service tests\n\n"
        "## Handoff target\n"
    )

    assert grants_graphify_import_ownership(negative_fixture)


def grants_root_cli_ownership(content: str) -> bool:
    allowed_section = content.split("## Allowed paths", maxsplit=1)[1]
    allowed_section = allowed_section.split("## Forbidden paths", maxsplit=1)[0]
    return any(grant in allowed_section for grant in FORBIDDEN_CLI_GRANTS)


def grants_graphify_import_ownership(content: str) -> bool:
    allowed_section = content.split("## Allowed paths", maxsplit=1)[1]
    allowed_section = allowed_section.split("## Forbidden paths", maxsplit=1)[0]
    tests_section = content.split("## Test expectations", maxsplit=1)[1]
    tests_section = tests_section.split("## Handoff target", maxsplit=1)[0]
    grant_surface = f"{allowed_section}\n{tests_section}".lower()
    return any(grant in grant_surface for grant in FORBIDDEN_GRAPHIFY_IMPORT_GRANTS)
