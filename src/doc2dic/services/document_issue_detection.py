"""Review issue construction for deterministic document checks."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from doc2dic.domain import (
    ConceptStatus,
    IssueEvidence,
    IssueEvidenceKind,
    TermIssue,
    TermIssueType,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.document_glossary import GlossaryTerm, term_is_active
from doc2dic.services.document_occurrences import DetectedOccurrence
from doc2dic.services.review_state_machine import IssueStatus

CREATED_AT: Final = "2026-06-25T00:00:00Z"
MAX_EVIDENCE_ITEMS: Final = 4
CONTEXT_CHARS: Final = 80


@dataclass(frozen=True, slots=True)
class IssueDraft:
    """Inputs needed to construct a stable review issue."""

    document_id: str
    issue_type: TermIssueType
    surface: str
    candidate_concept_id: str
    target_concept_id: str
    detections: tuple[DetectedOccurrence, ...]
    discriminator: str


def detect_issues(
    document_id: str,
    detections: tuple[DetectedOccurrence, ...],
    terms: tuple[GlossaryTerm, ...],
) -> tuple[TermIssue, ...]:
    """Generate lifecycle, exact conflict, and alias candidate issues."""
    issues = [*_forbidden_and_deprecated_issues(document_id, detections)]
    issues.extend(_same_term_issues(document_id, detections, terms))
    issues.extend(_same_meaning_issues(document_id, detections))
    return tuple(issues)


def _forbidden_and_deprecated_issues(
    document_id: str,
    detections: tuple[DetectedOccurrence, ...],
) -> tuple[TermIssue, ...]:
    grouped: dict[tuple[TermIssueType, str, str], list[DetectedOccurrence]] = {}
    for detection in detections:
        issue_type = _lifecycle_issue_type(detection.term)
        if issue_type is None:
            continue
        key = (issue_type, detection.term.concept_id, detection.term.normalized_label)
        grouped.setdefault(key, []).append(detection)
    return tuple(
        _issue(
            IssueDraft(
                document_id=document_id,
                issue_type=issue_type,
                surface=items[0].surface,
                candidate_concept_id=concept_id,
                target_concept_id=concept_id,
                detections=tuple(items),
                discriminator=(
                    f"lifecycle:{issue_type.value}:{concept_id}:{normalized_label}"
                ),
            ),
        )
        for (issue_type, concept_id, normalized_label), items in grouped.items()
    )


def _same_term_issues(
    document_id: str,
    detections: tuple[DetectedOccurrence, ...],
    terms: tuple[GlossaryTerm, ...],
) -> tuple[TermIssue, ...]:
    concepts_by_label: dict[str, set[str]] = {}
    for term in terms:
        if term_is_active(term):
            concepts_by_label.setdefault(term.normalized_label, set()).add(
                term.concept_id,
            )
    grouped: dict[str, list[DetectedOccurrence]] = {}
    for detection in detections:
        concepts = concepts_by_label.get(detection.term.normalized_label, set())
        if len(concepts) > 1 and term_is_active(detection.term):
            grouped.setdefault(detection.term.normalized_label, []).append(detection)
    return tuple(
        _same_term_issue(document_id, label, items)
        for label, items in grouped.items()
    )


def _same_meaning_issues(
    document_id: str,
    detections: tuple[DetectedOccurrence, ...],
) -> tuple[TermIssue, ...]:
    grouped: dict[str, list[DetectedOccurrence]] = {}
    for detection in detections:
        if (
            term_is_active(detection.term)
            and detection.term.variant_type is TermVariantType.ALIAS
        ):
            grouped.setdefault(detection.term.concept_id, []).append(detection)
    return tuple(
        _issue(
            IssueDraft(
                document_id=document_id,
                issue_type=TermIssueType.SAME_MEANING_DIFFERENT_TERM,
                surface=items[0].surface,
                candidate_concept_id=concept_id,
                target_concept_id=concept_id,
                detections=tuple(items),
                discriminator=f"same-meaning:{concept_id}",
            ),
        )
        for concept_id, items in grouped.items()
    )


def _same_term_issue(
    document_id: str,
    normalized_label: str,
    items: list[DetectedOccurrence],
) -> TermIssue:
    concept_ids = tuple(sorted({detection.term.concept_id for detection in items}))
    return _issue(
        IssueDraft(
            document_id=document_id,
            issue_type=TermIssueType.SAME_TERM_DIFFERENT_MEANING,
            surface=items[0].surface,
            candidate_concept_id=concept_ids[0],
            target_concept_id=concept_ids[-1],
            detections=tuple(items),
            discriminator=f"same-term:{normalized_label}",
        ),
    )


def _lifecycle_issue_type(term: GlossaryTerm) -> TermIssueType | None:
    if term.concept_status is ConceptStatus.FORBIDDEN:
        return TermIssueType.FORBIDDEN_TERM
    if term.variant_status is TermVariantStatus.FORBIDDEN:
        return TermIssueType.FORBIDDEN_TERM
    if term.concept_status is ConceptStatus.DEPRECATED:
        return TermIssueType.ALIAS_CANDIDATE
    if term.variant_status is TermVariantStatus.DEPRECATED:
        return TermIssueType.ALIAS_CANDIDATE
    return None


def _issue(draft: IssueDraft) -> TermIssue:
    evidence = tuple(
        _evidence(draft.document_id, draft.discriminator, detection, index)
        for index, detection in enumerate(
            draft.detections[:MAX_EVIDENCE_ITEMS],
            start=1,
        )
    )
    return TermIssue(
        id=f"issue_{_digest(draft.document_id, draft.discriminator)}",
        issue_type=draft.issue_type,
        status=IssueStatus.OPEN,
        surface=draft.surface,
        candidate_concept_id=draft.candidate_concept_id,
        target_concept_id=draft.target_concept_id,
        evidence=evidence,
        created_at=CREATED_AT,
    )


def _evidence(
    document_id: str,
    discriminator: str,
    detection: DetectedOccurrence,
    index: int,
) -> IssueEvidence:
    quote = _sentence_quote(
        detection.chunk.raw_text,
        detection.offset_start,
        detection.offset_end,
    )
    before_start = max(0, detection.offset_start - CONTEXT_CHARS)
    after_end = min(len(detection.chunk.raw_text), detection.offset_end + CONTEXT_CHARS)
    evidence_id = _digest(
        document_id,
        discriminator,
        detection.chunk.id,
        detection.surface,
        str(index),
    )
    return IssueEvidence(
        id=f"evidence_{evidence_id}",
        kind=IssueEvidenceKind.OCCURRENCE,
        source_document_id=document_id,
        chunk_id=detection.chunk.id,
        quote=quote,
        context_before=detection.chunk.raw_text[before_start : detection.offset_start],
        context_after=detection.chunk.raw_text[detection.offset_end : after_end],
        confidence=1.0,
    )


def _sentence_quote(text: str, offset_start: int, offset_end: int) -> str:
    before = text.rfind("\n", 0, offset_start)
    sentence_start = 0 if before < 0 else before + 1
    after = text.find("\n", offset_end)
    sentence_end = len(text) if after < 0 else after
    return text[sentence_start:sentence_end].strip()[:600]


def _digest(*parts: str) -> str:
    return sha256("\u241f".join(parts).encode()).hexdigest()[:16]
