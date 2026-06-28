"""Conflict detection pipeline for analysis-backed review issues."""

import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import Final

from doc2dic.domain import IssueEvidence, IssueEvidenceKind, TermIssue, TermIssueType
from doc2dic.services import conflict_vector
from doc2dic.services.document_check import CheckResult, check_document
from doc2dic.services.document_conflict_models import (
    CandidateContext,
    CandidateEvidence,
    ClassifiedCandidates,
    ConflictAnalysisResult,
    RejectedFinding,
)
from doc2dic.services.document_context_cards import DocumentContextInput
from doc2dic.services.document_glossary import load_glossary_terms
from doc2dic.services.document_issue_detection import CONTEXT_CHARS, CREATED_AT
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.llm_service import (
    AnalysisFailure,
    LLMTermCandidate,
    LLMTermExtractionService,
    TermExtractionSuccess,
    llm_provider_from_environment,
)
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage.repositories.issues import IssueRepository

MIN_CONFLICT_CONFIDENCE: Final = 0.65
MAX_CONTEXT_CHARS: Final = 240


def analyze_document(
    connection: sqlite3.Connection,
    path: Path,
    *,
    write_issues: bool,
    llm_service: LLMTermExtractionService | None = None,
    vector_dependencies: conflict_vector.ConflictVectorDependencies | None = None,
) -> ConflictAnalysisResult:
    """Run parser, exact checks, provider extraction, and conflict issue creation."""
    check = check_document(connection, path, write_issues=False)
    vector_candidates = conflict_vector.disabled_vector_query_result(
        "no semantic vector query candidates",
    )
    service = llm_service or LLMTermExtractionService(llm_provider_from_environment())
    extraction = service.extract_terms(
        DocumentContextInput(
            document_id=check.document.id,
            path=check.document.path,
            title=check.document.title,
            text=check.document.raw_text,
        ),
        )
    match extraction:
        case TermExtractionSuccess(provider=provider, candidates=candidates):
            dependencies = vector_dependencies
            if dependencies is None:
                dependencies = conflict_vector.default_conflict_vector_dependencies(
                    connection,
                )
            vector_result = conflict_vector.query_conflict_vector_candidates(
                connection,
                check,
                candidates,
                embedding_service=dependencies.embedding_service,
                vector_store=dependencies.vector_store,
            )
            vector_candidates = vector_result.vector_candidates
            classified = _classify_candidates(
                connection,
                check,
                candidates,
                semantic_matches=vector_result.matches,
            )
            llm_issues = classified.issues
            rejected = classified.rejected
            failure = None
        case AnalysisFailure() as failure:
            provider = failure.provider
            candidates = ()
            llm_issues = ()
            rejected = ()
    all_issues = (*check.issues, *llm_issues)
    if write_issues:
        _persist_issues(connection, all_issues)
    return ConflictAnalysisResult(
        check=check,
        provider=provider,
        candidates=candidates,
        llm_issues=llm_issues,
        all_issues=all_issues,
        rejected_findings=rejected,
        failure=failure,
        vector_candidates=vector_candidates,
    )

def _classify_candidates(
    connection: sqlite3.Connection,
    check: CheckResult,
    candidates: tuple[LLMTermCandidate, ...],
    *,
    semantic_matches: tuple[conflict_vector.SemanticConceptMatch, ...] = (),
) -> ClassifiedCandidates:
    terms = load_glossary_terms(connection)
    concepts = conflict_vector.load_active_concepts(connection)
    semantic_concept_ids = {
        semantic_match.candidate_index: semantic_match.concept_id
        for semantic_match in semantic_matches
    }
    issues: list[TermIssue] = []
    rejected: list[RejectedFinding] = []
    seen_issue_ids: set[str] = set()
    for candidate_index, candidate in enumerate(candidates):
        evidence = _candidate_evidence(check, candidate)
        if evidence is None:
            rejected.append(_rejected(candidate, "missing_bounded_evidence"))
            continue
        matched_terms = conflict_vector.matching_terms(terms, candidate.surface)
        context = CandidateContext(
            candidate=candidate,
            evidence=evidence,
            matching_terms=matched_terms,
            related_concept=conflict_vector.related_concept(
                concepts,
                candidate,
                matched_terms,
                semantic_concept_ids.get(candidate_index),
            ),
        )
        for issue in _candidate_issues(check.document.id, context):
            if issue.id not in seen_issue_ids:
                issues.append(issue)
                seen_issue_ids.add(issue.id)
    return ClassifiedCandidates(issues=tuple(issues), rejected=tuple(rejected))


def _candidate_issues(
    document_id: str,
    context: CandidateContext,
) -> tuple[TermIssue, ...]:
    if context.candidate.confidence < MIN_CONFLICT_CONFIDENCE:
        return (_issue(document_id, TermIssueType.AMBIGUOUS_USAGE, context),)
    concept_ids = tuple(sorted({term.concept_id for term in context.matching_terms}))
    if len(concept_ids) > 1:
        return (
            _issue(document_id, TermIssueType.SAME_TERM_DIFFERENT_MEANING, context),
        )
    if _has_same_meaning_different_terms(context):
        return (
            _issue(document_id, TermIssueType.SAME_MEANING_DIFFERENT_TERM, context),
        )
    return ()


def _issue(
    document_id: str,
    issue_type: TermIssueType,
    context: CandidateContext,
) -> TermIssue:
    concept_ids = tuple(sorted({term.concept_id for term in context.matching_terms}))
    candidate_concept_id = _candidate_concept_id(context, concept_ids)
    if len(concept_ids) > 1:
        target_concept_id = concept_ids[-1]
    else:
        target_concept_id = candidate_concept_id
    discriminator = ":".join(
        (
            "llm",
            issue_type.value,
            context.candidate.surface,
            candidate_concept_id or "none",
            target_concept_id or "none",
        ),
    )
    evidence_id = _digest(document_id, discriminator, context.evidence.chunk_id)
    return TermIssue(
        id=f"issue_{_digest(document_id, discriminator)}",
        issue_type=issue_type,
        status=IssueStatus.OPEN,
        surface=context.candidate.surface,
        candidate_concept_id=candidate_concept_id,
        target_concept_id=target_concept_id,
        evidence=(
            IssueEvidence(
                id=f"evidence_{evidence_id}",
                kind=IssueEvidenceKind.QUOTE,
                source_document_id=document_id,
                chunk_id=context.evidence.chunk_id,
                quote=context.evidence.quote,
                context_before=context.evidence.context_before,
                context_after=context.evidence.context_after,
                confidence=context.candidate.confidence,
            ),
        ),
        created_at=CREATED_AT,
    )


def _candidate_concept_id(
    context: CandidateContext,
    concept_ids: tuple[str, ...],
) -> str | None:
    if len(concept_ids) > 0:
        return concept_ids[0]
    if context.related_concept is not None:
        return context.related_concept.concept_id
    return None


def _has_same_meaning_different_terms(context: CandidateContext) -> bool:
    if context.related_concept is None:
        return False
    candidate_label = normalize_term_text(context.candidate.surface)
    primary_label = normalize_term_text(context.related_concept.primary_term)
    return candidate_label != primary_label or len(context.matching_terms) > 1


def _candidate_evidence(
    check: CheckResult,
    candidate: LLMTermCandidate,
) -> CandidateEvidence | None:
    for evidence in candidate.evidence:
        for chunk in check.chunks:
            start = chunk.raw_text.find(evidence.quote)
            if start >= 0:
                end = start + len(evidence.quote)
                return CandidateEvidence(
                    quote=evidence.quote,
                    chunk_id=chunk.id,
                    context_before=_context_before(chunk.raw_text, start),
                    context_after=chunk.raw_text[end : end + CONTEXT_CHARS][
                        :MAX_CONTEXT_CHARS
                    ],
                )
    return None


def _context_before(text: str, start: int) -> str:
    return text[max(0, start - CONTEXT_CHARS) : start][-MAX_CONTEXT_CHARS:]


def _rejected(candidate: LLMTermCandidate, reason: str) -> RejectedFinding:
    return RejectedFinding(
        surface=candidate.surface,
        reason=reason,
        confidence=candidate.confidence,
    )


def _persist_issues(
    connection: sqlite3.Connection,
    issues: tuple[TermIssue, ...],
) -> None:
    repository = IssueRepository(connection)
    for issue in issues:
        repository.upsert_issue(issue)


def _digest(*parts: str) -> str:
    return sha256("\u241f".join(parts).encode()).hexdigest()[:16]


__all__ = [
    "ConflictAnalysisResult",
    "RejectedFinding",
    "analyze_document",
]
