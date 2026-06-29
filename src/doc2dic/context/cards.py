"""Typed cards for agent-ready terminology context."""

from dataclasses import dataclass
from typing import Final

DEFAULT_MAX_OUTPUT_CHARS: Final = 6000
DEFAULT_MAX_QUERY_CHARS: Final = 240
DEFAULT_MAX_CONCEPTS: Final = 5
DEFAULT_MAX_ISSUES: Final = 5
DEFAULT_MAX_EVIDENCE: Final = 6
DEFAULT_MAX_EVIDENCE_QUOTE_CHARS: Final = 220


@dataclass(frozen=True, slots=True)
class ExploreContextLimits:
    """Budgets for agent-ready terminology context."""

    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS
    max_query_chars: int = DEFAULT_MAX_QUERY_CHARS
    max_concepts: int = DEFAULT_MAX_CONCEPTS
    max_issues: int = DEFAULT_MAX_ISSUES
    max_evidence: int = DEFAULT_MAX_EVIDENCE
    max_evidence_quote_chars: int = DEFAULT_MAX_EVIDENCE_QUOTE_CHARS


DEFAULT_EXPLORE_CONTEXT_LIMITS: Final = ExploreContextLimits()


@dataclass(frozen=True, slots=True)
class VariantGroups:
    """Variant labels grouped for approved fact rendering."""

    primary: tuple[str, ...]
    alias: tuple[str, ...]
    deprecated: tuple[str, ...]
    forbidden: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConceptCard:
    """Approved concept facts with bounded variant labels."""

    concept_id: str
    primary_term: str
    definition: str
    status: str
    variants: VariantGroups
    source_document: str | None = None
    physical_name: str | None = None


@dataclass(frozen=True, slots=True)
class IssueCard:
    """Open review issue candidate surfaced for agent judgment."""

    issue_id: str
    issue_type: str
    status: str
    surface: str
    candidate_concept_id: str | None
    target_concept_id: str | None


@dataclass(frozen=True, slots=True)
class EvidenceCard:
    """Bounded untrusted evidence quote with citation metadata."""

    evidence_id: str
    issue_id: str
    path: str
    section: str
    line_label: str
    quote: str
    quote_was_truncated: bool
