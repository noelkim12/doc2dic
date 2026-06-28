"""SQLite readers for context cards."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from doc2dic.context.cards import ConceptCard, EvidenceCard, IssueCard, VariantGroups
from doc2dic.context.markdown import compact, truncate
from doc2dic.storage.repositories.search_rows import SearchResults
from doc2dic.storage.sqlite_rows import optional_text_cell, require_row, text_cell


def load_index_status(connection: sqlite3.Connection) -> str:
    """Return a compact status line for the search index."""
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select value from search_index_metadata where key = 'last_rebuild_at'",
        ).fetchone(),
    )
    if row is None:
        return "metadata missing; search may be degraded or not rebuilt"
    return f"rebuilt at {text_cell(row, 'value')}"


def load_concept_cards(
    connection: sqlite3.Connection,
    results: SearchResults,
    max_concepts: int,
) -> tuple[ConceptCard, ...]:
    """Load approved concept cards for concept search rows."""
    return tuple(
        _concept_card(connection, row.concept_id)
        for row in results.concepts[:max_concepts]
    )


def load_issue_cards(
    connection: sqlite3.Connection,
    results: SearchResults,
    max_issues: int,
) -> tuple[IssueCard, ...]:
    """Load issue cards for issue search rows."""
    return tuple(
        _issue_card(connection, row.issue_id) for row in results.issues[:max_issues]
    )


def load_evidence_cards(
    connection: sqlite3.Connection,
    results: SearchResults,
    max_evidence: int,
    max_quote_chars: int,
) -> tuple[EvidenceCard, ...]:
    """Load bounded evidence cards for evidence search rows."""
    cards = tuple(
        _evidence_card(connection, row.evidence_id, max_quote_chars)
        for row in results.evidence[:max_evidence]
    )
    return _dedupe_evidence(cards)


def _concept_card(connection: sqlite3.Connection, concept_id: str) -> ConceptCard:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select * from concepts where id = ?",
            (concept_id,),
        ).fetchone(),
    )
    required = require_row(row)
    return ConceptCard(
        concept_id=concept_id,
        primary_term=text_cell(required, "primary_term"),
        definition=text_cell(required, "definition"),
        status=text_cell(required, "status"),
        variants=_variant_groups(connection, concept_id),
        source_document=optional_text_cell(required, "source_document"),
    )


def _variant_groups(connection: sqlite3.Connection, concept_id: str) -> VariantGroups:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            """
            select label, variant_type, status
            from term_variants
            where concept_id = ?
            order by variant_type, label, id
            """,
            (concept_id,),
        ).fetchall(),
    )
    groups = MutableVariantGroups()
    for row in rows:
        groups.append(row)
    return groups.freeze()


@dataclass(slots=True)
class MutableVariantGroups:
    """Accumulator used while grouping variant labels."""

    primary: list[str]
    alias: list[str]
    deprecated: list[str]
    forbidden: list[str]

    def __init__(self) -> None:
        """Create empty variant groups."""
        self.primary = []
        self.alias = []
        self.deprecated = []
        self.forbidden = []

    def append(self, row: sqlite3.Row) -> None:
        """Append one variant row to the matching group."""
        label = text_cell(row, "label")
        variant_type = text_cell(row, "variant_type")
        status = text_cell(row, "status")
        if variant_type == "primary" and status == "active":
            self.primary.append(label)
        elif variant_type in {"alias", "abbreviation"} and status == "active":
            self.alias.append(label)
        elif variant_type == "deprecated" or status == "deprecated":
            self.deprecated.append(label)
        elif variant_type == "forbidden" or status == "forbidden":
            self.forbidden.append(label)

    def freeze(self) -> VariantGroups:
        """Return immutable variant groups."""
        return VariantGroups(
            tuple(self.primary),
            tuple(self.alias),
            tuple(self.deprecated),
            tuple(self.forbidden),
        )


def _issue_card(connection: sqlite3.Connection, issue_id: str) -> IssueCard:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            "select * from term_issues where id = ?",
            (issue_id,),
        ).fetchone(),
    )
    required = require_row(row)
    return IssueCard(
        issue_id=issue_id,
        issue_type=text_cell(required, "issue_type"),
        status=text_cell(required, "status"),
        surface=text_cell(required, "surface"),
        candidate_concept_id=optional_text_cell(required, "candidate_concept_id"),
        target_concept_id=optional_text_cell(required, "target_concept_id"),
    )


def _dedupe_evidence(cards: Sequence[EvidenceCard]) -> tuple[EvidenceCard, ...]:
    seen: set[str] = set()
    deduped: list[EvidenceCard] = []
    for card in cards:
        if card.evidence_id not in seen:
            seen.add(card.evidence_id)
            deduped.append(card)
    return tuple(deduped)


def _evidence_card(
    connection: sqlite3.Connection,
    evidence_id: str,
    max_quote_chars: int,
) -> EvidenceCard:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            """
            select ie.id, ie.issue_id, ie.quote, d.path, d.raw_text as document_text,
                   coalesce(dc.section_title, d.title) as section_title,
                   coalesce(dc.raw_text, d.raw_text) as anchor_text
            from issue_evidence ie
            join documents d on d.id = ie.source_document_id
            left join document_chunks dc on dc.id = ie.chunk_id
            where ie.id = ?
            """,
            (evidence_id,),
        ).fetchone(),
    )
    required = require_row(row)
    quote = text_cell(required, "quote")
    bounded_quote = truncate(quote, max_quote_chars)
    return EvidenceCard(
        evidence_id=evidence_id,
        issue_id=text_cell(required, "issue_id"),
        path=text_cell(required, "path"),
        section=text_cell(required, "section_title"),
        line_label=_line_label(
            text_cell(required, "document_text"),
            text_cell(required, "anchor_text"),
            quote,
        ),
        quote=bounded_quote,
        quote_was_truncated=bounded_quote != compact(quote),
    )


def _line_label(document_text: str, anchor_text: str, quote: str) -> str:
    document_line = _line_number(document_text, quote)
    if document_line is not None:
        return f"line {document_line}"
    anchor_line = _line_number(document_text, anchor_text)
    if anchor_line is not None:
        return f"line {anchor_line}"
    return "line 1 (best effort)"


def _line_number(text: str, needle: str) -> int | None:
    compact_needle = compact(needle)
    if compact_needle == "":
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if compact_needle in compact(line):
            return index
    return None
