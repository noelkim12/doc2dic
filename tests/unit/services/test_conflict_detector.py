from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    TermIssueType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.conflict_detector import analyze_document
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.llm_service import (
    LLMEvidence,
    LLMProviderError,
    LLMTermCandidate,
    LLMTermCandidatesOutput,
    LLMTermExtractionService,
    TermType,
)
from doc2dic.storage import migrate_database, open_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3

    from doc2dic.services.document_context_cards import AnalysisContextCards


ROOT = Path(__file__).resolve().parents[3]
CREATED_AT = "2026-06-25T00:00:00Z"


@dataclass(slots=True)
class StaticProvider:
    payload: str
    provider_name: str = "static"

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        _ = context
        return self.payload


class FailingProvider:
    provider_name: str = "failing"

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        _ = context
        message = "provider failed"
        raise LLMProviderError(message)


def test_conflict_detector_when_dungeon_sample_analyzed_creates_expected_issues(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=True,
        )
        persisted_count = _issue_count(connection)

    issue_types = {issue.issue_type for issue in result.all_issues}
    assert TermIssueType.SAME_TERM_DIFFERENT_MEANING in issue_types
    assert TermIssueType.SAME_MEANING_DIFFERENT_TERM in issue_types
    assert result.rejected_findings == ()
    assert result.vector_candidates.enabled is False
    assert persisted_count == len(result.all_issues)
    for issue in result.llm_issues:
        for evidence in issue.evidence:
            assert len(evidence.quote) <= 600
            assert "# 던전 입장 규칙 초안" not in evidence.quote


def test_conflict_detector_when_confidence_is_low_creates_ambiguous_usage(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(
        confidence=0.4,
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
    )
    service = LLMTermExtractionService(StaticProvider(_output(candidate)))

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=True,
            llm_service=service,
        )

    assert tuple(issue.issue_type for issue in result.llm_issues) == (
        TermIssueType.AMBIGUOUS_USAGE,
    )
    assert result.rejected_findings == ()


def test_conflict_detector_when_evidence_is_missing_rejects_finding(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(confidence=0.9, quote="문서에 없는 증거 문장이다.")
    service = LLMTermExtractionService(StaticProvider(_output(candidate)))

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=True,
            llm_service=service,
        )

    assert result.llm_issues == ()
    assert len(result.rejected_findings) == 1
    assert result.rejected_findings[0].reason == "missing_bounded_evidence"


def test_conflict_detector_when_provider_fails_skips_provider_issues(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    service = LLMTermExtractionService(FailingProvider())

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=True,
            llm_service=service,
        )

    assert result.failure is not None
    assert result.llm_issues == ()
    assert tuple(issue.issue_type for issue in result.all_issues) == tuple(
        issue.issue_type for issue in result.check.issues
    )


def _candidate(*, confidence: float, quote: str) -> LLMTermCandidate:
    return LLMTermCandidate(
        surface="스태미나",
        definition="던전 입장 자원",
        term_type=TermType.RESOURCE,
        tags=("entry_resource",),
        evidence=(LLMEvidence(quote=quote),),
        confidence=confidence,
    )


def _output(candidate: LLMTermCandidate) -> str:
    return LLMTermCandidatesOutput(candidates=(candidate,)).model_dump_json()


def _database_with_glossary(tmp_path: Path) -> Path:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        repository = ConceptRepository(connection)
        for concept in _concepts():
            repository.upsert_concept(concept)
        for variant in _variants():
            repository.upsert_variant(variant)
    return db_path


def _concepts() -> tuple[Concept, ...]:
    return (
        Concept(
            id="concept_combat_stamina",
            primary_term="스태미나",
            definition="회피와 강공격에 소모되는 전투 자원",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("combat_resource", "combat"),
            variant_ids=("variant_combat_stamina",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_entry_resource",
            primary_term="입장 피로도",
            definition="던전 입장 가능 여부를 결정하는 입장 자원",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("entry_resource",),
            variant_ids=("variant_entry_fatigue", "variant_entry_stamina"),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
    )


def _variants() -> tuple[TermVariant, ...]:
    return (
        _variant(
            "variant_combat_stamina",
            "concept_combat_stamina",
            "스태미나",
            TermVariantType.PRIMARY,
        ),
        _variant(
            "variant_entry_fatigue",
            "concept_entry_resource",
            "입장 피로도",
            TermVariantType.PRIMARY,
        ),
        _variant(
            "variant_entry_stamina",
            "concept_entry_resource",
            "스태미나",
            TermVariantType.ALIAS,
        ),
    )


def _variant(
    variant_id: str,
    concept_id: str,
    label: str,
    variant_type: TermVariantType,
) -> TermVariant:
    return TermVariant(
        id=variant_id,
        concept_id=concept_id,
        label=label,
        normalized_label=normalize_term_text(label),
        variant_type=variant_type,
        status=TermVariantStatus.ACTIVE,
        created_at=CREATED_AT,
    )


def _issue_count(connection: sqlite3.Connection) -> int:
    row = cast(
        "sqlite3.Row | None",
        connection.execute("select count(*) as count from term_issues").fetchone(),
    )
    return int_cell(require_row(row), "count")
