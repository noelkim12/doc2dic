"""Search index repository over the v2 SQLite FTS layer."""

import sqlite3
from typing import Final, cast

from doc2dic.storage.repositories.search_rows import (
    SearchConceptRow,
    SearchDocumentRow,
    SearchEvidenceRow,
    SearchIssueRow,
    SearchResults,
)
from doc2dic.storage.repositories.search_sql import (
    concept_rebuild_sql,
    document_chunk_rebuild_sql,
    document_without_chunk_rebuild_sql,
    evidence_rebuild_sql,
    issue_rebuild_sql,
)
from doc2dic.storage.sqlite_rows import optional_text_cell, text_cell

MAX_SEARCH_LIMIT: Final = 25


class SearchIndexRepository:
    """Populate and query the v2 search layer from existing storage tables."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used by this repository."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def rebuild(self) -> None:
        """Rebuild FTS rows from current glossary, document, and issue tables."""
        with self._connection:
            _ = self._connection.execute("delete from concept_search_fts")
            _ = self._connection.execute("delete from document_search_fts")
            _ = self._connection.execute("delete from issue_search_fts")
            _ = self._connection.execute("delete from evidence_search_fts")
            _ = self._connection.execute(concept_rebuild_sql())
            _ = self._connection.execute(document_chunk_rebuild_sql())
            _ = self._connection.execute(document_without_chunk_rebuild_sql())
            _ = self._connection.execute(issue_rebuild_sql())
            _ = self._connection.execute(evidence_rebuild_sql())
            _ = self._connection.execute(
                """
                insert into search_index_metadata(key, value, updated_at)
                values ('last_rebuild_at', strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                        strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                on conflict(key) do update set
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
            )

    def search(self, query: str, *, limit: int = 10) -> SearchResults:
        """Return stable bounded search groups for a user query."""
        bounded_limit = _bounded_limit(limit)
        terms = _query_terms(query)
        fts_expression = _fts_expression(terms)
        if fts_expression is None or bounded_limit == 0:
            return SearchResults(concepts=(), documents=(), issues=(), evidence=())
        return SearchResults(
            concepts=self._search_concepts(fts_expression, bounded_limit),
            documents=self._search_documents(fts_expression, bounded_limit),
            issues=self._search_issues(fts_expression, bounded_limit),
            evidence=self._search_evidence(fts_expression, bounded_limit),
        )

    def _search_concepts(
        self,
        fts_expression: str,
        limit: int,
    ) -> tuple[SearchConceptRow, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select c.id as concept_id, c.primary_term, c.definition
                from concept_search_fts fts
                join concepts c on c.id = fts.concept_id
                where concept_search_fts match ?
                order by bm25(concept_search_fts), c.primary_term, c.id
                limit ?
                """,
                (fts_expression, limit),
            ).fetchall(),
        )
        return tuple(_concept_row(row) for row in rows)

    def _search_documents(
        self,
        fts_expression: str,
        limit: int,
    ) -> tuple[SearchDocumentRow, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select document_id, chunk_id, path, title, section_title
                from document_search_fts
                where document_search_fts match ?
                order by bm25(document_search_fts), path, title, document_id, chunk_id
                limit ?
                """,
                (fts_expression, limit),
            ).fetchall(),
        )
        return tuple(_document_row(row) for row in rows)

    def _search_issues(
        self,
        fts_expression: str,
        limit: int,
    ) -> tuple[SearchIssueRow, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select i.id as issue_id, i.surface, i.status,
                       i.candidate_concept_id, i.target_concept_id
                from issue_search_fts fts
                join term_issues i on i.id = fts.issue_id
                where issue_search_fts match ?
                order by bm25(issue_search_fts), i.created_at, i.id
                limit ?
                """,
                (fts_expression, limit),
            ).fetchall(),
        )
        return tuple(_issue_row(row) for row in rows)

    def _search_evidence(
        self,
        fts_expression: str,
        limit: int,
    ) -> tuple[SearchEvidenceRow, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select ie.id as evidence_id, ie.issue_id, ie.source_document_id,
                       ie.chunk_id, ie.quote
                from evidence_search_fts fts
                join issue_evidence ie on ie.id = fts.evidence_id
                join term_issues i on i.id = ie.issue_id
                where evidence_search_fts match ?
                order by bm25(evidence_search_fts), i.created_at, ie.id
                limit ?
                """,
                (fts_expression, limit),
            ).fetchall(),
        )
        return tuple(_evidence_row(row) for row in rows)


def _bounded_limit(limit: int) -> int:
    if limit < 1:
        return 0
    return min(limit, MAX_SEARCH_LIMIT)


def _query_terms(query: str) -> tuple[str, ...]:
    return tuple(
        term for term in query.split() if any(char.isalnum() for char in term)
    )


def _fts_expression(terms: tuple[str, ...]) -> str | None:
    if len(terms) == 0:
        return None
    return " ".join(_quote_fts_term(term) for term in terms)


def _quote_fts_term(term: str) -> str:
    escaped = term.replace('"', '""')
    return f'"{escaped}"'


def _concept_row(row: sqlite3.Row) -> SearchConceptRow:
    return SearchConceptRow(
        concept_id=text_cell(row, "concept_id"),
        primary_term=text_cell(row, "primary_term"),
        definition=text_cell(row, "definition"),
    )


def _document_row(row: sqlite3.Row) -> SearchDocumentRow:
    return SearchDocumentRow(
        document_id=text_cell(row, "document_id"),
        chunk_id=optional_text_cell(row, "chunk_id"),
        path=text_cell(row, "path"),
        title=text_cell(row, "title"),
        section_title=text_cell(row, "section_title"),
    )


def _issue_row(row: sqlite3.Row) -> SearchIssueRow:
    return SearchIssueRow(
        issue_id=text_cell(row, "issue_id"),
        surface=text_cell(row, "surface"),
        status=text_cell(row, "status"),
        candidate_concept_id=optional_text_cell(row, "candidate_concept_id"),
        target_concept_id=optional_text_cell(row, "target_concept_id"),
    )


def _evidence_row(row: sqlite3.Row) -> SearchEvidenceRow:
    return SearchEvidenceRow(
        evidence_id=text_cell(row, "evidence_id"),
        issue_id=text_cell(row, "issue_id"),
        source_document_id=text_cell(row, "source_document_id"),
        chunk_id=optional_text_cell(row, "chunk_id"),
        quote=text_cell(row, "quote"),
    )
