from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

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
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.graph_projection_service import (
    GraphProjectionError,
    GraphProjectionService,
)
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage import initialize_project_storage, open_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.repositories.documents import DocumentRepository
from doc2dic.storage.repositories.issues import IssueRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3

CREATED_AT = "2026-06-25T00:00:00Z"


def test_current_graph_when_fixture_db_projected_contains_expected_nodes_and_edges(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)
    with open_database(db_path) as connection:
        seed_graph_fixture(connection)

        graph = GraphProjectionService(connection).current_graph()

    assert [node.id for node in graph.nodes] == [
        "concept_combat_stamina",
        "concept_dodge_roll",
        "concept_entry_stamina",
    ]
    assert graph.nodes[0].label == "combat.stamina"
    assert [(edge.source, edge.relation, edge.target) for edge in graph.edges] == [
        ("concept_combat_stamina", "alias_of", "concept_combat_stamina"),
        ("concept_combat_stamina", "contradicts", "concept_entry_stamina"),
        ("concept_combat_stamina", "depends_on", "concept_dodge_roll"),
    ]


def test_current_graph_when_unknown_relation_exists_raises_projection_error(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)
    with open_database(db_path) as connection:
        seed_graph_fixture(connection)
        _ = connection.execute(
            """
            insert into concept_relations(
              id, source_concept_id, target_concept_id, relation_type,
              confidence, status
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                "relation_unknown",
                "concept_dodge_roll",
                "concept_entry_stamina",
                "unsafe_unknown",
                1.0,
                "approved",
            ),
        )

        with pytest.raises(GraphProjectionError, match="unknown graph relation type"):
            _ = GraphProjectionService(connection).current_graph()


def test_persist_current_snapshot_when_run_repeatedly_is_deterministic(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)
    with open_database(db_path) as connection:
        seed_graph_fixture(connection)
        service = GraphProjectionService(connection)

        first = service.persist_current_snapshot()
        second = service.persist_current_snapshot()

        row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select count(*) as count from graph_snapshots",
            ).fetchone(),
        )

    assert first == second
    assert int_cell(require_row(row), "count") == 1
    assert first.id.startswith("snapshot_")
    assert first.created_at == CREATED_AT


def seed_graph_fixture(connection: "sqlite3.Connection") -> None:
    concept_repository = ConceptRepository(connection)
    document_repository = DocumentRepository(connection)
    issue_repository = IssueRepository(connection)
    for concept in _concepts():
        concept_repository.upsert_concept(concept)
    for variant in _variants():
        concept_repository.upsert_variant(variant)
    document_repository.upsert_document(_document())
    document_repository.upsert_chunk(_chunk())
    issue_repository.upsert_issue(_issue())
    _ = connection.execute(
        """
        insert into concept_relations(
          id, source_concept_id, target_concept_id, relation_type, confidence, status
        ) values (?, ?, ?, ?, ?, ?)
        """,
        (
            "relation_combat_stamina_depends_on_dodge",
            "concept_combat_stamina",
            "concept_dodge_roll",
            "depends_on",
            1.0,
            "approved",
        ),
    )
    connection.commit()


def _concepts() -> tuple[Concept, ...]:
    return (
        Concept(
            id="concept_combat_stamina",
            primary_term="combat.stamina",
            definition="Resource spent by combat actions.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("combat",),
            variant_ids=("variant_combat_stamina", "variant_sta"),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_dodge_roll",
            primary_term="Dodge Roll",
            definition="Movement action that spends stamina.",
            term_type=ConceptTermType.ACTION,
            status=ConceptStatus.ACTIVE,
            tags=("combat",),
            variant_ids=("variant_dodge_roll",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_entry_stamina",
            primary_term="Entry Stamina",
            definition="Resource spent to enter a dungeon.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("economy",),
            variant_ids=("variant_entry_stamina",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
    )


def _variants() -> tuple[TermVariant, ...]:
    return (
        _variant("variant_combat_stamina", "concept_combat_stamina", "combat.stamina"),
        _variant(
            "variant_sta",
            "concept_combat_stamina",
            "STA",
            TermVariantType.ALIAS,
        ),
        _variant("variant_dodge_roll", "concept_dodge_roll", "Dodge Roll"),
        _variant("variant_entry_stamina", "concept_entry_stamina", "Entry Stamina"),
    )


def _variant(
    variant_id: str,
    concept_id: str,
    label: str,
    variant_type: TermVariantType = TermVariantType.PRIMARY,
) -> TermVariant:
    return TermVariant(
        id=variant_id,
        concept_id=concept_id,
        label=label,
        normalized_label=label.casefold(),
        variant_type=variant_type,
        status=TermVariantStatus.ACTIVE,
        created_at=CREATED_AT,
    )


def _document() -> Document:
    return Document(
        id="doc_combat_core",
        path="docs/combat.md",
        title="Combat Core",
        content_hash="a" * 16,
        mime_type=DocumentMimeType.MARKDOWN,
        chunk_ids=("chunk_combat_core",),
        analyzed_at=CREATED_AT,
        raw_text="combat.stamina conflicts with entry stamina.",
        status=DocumentStatus.ANALYZED,
    )


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        id="chunk_combat_core",
        document_id="doc_combat_core",
        section_title="Combat",
        ordinal=0,
        text_preview="combat.stamina conflicts with entry stamina.",
        content_hash="b" * 16,
        raw_text="combat.stamina conflicts with entry stamina.",
    )


def _issue() -> TermIssue:
    return TermIssue(
        id="issue_stamina_conflict",
        issue_type=TermIssueType.SAME_TERM_DIFFERENT_MEANING,
        status=IssueStatus.OPEN,
        surface="stamina",
        evidence=(
            IssueEvidence(
                id="evidence_stamina_conflict",
                kind=IssueEvidenceKind.QUOTE,
                source_document_id="doc_combat_core",
                chunk_id="chunk_combat_core",
                quote="combat.stamina conflicts with entry stamina.",
                confidence=1.0,
            ),
        ),
        created_at=CREATED_AT,
        candidate_concept_id="concept_combat_stamina",
        target_concept_id="concept_entry_stamina",
    )
