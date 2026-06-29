"""Tool handlers for the doc2dic MCP server."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from doc2dic.context import build_explore_context
from doc2dic.context.tag_suggestions import build_tag_suggestions
from doc2dic.mcp.guidance import (
    concept_not_found_guidance,
    degraded_index_guidance,
    delete_not_confirmed_guidance,
    duplicate_concept_guidance,
    invalid_mutation_input_guidance,
    invalid_project_guidance,
    missing_project_guidance,
    status_guidance,
)
from doc2dic.mcp.schemas import (
    AnalyzeToolInput,
    CreateConceptToolInput,
    DeleteConceptToolInput,
    ExploreToolInput,
    StatusToolInput,
    SuggestTagsToolInput,
    UpdateConceptToolInput,
)
from doc2dic.services.conflict_detector import analyze_document
from doc2dic.services.document_conflict_models import ConflictAnalysisResult
from doc2dic.services.document_parser import UnsupportedDocumentFormatError
from doc2dic.services.glossary_models import (
    CreateConceptInput,
    DuplicateGlossaryItemError,
    GlossaryItemNotFoundError,
    UpdateConceptInput,
)
from doc2dic.services.glossary_service import GlossaryService
from doc2dic.storage.connection import DB_DIR_NAME, DB_FILE_NAME, open_database

REVIEW_WORKFLOW_GUIDANCE: Final = "- Use the review workflow before adding aliases, forbidden terms, or concepts."  # noqa: E501


def run_doc2dic_explore(query: str, project_path: str | Path | None = None) -> str:
    """Return terminology context or success-shaped guidance for expected gaps."""
    try:
        parsed = ExploreToolInput(
            query=query,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            return build_explore_context(
                parsed.query,
                connection=connection,
                project_root=paths.root,
            )
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)


def run_doc2dic_analyze(
    document_path: str | Path,
    project_path: str | Path | None = None,
) -> str:
    """Run hidden legacy local analysis for one document."""
    try:
        parsed = AnalyzeToolInput(
            document_path=Path(document_path),
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
        resolved_document = _document_path(paths.root, parsed.document_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            result = analyze_document(
                connection,
                resolved_document,
                write_issues=False,
            )
    except UnsupportedDocumentFormatError as exc:
        return _unsupported_document_guidance(resolved_document, exc)
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(_analysis_lines(paths.root, resolved_document, result))


def run_doc2dic_suggest_tags(
    query: str,
    project_path: str | Path | None = None,
) -> str:
    """Return existing-tag suggestions for a proposed glossary term."""
    try:
        parsed = SuggestTagsToolInput(
            query=query,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            return build_tag_suggestions(parsed.query, connection=connection)
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)


def run_doc2dic_create_concept(  # noqa: PLR0913
    primary_term: str,
    definition: str,
    term_type: str = "unknown",
    tags: tuple[str, ...] | None = None,
    physical_name: str | None = None,
    source_document: str | None = None,
    project_path: str | Path | None = None,
) -> str:
    """Create a glossary concept and return a success summary or guidance."""
    try:
        parsed = CreateConceptToolInput(
            primary_term=primary_term,
            definition=definition,
            term_type=term_type,  # pyright: ignore[reportArgumentType]
            tags=tags or (),
            physical_name=physical_name,
            source_document=source_document,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            concept = GlossaryService(connection).create_concept(
                CreateConceptInput(
                    primary_term=parsed.primary_term,
                    definition=parsed.definition,
                    term_type=parsed.term_type,
                    tags=parsed.tags,
                    source_document=parsed.source_document,
                    physical_name=parsed.physical_name,
                ),
            )
    except DuplicateGlossaryItemError as error:
        return duplicate_concept_guidance(str(error))
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept created",
            "",
            f"- Concept: `{concept.id}`",
            f"- Primary term: {concept.primary_term}",
            f"- Physical name: {concept.physical_name or 'none'}",
            f"- Status: {concept.status.value}",
        ),
    )


def run_doc2dic_update_concept(  # noqa: PLR0911, PLR0913
    concept_id: str,
    primary_term: str | None = None,
    definition: str | None = None,
    term_type: str | None = None,
    status: str | None = None,
    tags: tuple[str, ...] | None = None,
    physical_name: str | None = None,
    source_document: str | None = None,
    project_path: str | Path | None = None,
) -> str:
    """Patch a glossary concept and return a success summary or guidance."""
    try:
        parsed = UpdateConceptToolInput(
            concept_id=concept_id,
            primary_term=primary_term,
            definition=definition,
            term_type=term_type,  # pyright: ignore[reportArgumentType]
            status=status,  # pyright: ignore[reportArgumentType]
            tags=tags,
            physical_name=physical_name,
            source_document=source_document,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            concept = GlossaryService(connection).update_concept(
                parsed.concept_id,
                UpdateConceptInput(
                    primary_term=parsed.primary_term,
                    definition=parsed.definition,
                    term_type=parsed.term_type,
                    status=parsed.status,
                    tags=parsed.tags,
                    source_document=parsed.source_document,
                    physical_name=parsed.physical_name,
                ),
            )
    except GlossaryItemNotFoundError:
        return concept_not_found_guidance(parsed.concept_id)
    except DuplicateGlossaryItemError as error:
        return duplicate_concept_guidance(str(error))
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept updated",
            "",
            f"- Concept: `{concept.id}`",
            f"- Primary term: {concept.primary_term}",
            f"- Physical name: {concept.physical_name or 'none'}",
            f"- Status: {concept.status.value}",
        ),
    )


def run_doc2dic_delete_concept(  # noqa: PLR0911
    concept_id: str,
    confirm: bool = False,
    project_path: str | Path | None = None,
) -> str:
    """Delete a glossary concept after confirmation, or return guidance."""
    try:
        parsed = DeleteConceptToolInput(
            concept_id=concept_id,
            confirm=confirm,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    if not parsed.confirm:
        return delete_not_confirmed_guidance(parsed.concept_id)
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            GlossaryService(connection).delete_concept(parsed.concept_id)
    except GlossaryItemNotFoundError:
        return concept_not_found_guidance(parsed.concept_id)
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept deleted",
            "",
            f"- Concept: `{parsed.concept_id}`",
            "- Cascade removed variants, tags, and relations.",
        ),
    )


def run_doc2dic_status(project_path: str | Path | None = None) -> str:
    """Return hidden diagnostic status for explicitly allowlisted operators."""
    try:
        parsed = StatusToolInput(
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
        paths = _project_paths(parsed.project_path)
    except (OSError, ValidationError, ValueError):
        return invalid_project_guidance(str(project_path))
    return status_guidance(paths.root, paths.db_path)


@dataclass(frozen=True, slots=True)
class _ProjectPaths:
    """Resolved project-local storage paths."""

    root: Path
    db_path: Path


def _project_paths(project_path: Path) -> _ProjectPaths:
    root = project_path.expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise OSError(project_path)
    return _ProjectPaths(root=root, db_path=root / DB_DIR_NAME / DB_FILE_NAME)


def _document_path(project_root: Path, document_path: Path) -> Path:
    if document_path.is_absolute():
        return document_path.resolve(strict=False)
    return (project_root / document_path).resolve(strict=False)


def _analysis_lines(
    project_root: Path,
    document_path: Path,
    result: ConflictAnalysisResult,
) -> tuple[str, ...]:
    relative_path = _display_path(project_root, document_path)
    lines = [
        "# doc2dic document analysis",
        "",
        f"- Project: `{project_root}`",
        f"- Document: `{relative_path}`",
        f"- Provider: {result.provider or 'none'}",
        f"- Candidates: {len(result.candidates)}",
        f"- Issues: {len(result.all_issues)}",
        "- Issues written: no",
        f"- Vector candidates enabled: {str(result.vector_candidates.enabled).lower()}",
        "",
        "## Candidate terms",
    ]
    if len(result.candidates) == 0:
        lines.append("- No candidate terms were produced.")
    for candidate in result.candidates:
        tags = ", ".join(candidate.tags) if candidate.tags else "none"
        heading = (
            f"- `{candidate.surface}` "
            f"({candidate.term_type.value}, confidence {candidate.confidence:.2f})"
        )
        lines.extend([
            heading,
            f"  - Definition: {candidate.definition}",
            f"  - Tags: {tags}",
        ])
    lines.extend([
        "",
        "## Review boundary",
        "- This tool does not mutate the glossary or approve terms automatically.",
        REVIEW_WORKFLOW_GUIDANCE,
    ])
    return tuple(lines)


def _display_path(project_root: Path, document_path: Path) -> str:
    try:
        return document_path.relative_to(project_root).as_posix()
    except ValueError:
        return document_path.as_posix()


def _unsupported_document_guidance(
    document_path: Path,
    error: UnsupportedDocumentFormatError,
) -> str:
    return "\n".join(
        (
            "# doc2dic document analysis",
            "",
            f"Document `{document_path}` is not supported for analysis.",
            "",
            "## What this means",
            f"- {error}",
            "- Provide a Markdown or TXT document path.",
        ),
    )
