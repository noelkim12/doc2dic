"""Review issue domain models."""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from doc2dic.services.review_state_machine import IssueStatus


class TermIssueType(StrEnum):
    """Issue classes stored for human review."""

    UNKNOWN_TERM = "unknown_term"
    FORBIDDEN_TERM = "forbidden_term"
    CONFLICTING_DEFINITION = "conflicting_definition"
    ALIAS_CANDIDATE = "alias_candidate"
    GRAPH_RELATION_CANDIDATE = "graph_relation_candidate"
    SAME_TERM_DIFFERENT_MEANING = "same_term_different_meaning"
    SAME_MEANING_DIFFERENT_TERM = "same_meaning_different_term"
    AMBIGUOUS_USAGE = "ambiguous_usage"


class IssueEvidenceKind(StrEnum):
    """Kinds of evidence attached to review issues."""

    QUOTE = "quote"
    OCCURRENCE = "occurrence"
    GRAPH_RELATION = "graph_relation"
    LLM_RATIONALE = "llm_rationale"


class IssueEvidence(BaseModel):
    """Bounded evidence quote for a review issue."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^evidence_[A-Za-z0-9_-]+$")
    kind: IssueEvidenceKind
    source_document_id: str = Field(pattern=r"^doc_[A-Za-z0-9_-]+$")
    quote: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0, le=1)
    chunk_id: str | None = None
    context_before: str = Field(default="", max_length=240)
    context_after: str = Field(default="", max_length=240)


class TermIssue(BaseModel):
    """A review queue issue and its evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^issue_[A-Za-z0-9_-]+$")
    issue_type: TermIssueType
    status: IssueStatus
    surface: str = Field(min_length=1, max_length=160)
    evidence: tuple[IssueEvidence, ...] = Field(min_length=1)
    created_at: str
    candidate_concept_id: str | None = None
    target_concept_id: str | None = None
    resolved_at: str | None = None
    version: int = Field(default=0, ge=0)
    applied_idempotency_key: str | None = None
