import sqlite3
from pathlib import Path
from typing import cast

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
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.repositories.documents import DocumentRepository
from doc2dic.storage.repositories.issues import IssueRepository
from doc2dic.storage.sqlite_rows import require_row, text_cell


def test_concept_repository_when_upserting_concept_returns_canonical_json(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    concept = Concept(
        id="concept_stamina",
        primary_term="Stamina",
        definition="A resource spent to enter dungeons.",
        term_type=ConceptTermType.RESOURCE,
        status=ConceptStatus.ACTIVE,
        tags=("combat", "resource"),
        variant_ids=("variant_stamina",),
        created_at="2026-06-25T00:00:00Z",
        updated_at="2026-06-25T00:00:00Z",
    )
    variant = TermVariant(
        id="variant_stamina",
        concept_id="concept_stamina",
        label="Stamina",
        normalized_label="stamina",
        variant_type=TermVariantType.PRIMARY,
        status=TermVariantStatus.ACTIVE,
        created_at="2026-06-25T00:00:00Z",
    )

    with open_database(db_path) as connection:
        repository = ConceptRepository(connection)
        repository.upsert_concept(concept)
        repository.upsert_variant(variant)
        loaded = repository.get_concept("concept_stamina")
        raw = cast(
            "sqlite3.Row | None",
            connection.execute(
            "select tags_json, variants_json from concepts where id = ?",
            ("concept_stamina",),
            ).fetchone(),
        )

    assert loaded == concept
    row = require_row(raw)
    assert text_cell(row, "tags_json") == '["combat","resource"]'
    assert text_cell(row, "variants_json") == '["variant_stamina"]'


def test_document_repository_when_upserting_document_with_chunk_reads_both(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    document = Document(
        id="doc_design",
        path="docs/design.md",
        title="Design",
        content_hash="hashhashhashhash",
        mime_type=DocumentMimeType.MARKDOWN,
        chunk_ids=("chunk_intro",),
        analyzed_at="2026-06-25T00:00:00Z",
        raw_text="Stamina gates dungeon entry.",
        status=DocumentStatus.ANALYZED,
    )
    chunk = DocumentChunk(
        id="chunk_intro",
        document_id="doc_design",
        section_title="Intro",
        ordinal=0,
        text_preview="Stamina gates dungeon entry.",
        content_hash="chunkhashhashhash",
    )

    with open_database(db_path) as connection:
        repository = DocumentRepository(connection)
        repository.upsert_document(document)
        repository.upsert_chunk(chunk)

        loaded_document = repository.get_document("doc_design")
        loaded_chunks = repository.list_chunks("doc_design")

    assert loaded_document == document
    assert loaded_chunks == (chunk,)


def test_issue_repository_when_upserting_issue_reads_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    evidence = IssueEvidence(
        id="evidence_quote",
        kind=IssueEvidenceKind.QUOTE,
        source_document_id="doc_design",
        chunk_id="chunk_intro",
        quote="Stamina is also a character stat.",
        context_before="",
        context_after="",
        confidence=0.75,
    )
    issue = TermIssue(
        id="issue_stamina",
        issue_type=TermIssueType.SAME_TERM_DIFFERENT_MEANING,
        status=IssueStatus.OPEN,
        surface="Stamina",
        candidate_concept_id="concept_stamina",
        target_concept_id=None,
        evidence=(evidence,),
        created_at="2026-06-25T00:00:00Z",
        resolved_at=None,
        version=0,
        applied_idempotency_key=None,
    )

    with open_database(db_path) as connection:
        concept_repository = ConceptRepository(connection)
        concept_repository.upsert_concept(
            Concept(
                id="concept_stamina",
                primary_term="Stamina",
                definition="A resource spent to enter dungeons.",
                term_type=ConceptTermType.RESOURCE,
                status=ConceptStatus.ACTIVE,
                tags=("combat",),
                variant_ids=(),
                created_at="2026-06-25T00:00:00Z",
                updated_at="2026-06-25T00:00:00Z",
            ),
        )
        document_repository = DocumentRepository(connection)
        document_repository.upsert_document(
            Document(
                id="doc_design",
                path="docs/design.md",
                title="Design",
                content_hash="hashhashhashhash",
                mime_type=DocumentMimeType.MARKDOWN,
                chunk_ids=("chunk_intro",),
                analyzed_at="2026-06-25T00:00:00Z",
                raw_text="Stamina is also a character stat.",
                status=DocumentStatus.ANALYZED,
            ),
        )
        document_repository.upsert_chunk(
            DocumentChunk(
                id="chunk_intro",
                document_id="doc_design",
                section_title="Intro",
                ordinal=0,
                text_preview="Stamina is also a character stat.",
                content_hash="chunkhashhashhash",
            ),
        )
        repository = IssueRepository(connection)
        repository.upsert_issue(issue)
        loaded = repository.get_issue("issue_stamina")

    assert loaded == issue


@pytest.fixture
def connection(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def test_concept_physical_name_round_trips(connection: sqlite3.Connection) -> None:
    repo = ConceptRepository(connection)
    concept = Concept(
        id="concept_hp",
        primary_term="체력",
        definition="캐릭터의 생명 수치",
        term_type=ConceptTermType.STAT,
        status=ConceptStatus.ACTIVE,
        created_at="2026-06-29T00:00:00Z",
        updated_at="2026-06-29T00:00:00Z",
        physical_name="hp",
    )
    repo.upsert_concept(concept)

    loaded = repo.get_concept("concept_hp")
    assert loaded is not None
    assert loaded.physical_name == "hp"
