from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from unittest.mock import patch

from doc2dic.commands import check as check_command
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
from doc2dic.services.conflict_vector import ConflictVectorDependencies
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.embedding_service import (
    DisabledEmbeddingProvider,
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingVector,
)
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
from doc2dic.storage.vector_store import StoredVector, VectorStore

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Sequence

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


@dataclass(slots=True)
class RecordingEmbeddingProvider:
    dimension: int = 3
    model: str = "recording-model"
    provider_name: str = "recording-provider"
    calls: list[tuple[tuple[str, ...], EmbeddingInputType]] = field(
        default_factory=list,
    )

    def embed_texts(
        self,
        texts: tuple[str, ...],
        input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        self.calls.append((texts, input_type))
        return tuple(
            EmbeddingVector(
                text=text,
                model=self.model,
                values=tuple(float(index + 1) for index in range(self.dimension)),
            )
            for text in texts
        )


@dataclass(slots=True)
class RecordingVectorBackend:
    query_matches: tuple[tuple[int, float], ...]
    create_dimensions: list[int] = field(default_factory=list)
    query_calls: list[tuple[tuple[float, ...], int]] = field(default_factory=list)

    def load(self, connection: sqlite3.Connection) -> None:
        del connection

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        self.create_dimensions.append(dimension)
        _ = connection.execute("drop table if exists embedding_vectors")
        _ = connection.execute(
            "create table embedding_vectors(rowid integer primary key, embedding text)",
        )

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        _ = connection.execute(
            "insert or replace into embedding_vectors(rowid, embedding) values (?, ?)",
            (vector.embedding_id, json.dumps(vector.values)),
        )

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        del connection
        self.query_calls.append((tuple(vector), top_k))
        return self.query_matches


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


def test_conflict_detector_embeds_candidate_query_before_vector_search(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    quote = "스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다."
    candidate = _candidate(surface="입장 자원", quote=quote, tags=("semantic",))
    llm_service = LLMTermExtractionService(StaticProvider(_output(candidate)))
    embedding_provider = RecordingEmbeddingProvider()
    vector_backend = RecordingVectorBackend(query_matches=((2, 0.1),))

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=False,
            llm_service=llm_service,
            vector_dependencies=ConflictVectorDependencies(
                embedding_service=EmbeddingService(embedding_provider),
                vector_store=VectorStore(connection, backend=vector_backend),
            ),
        )

    input_types = tuple(input_type for _, input_type in embedding_provider.calls)
    query_text = embedding_provider.calls[-1][0][0]
    assert input_types == (
        EmbeddingInputType.DOCUMENT,
        EmbeddingInputType.QUERY,
    )
    assert all(text in query_text for text in ("입장 자원", "던전 입장 자원", quote))
    assert vector_backend.query_calls == [((1.0, 2.0, 3.0), 3)]
    assert result.vector_candidates.enabled is True
    assert result.vector_candidates.matches[0].embedding_id == 2


def test_conflict_detector_ensures_active_concept_embeddings_before_query(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(
        surface="입장 자원",
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
        tags=("semantic",),
    )
    embedding_provider = RecordingEmbeddingProvider(dimension=4)
    vector_backend = RecordingVectorBackend(query_matches=((2, 0.1),))

    with open_database(db_path) as connection:
        _ = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=False,
            llm_service=LLMTermExtractionService(StaticProvider(_output(candidate))),
            vector_dependencies=ConflictVectorDependencies(
                embedding_service=EmbeddingService(embedding_provider),
                vector_store=VectorStore(connection, backend=vector_backend),
            ),
        )
        embedding_count = _table_count(connection, "embeddings")

    assert vector_backend.create_dimensions == [4]
    assert embedding_count == 2
    assert tuple(input_type for _, input_type in embedding_provider.calls) == (
        EmbeddingInputType.DOCUMENT,
        EmbeddingInputType.QUERY,
    )


def test_conflict_detector_exact_match_wins_over_vector_match(tmp_path: Path) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(
        surface="입장 피로도",
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
        tags=("semantic",),
    )

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=False,
            llm_service=LLMTermExtractionService(StaticProvider(_output(candidate))),
            vector_dependencies=ConflictVectorDependencies(
                embedding_service=EmbeddingService(RecordingEmbeddingProvider()),
                vector_store=VectorStore(
                    connection,
                    backend=RecordingVectorBackend(query_matches=((1, 0.1),)),
                ),
            ),
        )

    assert result.llm_issues == ()
    assert result.vector_candidates.enabled is True


def test_conflict_detector_semantic_match_creates_related_concept_issue(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(
        surface="입장 자원",
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
        tags=("semantic",),
    )

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=False,
            llm_service=LLMTermExtractionService(StaticProvider(_output(candidate))),
            vector_dependencies=ConflictVectorDependencies(
                embedding_service=EmbeddingService(RecordingEmbeddingProvider()),
                vector_store=VectorStore(
                    connection,
                    backend=RecordingVectorBackend(query_matches=((2, 0.1),)),
                ),
            ),
        )

    assert tuple(issue.issue_type for issue in result.llm_issues) == (
        TermIssueType.SAME_MEANING_DIFFERENT_TERM,
    )
    assert result.llm_issues[0].candidate_concept_id == "concept_entry_resource"
    assert result.vector_candidates.enabled is True


def test_check_without_write_issues_does_not_run_analysis_embeddings(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    doc_path = project / "doc.md"
    _ = doc_path.write_text("# 문서\n\n스태미나를 점검한다.\n", encoding="utf-8")
    doc2dic_dir = project / ".doc2dic"
    doc2dic_dir.mkdir()
    db_path = doc2dic_dir / "glossary.sqlite3"
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        repository = ConceptRepository(connection)
        for concept in _concepts():
            repository.upsert_concept(concept)
        for variant in _variants():
            repository.upsert_variant(variant)
    _ = (doc2dic_dir / "config.toml").write_text("[project]\n", encoding="utf-8")

    failure_message = "analysis should not run for check without --write-issues"
    original_cwd = Path.cwd()
    os.chdir(project)
    try:
        with patch(
            "doc2dic.commands.check.analyze_document",
            side_effect=AssertionError(failure_message),
        ):
            check_command.check(paths=[str(doc_path)], write_issues=False)
    finally:
        os.chdir(original_cwd)


def test_conflict_detector_disabled_embedding_returns_disabled_vector_candidates(
    tmp_path: Path,
) -> None:
    db_path = _database_with_glossary(tmp_path)
    candidate = _candidate(
        surface="입장 자원",
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
        tags=("semantic",),
    )

    with open_database(db_path) as connection:
        result = analyze_document(
            connection,
            ROOT / "samples" / "docs" / "dungeon_draft.md",
            write_issues=False,
            llm_service=LLMTermExtractionService(StaticProvider(_output(candidate))),
            vector_dependencies=ConflictVectorDependencies(
                embedding_service=EmbeddingService(DisabledEmbeddingProvider()),
                vector_store=VectorStore(connection),
            ),
        )

    assert result.vector_candidates.enabled is False
    assert tuple(issue.issue_type for issue in result.llm_issues) == ()


def _candidate(
    *,
    quote: str,
    confidence: float = 0.9,
    surface: str = "스태미나",
    definition: str = "던전 입장 자원",
    tags: tuple[str, ...] = ("entry_resource",),
) -> LLMTermCandidate:
    return LLMTermCandidate(
        surface=surface,
        definition=definition,
        term_type=TermType.RESOURCE,
        tags=tags,
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


def _table_count(
    connection: sqlite3.Connection,
    table_name: Literal["embeddings"],
) -> int:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(f"select count(*) as count from {table_name}").fetchone(),  # noqa: S608
    )
    return int_cell(require_row(row), "count")
