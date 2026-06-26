"""Build agent-ready terminology exploration context from search rows."""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from doc2dic.context.cards import (
    DEFAULT_EXPLORE_CONTEXT_LIMITS,
    EvidenceCard,
    ExploreContextLimits,
)
from doc2dic.context.markdown import (
    action_lines,
    apply_output_budget,
    compact,
    concept_lines,
    evidence_lines,
    graph_lines,
    inline,
    issue_lines,
    summary_lines,
    truncate,
)
from doc2dic.context.repository import (
    load_concept_cards,
    load_evidence_cards,
    load_index_status,
    load_issue_cards,
)
from doc2dic.storage.repositories.search import SearchIndexRepository
from doc2dic.storage.repositories.search_rows import (
    SearchConceptRow,
    SearchDocumentRow,
    SearchEvidenceRow,
    SearchIssueRow,
    SearchResults,
)
from doc2dic.sync import freshness_report, stale_banner_lines


def build_explore_context(
    query: str,
    *,
    connection: sqlite3.Connection,
    project_root: Path | None = None,
    limits: ExploreContextLimits = DEFAULT_EXPLORE_CONTEXT_LIMITS,
) -> str:
    """Build compact Markdown context for terminology exploration."""
    capped_query = _searchable_query(query, limits.max_query_chars)
    display_query = capped_query
    results = _search_results(connection, capped_query, _search_limit(limits))
    lines = [
        "# doc2dic terminology context",
        "",
        "## Project/index status",
        f"- Query: `{inline(display_query)}`",
        f"- Search index: {load_index_status(connection)}",
    ]
    if project_root is not None:
        lines.extend(stale_banner_lines(freshness_report(connection, project_root)))
    lines.append("")
    if _has_no_terms(display_query):
        lines.extend([
            "## Summary",
            "No searchable query terms were provided.",
            "",
            "## Suggested actions",
            "- Provide one or more Korean term surfaces or concept names.",
        ])
        return apply_output_budget(lines, limits.max_output_chars)

    concepts = load_concept_cards(connection, results, limits.max_concepts)
    issues = load_issue_cards(connection, results, limits.max_issues)
    evidence = load_evidence_cards(
        connection,
        results,
        limits.max_evidence,
        limits.max_evidence_quote_chars,
    )
    lines.extend(summary_lines(results, concepts, issues, evidence))
    lines.extend(evidence_lines(evidence))
    lines.extend(concept_lines(concepts))
    lines.extend(issue_lines(issues))
    lines.extend(graph_lines(concepts, issues))
    lines.extend(action_lines(results))
    budget_notes = _budget_notes(display_query != compact(query), evidence)
    if budget_notes:
        lines.extend(["", "## Budget note", *budget_notes])
    return apply_output_budget(lines, limits.max_output_chars)


def _search_limit(limits: ExploreContextLimits) -> int:
    return max(limits.max_concepts, limits.max_issues, limits.max_evidence, 1)


def _searchable_query(query: str, max_chars: int) -> str:
    terms: list[str] = []
    for term in compact(query).split():
        if term not in terms and any(char.isalnum() for char in term):
            terms.append(term)
        if len(" ".join(terms)) >= max_chars:
            break
    return truncate(" ".join(terms), max_chars)


def _search_results(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
) -> SearchResults:
    repository = SearchIndexRepository(connection)
    first = repository.search(query, limit=limit)
    per_term = tuple(repository.search(term, limit=limit) for term in query.split())
    merged = _merge_results((first, *per_term))
    return SearchResults(
        concepts=merged.concepts[:limit],
        documents=merged.documents[:limit],
        issues=merged.issues[:limit],
        evidence=merged.evidence[:limit],
    )


def _merge_results(results: Sequence[SearchResults]) -> SearchResults:
    concepts: list[SearchConceptRow] = []
    documents: list[SearchDocumentRow] = []
    issues: list[SearchIssueRow] = []
    evidence: list[SearchEvidenceRow] = []
    concept_ids: set[str] = set()
    document_ids: set[tuple[str, str | None]] = set()
    issue_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for result in results:
        for row in result.concepts:
            if row.concept_id not in concept_ids:
                concept_ids.add(row.concept_id)
                concepts.append(row)
        for row in result.documents:
            document_key = (row.document_id, row.chunk_id)
            if document_key not in document_ids:
                document_ids.add(document_key)
                documents.append(row)
        for row in result.issues:
            if row.issue_id not in issue_ids:
                issue_ids.add(row.issue_id)
                issues.append(row)
        for row in result.evidence:
            if row.evidence_id not in evidence_ids:
                evidence_ids.add(row.evidence_id)
                evidence.append(row)
    return SearchResults(
        tuple(concepts),
        tuple(documents),
        tuple(issues),
        tuple(evidence),
    )


def _has_no_terms(query: str) -> bool:
    return not any(char.isalnum() for char in query)


def _budget_notes(
    query_was_truncated: bool,
    evidence: Sequence[EvidenceCard],
) -> list[str]:
    notes: list[str] = []
    if query_was_truncated:
        notes.append("- Query was truncated before search to respect input caps.")
    if any(card.quote_was_truncated for card in evidence):
        notes.append(
            "- One or more evidence quotes were truncated to fit context budgets.",
        )
    return notes
