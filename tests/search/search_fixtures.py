import sqlite3
from dataclasses import dataclass

from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    Document,
    DocumentChunk,
    DocumentMimeType,
    DocumentStatus,
    IssueEvidence,
    IssueEvidenceKind,
    TermIssue,
    TermIssueType,
    TermOccurrence,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.repositories.documents import DocumentRepository
from doc2dic.storage.repositories.issues import IssueRepository

TIMESTAMP = "2026-06-25T00:00:00Z"


@dataclass(frozen=True, slots=True)
class _ConceptSeed:
    concept_id: str
    primary_term: str
    definition: str
    term_type: ConceptTermType
    tags: tuple[str, ...]
    variant_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _IssueSeed:
    issue_id: str
    surface: str
    concept_id: str
    evidence_id: str
    document_id: str
    chunk_id: str
    quote: str


def seed_korean_search_sample(connection: sqlite3.Connection) -> None:
    concept_repository = ConceptRepository(connection)
    document_repository = DocumentRepository(connection)
    issue_repository = IssueRepository(connection)

    for concept in _concepts():
        concept_repository.upsert_concept(concept)
    for variant in _variants():
        concept_repository.upsert_variant(variant)
    for document in _documents():
        document_repository.upsert_document(document)
    for chunk in _chunks():
        document_repository.upsert_chunk(chunk)
    for occurrence in _occurrences():
        document_repository.upsert_occurrence(occurrence)
    for issue in _issues():
        issue_repository.upsert_issue(issue)


def _concepts() -> tuple[Concept, ...]:
    return tuple(
        _concept(seed)
        for seed in (
            _ConceptSeed(
                "concept_stamina",
                "스태미나",
                "던전 입장에 소비되는 행동 자원.",
                ConceptTermType.RESOURCE,
                ("combat", "resource"),
                ("variant_stamina_primary", "variant_stamina_alias"),
            ),
            _ConceptSeed(
                "concept_entry_fatigue",
                "입장 피로도",
                "던전 입장 횟수를 제한하는 피로도 자원.",
                ConceptTermType.RESOURCE,
                ("dungeon",),
                ("variant_entry_fatigue_primary",),
            ),
            _ConceptSeed(
                "concept_stagger",
                "경직",
                "피격 후 잠시 행동할 수 없는 상태.",
                ConceptTermType.STATE,
                ("combat",),
                ("variant_stagger_primary",),
            ),
        )
    )


def _concept(seed: _ConceptSeed) -> Concept:
    return Concept(
        id=seed.concept_id,
        primary_term=seed.primary_term,
        definition=seed.definition,
        term_type=seed.term_type,
        status=ConceptStatus.ACTIVE,
        tags=seed.tags,
        variant_ids=seed.variant_ids,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def _variants() -> tuple[TermVariant, ...]:
    return (
        _variant("variant_stamina_primary", "concept_stamina", "스태미나"),
        _variant("variant_stamina_alias", "concept_stamina", "행동력"),
        _variant(
            "variant_entry_fatigue_primary",
            "concept_entry_fatigue",
            "입장 피로도",
        ),
        _variant("variant_stagger_primary", "concept_stagger", "경직"),
    )


def _variant(variant_id: str, concept_id: str, label: str) -> TermVariant:
    return TermVariant(
        id=variant_id,
        concept_id=concept_id,
        label=label,
        normalized_label=label,
        variant_type=TermVariantType.PRIMARY,
        status=TermVariantStatus.ACTIVE,
        created_at=TIMESTAMP,
        language="ko",
    )


def _documents() -> tuple[Document, ...]:
    return (
        _document("doc_combat", "docs/combat.md", "Combat Design", "스태미나"),
        _document("doc_dungeon", "docs/dungeon.md", "Dungeon Rules", "입장 피로도"),
        _document("doc_status", "docs/status.md", "Status Rules", "경직"),
    )


def _document(document_id: str, path: str, title: str, term: str) -> Document:
    return Document(
        id=document_id,
        path=path,
        title=title,
        content_hash=f"hashhashhash{document_id[-6:]}",
        mime_type=DocumentMimeType.MARKDOWN,
        chunk_ids=(f"chunk_{document_id.removeprefix('doc_')}",),
        raw_text=f"{term} 검색 검증 문서이다.",
        status=DocumentStatus.ANALYZED,
        analyzed_at=TIMESTAMP,
    )


def _chunks() -> tuple[DocumentChunk, ...]:
    return (
        _chunk("chunk_combat", "doc_combat", "전투 자원", "스태미나"),
        _chunk("chunk_dungeon", "doc_dungeon", "입장 규칙", "입장 피로도"),
        _chunk("chunk_status", "doc_status", "상태 이상", "경직"),
    )


def _chunk(chunk_id: str, document_id: str, section: str, term: str) -> DocumentChunk:
    text = f"{term} 검색 검증 청크이다."
    return DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        section_title=section,
        ordinal=0,
        text_preview=text,
        content_hash=f"chunkhashhash{chunk_id[-6:]}",
        raw_text=text,
    )


def _occurrences() -> tuple[TermOccurrence, ...]:
    return (
        _occurrence(
            "occ_stamina",
            "doc_combat",
            "chunk_combat",
            "concept_stamina",
            "스태미나",
        ),
        _occurrence(
            "occ_entry_fatigue",
            "doc_dungeon",
            "chunk_dungeon",
            "concept_entry_fatigue",
            "입장 피로도",
        ),
        _occurrence(
            "occ_stagger",
            "doc_status",
            "chunk_status",
            "concept_stagger",
            "경직",
        ),
    )


def _occurrence(
    occurrence_id: str,
    document_id: str,
    chunk_id: str,
    concept_id: str,
    surface: str,
) -> TermOccurrence:
    return TermOccurrence(
        id=occurrence_id,
        document_id=document_id,
        chunk_id=chunk_id,
        concept_id=concept_id,
        surface=surface,
        offset_start=0,
        offset_end=len(surface),
        confidence=0.98,
    )


def _issues() -> tuple[TermIssue, ...]:
    return tuple(
        _issue(seed)
        for seed in (
            _IssueSeed(
                "issue_stamina",
                "스태미나",
                "concept_stamina",
                "evidence_stamina",
                "doc_combat",
                "chunk_combat",
                "스태미나와 행동력이 같은 문서에서 함께 사용된다.",
            ),
            _IssueSeed(
                "issue_entry_fatigue",
                "입장 피로도",
                "concept_entry_fatigue",
                "evidence_entry_fatigue",
                "doc_dungeon",
                "chunk_dungeon",
                "입장 피로도와 입장권이 던전 입장 비용으로 혼용된다.",
            ),
            _IssueSeed(
                "issue_stagger",
                "경직",
                "concept_stagger",
                "evidence_stagger",
                "doc_status",
                "chunk_status",
                "경직과 기절이 상태 이상 설명에서 혼용된다.",
            ),
        )
    )


def _issue(seed: _IssueSeed) -> TermIssue:
    return TermIssue(
        id=seed.issue_id,
        issue_type=TermIssueType.SAME_MEANING_DIFFERENT_TERM,
        status=IssueStatus.OPEN,
        surface=seed.surface,
        candidate_concept_id=seed.concept_id,
        target_concept_id=None,
        evidence=(
            IssueEvidence(
                id=seed.evidence_id,
                kind=IssueEvidenceKind.QUOTE,
                source_document_id=seed.document_id,
                chunk_id=seed.chunk_id,
                quote=seed.quote,
                confidence=0.88,
            ),
        ),
        created_at=TIMESTAMP,
    )
