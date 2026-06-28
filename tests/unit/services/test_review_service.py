from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pytest

from doc2dic.domain import (
    ConceptTermType,
    IssueEvidence,
    IssueEvidenceKind,
    TermIssue,
    TermIssueType,
)
from doc2dic.services.glossary_service import CreateConceptInput, GlossaryService
from doc2dic.services.review_service import (
    ReviewActionInput,
    ReviewService,
    ReviewServiceError,
    ReviewServiceErrorCode,
)
from doc2dic.services.review_state_machine import IssueStatus, ReviewAction
from doc2dic.storage import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.repositories.issues import IssueRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3


def test_list_show_and_dismiss_when_issue_open_updates_state(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        issue = _seed_issue(connection, "issue_stamina", "Stamina")
        service = ReviewService(connection)

        listed = service.list_issues(status=IssueStatus.OPEN)
        shown = service.get_issue(issue.id)
        result = service.apply_action(
            issue.id,
            ReviewActionInput(ReviewAction.DISMISS, 0, "dismiss-1", reason="noise"),
        )

        assert tuple(item.id for item in listed) == (issue.id,)
        assert shown.surface == "Stamina"
        assert result.issue.status is IssueStatus.DISMISSED
        assert result.issue.version == 1


def test_resolve_new_concept_when_replayed_is_idempotent(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        issue = _seed_issue(connection, "issue_energy", "Energy")
        service = ReviewService(connection)
        command = ReviewActionInput(
            ReviewAction.RESOLVE_AS_NEW_CONCEPT,
            0,
            "new-1",
            term="Energy",
            definition="Resource spent on actions.",
        )

        first = service.apply_action(issue.id, command)
        replay = service.apply_action(issue.id, command)

        assert first.outcome == "applied"
        assert first.concept is not None
        assert first.concept.id.startswith("concept_")
        assert replay.outcome == "already_applied"
        assert _count(connection, "concepts") == 1
        assert _count(connection, "term_variants") == 1


def test_resolve_alias_and_forbidden_when_valid_create_expected_variants(
    tmp_path: Path,
) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        concept = GlossaryService(connection).create_concept(
            CreateConceptInput("Health", "Hit points.", ConceptTermType.STAT),
        )
        alias_issue = _seed_issue(connection, "issue_hp", "HP")
        forbidden_issue = _seed_issue(connection, "issue_life", "Life")
        service = ReviewService(connection)

        alias = service.apply_action(
            alias_issue.id,
            ReviewActionInput(
                ReviewAction.RESOLVE_AS_ALIAS,
                0,
                "alias-1",
                concept_id=concept.id,
                variant="HP",
            ),
        )
        forbidden = service.apply_action(
            forbidden_issue.id,
            ReviewActionInput(
                ReviewAction.RESOLVE_AS_FORBIDDEN,
                0,
                "forbidden-1",
                concept_id=concept.id,
                variant="Life",
            ),
        )

        assert alias.variant is not None
        assert alias.variant.variant_type.value == "alias"
        assert forbidden.variant is not None
        assert forbidden.variant.status.value == "forbidden"


def test_resolve_relation_when_targets_exist_creates_relation(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        glossary = GlossaryService(connection)
        source = glossary.create_concept(
            CreateConceptInput("Sword", "Weapon.", ConceptTermType.ENTITY),
        )
        target = glossary.create_concept(
            CreateConceptInput("Damage", "Health reduction.", ConceptTermType.STAT),
        )
        issue = _seed_issue(connection, "issue_relation", "Sword damage")

        result = ReviewService(connection).apply_action(
            issue.id,
            ReviewActionInput(
                ReviewAction.RESOLVE_AS_RELATION,
                0,
                "relation-1",
                source_concept_id=source.id,
                target_concept_id=target.id,
                relation_type="related_to",
            ),
        )

        assert result.relation is not None
        assert result.relation.source_concept_id == source.id
        assert _count(connection, "concept_relations") == 1


def test_stale_and_closed_issue_when_mutated_raise_conflict_errors(
    tmp_path: Path,
) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        issue = _seed_issue(connection, "issue_stale", "Dash")
        service = ReviewService(connection)

        with pytest.raises(ReviewServiceError) as stale:
            _ = service.apply_action(
                "issue_stale",
                ReviewActionInput(
                    ReviewAction.DISMISS,
                    9,
                    "dismiss-stale",
                    reason="old",
                ),
            )
        _ = service.apply_action(
            issue.id,
            ReviewActionInput(ReviewAction.DISMISS, 0, "dismiss-closed", reason="done"),
        )

        with pytest.raises(ReviewServiceError) as closed:
            _ = service.apply_action(
                "issue_stale",
                ReviewActionInput(
                    ReviewAction.DISMISS,
                    1,
                    "dismiss-new",
                    reason="closed",
                ),
            )

        assert stale.value.code is ReviewServiceErrorCode.STALE_VERSION
        assert closed.value.code is ReviewServiceErrorCode.ISSUE_CLOSED


def test_transaction_rolls_back_when_glossary_effect_fails(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    with open_database(db_path) as connection:
        concept = GlossaryService(connection).create_concept(
            CreateConceptInput("Health", "Hit points.", ConceptTermType.STAT),
        )
        issue = _seed_issue(connection, "issue_duplicate", "Health")

        with pytest.raises(ReviewServiceError) as error:
            _ = ReviewService(connection).apply_action(
                issue.id,
                ReviewActionInput(
                    ReviewAction.RESOLVE_AS_ALIAS,
                    0,
                    "alias-duplicate",
                    concept_id=concept.id,
                    variant="Health",
                ),
            )

        refreshed = ReviewService(connection).get_issue(issue.id)
        assert error.value.code is ReviewServiceErrorCode.DUPLICATE_TERM
        assert refreshed.status is IssueStatus.OPEN
        assert refreshed.version == 0
        assert _count(connection, "term_variants") == 1


def _db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)
    return db_path


def _seed_issue(
    connection: "sqlite3.Connection",
    issue_id: str,
    surface: str,
) -> TermIssue:
    issue = TermIssue(
        id=issue_id,
        issue_type=TermIssueType.UNKNOWN_TERM,
        status=IssueStatus.OPEN,
        surface=surface,
        evidence=(
            IssueEvidence(
                id=f"evidence_{issue_id.removeprefix('issue_')}",
                kind=IssueEvidenceKind.QUOTE,
                source_document_id="doc_seed",
                quote=surface,
                confidence=0.8,
            ),
        ),
        created_at="2026-06-25T00:00:00Z",
    )
    with connection:
        _ = connection.execute(
            """
            insert or ignore into documents(
              id, path, title, content_hash, mime_type, chunk_ids_json, raw_text,
              status, analyzed_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc_seed",
                "seed.md",
                "Seed",
                "hash",
                "text/markdown",
                "[]",
                "",
                "analyzed",
                "2026-06-25T00:00:00Z",
            ),
        )
        IssueRepository(connection).upsert_issue(issue)
    return issue


def _count(
    connection: "sqlite3.Connection",
    table_name: Literal["concepts", "term_variants", "concept_relations"],
) -> int:
    match table_name:
        case "concepts":
            sql = "select count(*) as count from concepts"
        case "term_variants":
            sql = "select count(*) as count from term_variants"
        case "concept_relations":
            sql = "select count(*) as count from concept_relations"
    row = cast("sqlite3.Row | None", connection.execute(sql).fetchone())
    return int_cell(require_row(row), "count")
