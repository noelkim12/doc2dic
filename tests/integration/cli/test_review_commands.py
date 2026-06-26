from pathlib import Path

import pytest
from typer.testing import CliRunner

from doc2dic.cli import app
from doc2dic.domain import IssueEvidence, IssueEvidenceKind, TermIssue, TermIssueType
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage import open_database
from doc2dic.storage.repositories.issues import IssueRepository


def test_review_commands_when_issue_resolved_as_new_concept_create_one_concept(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init"])
    _seed_issue(tmp_path, "issue_stamina", "Stamina")

    list_result = runner.invoke(app, ["review", "list"])
    show_result = runner.invoke(app, ["review", "show", "issue_stamina"])
    resolve_result = runner.invoke(
        app,
        [
            "review",
            "resolve-as-new-concept",
            "issue_stamina",
            "--expected-version",
            "0",
            "--idempotency-key",
            "cli-new-1",
            "--term",
            "Stamina",
            "--definition",
            "Resource spent to enter dungeons.",
        ],
    )
    replay_result = runner.invoke(
        app,
        [
            "review",
            "resolve-as-new-concept",
            "issue_stamina",
            "--expected-version",
            "0",
            "--idempotency-key",
            "cli-new-1",
            "--term",
            "Stamina",
            "--definition",
            "Resource spent to enter dungeons.",
        ],
    )

    assert init_result.exit_code == 0
    assert list_result.exit_code == 0
    assert "issue_stamina\topen\tStamina" in list_result.output
    assert show_result.exit_code == 0
    assert "Version: 0" in show_result.output
    assert resolve_result.exit_code == 0
    assert "Review action applied: issue_stamina" in resolve_result.output
    assert replay_result.exit_code == 0
    assert "Review action already_applied: issue_stamina" in replay_result.output


def test_review_dismiss_when_stale_version_returns_concise_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    _ = runner.invoke(app, ["init"])
    _seed_issue(tmp_path, "issue_noise", "Noise")

    result = runner.invoke(
        app,
        [
            "review",
            "dismiss",
            "issue_noise",
            "--expected-version",
            "4",
            "--idempotency-key",
            "cli-dismiss-stale",
            "--reason",
            "not relevant",
        ],
    )

    assert result.exit_code != 0
    assert "Error: Issue version changed" in result.output
    assert "Traceback" not in result.output


def _seed_issue(tmp_path: Path, issue_id: str, surface: str) -> None:
    with open_database(tmp_path / ".doc2dic" / "glossary.sqlite3") as connection:
        issue = TermIssue(
                id=issue_id,
                issue_type=TermIssueType.UNKNOWN_TERM,
                status=IssueStatus.OPEN,
                surface=surface,
                evidence=(
                    IssueEvidence(
                        id=f"evidence_{issue_id.removeprefix('issue_')}",
                        kind=IssueEvidenceKind.QUOTE,
                        source_document_id="doc_cli_seed",
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
                    "doc_cli_seed",
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
