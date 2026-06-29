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


def duplicate_concept_guidance(detail: str) -> str:
    """Return guidance for a duplicate term or physical name conflict."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"The mutation was rejected as a duplicate: {detail}.",
            "",
            "## What to do",
            "- Run `doc2dic_explore` to find the existing concept.",
            "- Pick a different term/physical name, or update the existing concept.",
        ),
    )


def concept_not_found_guidance(concept_id: str) -> str:
    """Return guidance for a missing concept id on update/delete."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"Concept `{concept_id}` was not found.",
            "",
            "## What to do",
            "- Run `doc2dic_explore` to confirm the concept id.",
        ),
    )


def invalid_mutation_input_guidance(detail: str) -> str:
    """Return guidance for input that failed schema validation."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"The request was rejected as invalid input: {detail}.",
            "",
            "## What to do",
            "- physical_name must match `^[A-Za-z_][A-Za-z0-9_]*$` (max 80).",
            "- primary_term: 1-160 chars; definition: 1-2000 chars.",
            "- term_type: mechanic, resource, state, action, stat,"
            " entity, rule, ui-label, lore, unknown.",
            "- status: active, deprecated, forbidden.",
        ),
    )


def delete_not_confirmed_guidance(concept_id: str) -> str:
    """Return guidance when a delete is requested without confirmation."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"Delete of `{concept_id}` was not performed.",
            "",
            "## What to do",
            "- This is a permanent cascade delete of variants, tags, and relations.",
            "- Re-call with `confirm=true` to proceed.",
        ),
    )
