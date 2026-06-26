"""Immutable data models for document conflict analysis."""

from dataclasses import dataclass

from doc2dic.domain import TermIssue
from doc2dic.services.document_check import CheckResult
from doc2dic.services.document_glossary import GlossaryTerm
from doc2dic.services.llm_service import AnalysisFailure, LLMTermCandidate
from doc2dic.storage.vector_types import VectorQueryResult


@dataclass(frozen=True, slots=True)
class RejectedFinding:
    """Provider candidate rejected before review issue persistence."""

    surface: str
    reason: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ActiveConcept:
    """Glossary concept data needed for inferred conflict classification."""

    concept_id: str
    primary_term: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """Bounded candidate evidence resolved against a stored chunk."""

    quote: str
    chunk_id: str
    context_before: str
    context_after: str


@dataclass(frozen=True, slots=True)
class CandidateContext:
    """Typed context for classifying one provider candidate."""

    candidate: LLMTermCandidate
    evidence: CandidateEvidence
    matching_terms: tuple[GlossaryTerm, ...]
    related_concept: ActiveConcept | None


@dataclass(frozen=True, slots=True)
class ClassifiedCandidates:
    """Accepted and rejected provider candidate classifications."""

    issues: tuple[TermIssue, ...]
    rejected: tuple[RejectedFinding, ...]


@dataclass(frozen=True, slots=True)
class ConflictAnalysisResult:
    """Combined deterministic check and provider conflict analysis result."""

    check: CheckResult
    provider: str | None
    candidates: tuple[LLMTermCandidate, ...]
    llm_issues: tuple[TermIssue, ...]
    all_issues: tuple[TermIssue, ...]
    rejected_findings: tuple[RejectedFinding, ...]
    failure: AnalysisFailure | None
    vector_candidates: VectorQueryResult


__all__ = [
    "ActiveConcept",
    "CandidateContext",
    "CandidateEvidence",
    "ClassifiedCandidates",
    "ConflictAnalysisResult",
    "RejectedFinding",
]
