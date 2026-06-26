"""Success-shaped guidance text for expected MCP tool conditions."""

from pathlib import Path


def missing_project_guidance(project_root: Path) -> str:
    """Return normal text for a project without doc2dic storage."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"Project `{project_root}` is not initialized for doc2dic.",
            "",
            "## What this means",
            "- `.doc2dic/glossary.sqlite3` was not found.",
            "- Use repo search/read tools for this request.",
            "- Ask the user before running `doc2dic init` or changing glossary data.",
        ),
    )


def invalid_project_guidance(project_path: str) -> str:
    """Return normal text for an unreadable or invalid project path."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"doc2dic could not inspect project path `{project_path}`.",
            "",
            "## What this means",
            "- The path is missing, invalid, or inaccessible from this process.",
            "- Use repo search/read tools and ask the user for the intended root.",
        ),
    )


def degraded_index_guidance(project_root: Path) -> str:
    """Return normal text for an unreadable, old, or degraded database."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            (
                f"Project `{project_root}` has doc2dic storage, but the search "
                "index is not ready."
            ),
            "",
            "## What this means",
            (
                "- The database may be missing MCP/search migration tables or "
                "may be degraded."
            ),
            "- Use repo search/read tools for now.",
            "- Ask the user before rebuilding indexes or mutating glossary data.",
        ),
    )


def status_guidance(project_root: Path, db_path: Path) -> str:
    """Return concise status text for the hidden status tool."""
    state = "initialized" if db_path.exists() else "not initialized"
    return "\n".join(
        (
            "# doc2dic MCP status",
            "",
            f"- Project: `{project_root}`",
            f"- Glossary DB: `{db_path}`",
            f"- State: {state}",
        ),
    )
