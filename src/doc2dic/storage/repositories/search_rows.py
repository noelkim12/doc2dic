"""Typed search result rows."""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchConceptRow:
    """Concept search hit from glossary terms and variants."""

    concept_id: str
    primary_term: str
    definition: str


@dataclass(frozen=True, slots=True)
class SearchDocumentRow:
    """Document or chunk search hit from indexed source text."""

    document_id: str
    chunk_id: str | None
    path: str
    title: str
    section_title: str


@dataclass(frozen=True, slots=True)
class SearchIssueRow:
    """Review issue search hit from surfaces and attached evidence."""

    issue_id: str
    surface: str
    status: str
    candidate_concept_id: str | None
    target_concept_id: str | None


@dataclass(frozen=True, slots=True)
class SearchEvidenceRow:
    """Issue evidence search hit with document and chunk anchors."""

    evidence_id: str
    issue_id: str
    source_document_id: str
    chunk_id: str | None
    quote: str


@dataclass(frozen=True, slots=True)
class SearchResults:
    """Typed bounded search result groups."""

    concepts: tuple[SearchConceptRow, ...]
    documents: tuple[SearchDocumentRow, ...]
    issues: tuple[SearchIssueRow, ...]
    evidence: tuple[SearchEvidenceRow, ...]

    @property
    def is_empty(self) -> bool:
        """Return whether every result group is empty."""
        return not (self.concepts or self.documents or self.issues or self.evidence)

    def __iter__(
        self,
    ) -> Iterator[
        tuple[SearchConceptRow, ...]
        | tuple[SearchDocumentRow, ...]
        | tuple[SearchIssueRow, ...]
        | tuple[SearchEvidenceRow, ...]
    ]:
        """Iterate result groups for aggregate bounds checks."""
        yield self.concepts
        yield self.documents
        yield self.issues
        yield self.evidence
