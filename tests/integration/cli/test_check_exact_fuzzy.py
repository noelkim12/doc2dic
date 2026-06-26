from __future__ import annotations

from textwrap import dedent
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
from doc2dic.storage.connection import open_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row, text_cell

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    import pytest

type CountTable = Literal[
    "document_chunks",
    "documents",
    "term_issues",
    "term_occurrences",
]


def test_check_when_write_issues_detects_exact_fuzzy_and_lifecycle_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    _seed_glossary(tmp_path)
    path = tmp_path / "design.md"
    text = dedent(
        """
        # 설계

        스태미나는 던전에 입장할 때 소모된다.
        입장 피로도가 부족하면 입장할 수 없다.
        금지어와 옛용어도 문서에 남아 있다.
        """,
    ).lstrip()
    _ = path.write_text(
        text,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["check", str(path), "--write-issues"])

    assert init_result.exit_code == 0
    assert result.exit_code == 0
    assert "Occurrences:" in result.output
    assert "Issues written: yes" in result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        counts = _issue_counts(connection)
        occurrence_count = _count(connection, "term_occurrences")
        document_count = _count(connection, "documents")
        quote_row = cast(
            "sqlite3.Row | None",
            connection.execute(
                "select quote from issue_evidence order by id limit 1",
            ).fetchone(),
        )

    assert document_count == 1
    assert occurrence_count >= 5
    assert counts["forbidden_term"] == 1
    assert counts["alias_candidate"] >= 1
    assert counts["same_term_different_meaning"] == 1
    assert counts["same_meaning_different_term"] == 1
    assert "# 설계" not in text_cell(require_row(quote_row), "quote")


def test_check_when_path_is_unsupported_does_not_write_partial_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    _seed_glossary(tmp_path)
    pdf_path = tmp_path / "design.pdf"
    _ = pdf_path.write_bytes(b"%PDF-1.7 fake")

    result = runner.invoke(app, ["check", str(pdf_path), "--write-issues"])

    assert init_result.exit_code == 0
    assert result.exit_code == 2
    assert "Unsupported document format" in result.output
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _count(connection, "documents") == 0
        assert _count(connection, "document_chunks") == 0
        assert _count(connection, "term_occurrences") == 0
        assert _count(connection, "term_issues") == 0


def _seed_glossary(project_root: Path) -> None:
    with open_database(project_root / ".doc2dic" / "glossary.sqlite3") as connection:
        repository = ConceptRepository(connection)
        for concept in _concepts():
            repository.upsert_concept(concept)
        for variant in _variants():
            repository.upsert_variant(variant)


def _concepts() -> tuple[Concept, ...]:
    created_at = "2026-06-25T00:00:00Z"
    return (
        Concept(
            id="concept_combat_stamina",
            primary_term="스태미나",
            definition="전투 행동에 소모되는 자원.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            variant_ids=("variant_combat_stamina",),
            created_at=created_at,
            updated_at=created_at,
        ),
        Concept(
            id="concept_entry_resource",
            primary_term="입장 피로도",
            definition="던전 입장에 소모되는 자원.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            variant_ids=("variant_entry_fatigue", "variant_entry_stamina"),
            created_at=created_at,
            updated_at=created_at,
        ),
        Concept(
            id="concept_forbidden",
            primary_term="금지어",
            definition="사용하면 안 되는 용어.",
            term_type=ConceptTermType.UNKNOWN,
            status=ConceptStatus.FORBIDDEN,
            created_at=created_at,
            updated_at=created_at,
        ),
        Concept(
            id="concept_deprecated",
            primary_term="옛용어",
            definition="교체가 필요한 용어.",
            term_type=ConceptTermType.UNKNOWN,
            status=ConceptStatus.DEPRECATED,
            created_at=created_at,
            updated_at=created_at,
        ),
    )


def _variants() -> tuple[TermVariant, ...]:
    created_at = "2026-06-25T00:00:00Z"
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
        TermVariant(
            id="variant_deprecated",
            concept_id="concept_deprecated",
            label="옛용어",
            normalized_label=normalize_term_text("옛용어"),
            variant_type=TermVariantType.DEPRECATED,
            status=TermVariantStatus.DEPRECATED,
            created_at=created_at,
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
        created_at="2026-06-25T00:00:00Z",
    )


def _issue_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            "select issue_type, count(*) as count from term_issues group by issue_type",
        ).fetchall(),
    )
    return {text_cell(row, "issue_type"): int_cell(row, "count") for row in rows}


def _count(connection: sqlite3.Connection, table: CountTable) -> int:
    match table:
        case "document_chunks":
            query = "select count(*) as count from document_chunks"
        case "documents":
            query = "select count(*) as count from documents"
        case "term_issues":
            query = "select count(*) as count from term_issues"
        case "term_occurrences":
            query = "select count(*) as count from term_occurrences"
    row = cast(
        "sqlite3.Row | None",
        connection.execute(query).fetchone(),
    )
    return int_cell(require_row(row), "count")
