from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.storage import open_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row, text_cell

if TYPE_CHECKING:
    import sqlite3

    import pytest

type CountTable = Literal["documents", "issue_evidence", "term_occurrences"]


ROOT = Path(__file__).resolve().parents[3]
CREATED_AT = "2026-06-25T00:00:00Z"


def test_analyze_command_when_sample_doc_runs_persists_conflict_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    _seed_glossary(tmp_path)

    result = runner.invoke(
        app,
        ["analyze", str(ROOT / "samples" / "docs" / "dungeon_draft.md")],
    )

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Provider: deterministic_mock" in result.output
    assert "Issues written: yes" in result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        counts = _issue_counts(connection)
        evidence_count = _evidence_count(connection)
    assert counts["same_term_different_meaning"] >= 1
    assert counts["same_meaning_different_term"] >= 1
    assert evidence_count >= 2


def test_check_write_issues_when_enhanced_runs_provider_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    _seed_glossary(tmp_path)

    result = runner.invoke(
        app,
        [
            "check",
            str(ROOT / "samples" / "docs" / "dungeon_draft.md"),
            "--write-issues",
        ],
    )

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Issues written: yes" in result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        counts = _issue_counts(connection)
        document_count = _table_count(connection, "documents")
        occurrence_count = _table_count(connection, "term_occurrences")
    assert document_count == 1
    assert occurrence_count >= 4
    assert counts["same_term_different_meaning"] >= 1
    assert counts["same_meaning_different_term"] >= 1


def _seed_glossary(project_root: Path) -> None:
    with open_database(project_root / ".doc2dic" / "glossary.sqlite3") as connection:
        repository = ConceptRepository(connection)
        for concept in _concepts():
            repository.upsert_concept(concept)
        for variant in _variants():
            repository.upsert_variant(variant)


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


def _issue_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select issue_type, count(*) as count from term_issues group by issue_type",
        ).fetchall(),
    )
    return {
        text_cell(row, "issue_type"): int_cell(row, "count")
        for row in rows
    }


def _evidence_count(connection: sqlite3.Connection) -> int:
    return _table_count(connection, "issue_evidence")


def _table_count(connection: sqlite3.Connection, table: CountTable) -> int:
    match table:
        case "documents":
            query = "select count(*) as count from documents"
        case "issue_evidence":
            query = "select count(*) as count from issue_evidence"
        case "term_occurrences":
            query = "select count(*) as count from term_occurrences"
    row = cast(
        "sqlite3.Row | None",
        connection.execute(query).fetchone(),
    )
    return int_cell(require_row(row), "count")
