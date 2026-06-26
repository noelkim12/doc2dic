from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import sqlite3

from doc2dic.context import build_explore_context
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.sqlite_rows import text_cell
from doc2dic.sync import freshness_report, reconcile_project, scan_project


def test_reconcile_when_markdown_changes_clears_stale_banner(tmp_path: Path) -> None:
    # Given: a project with a Markdown evidence file reconciled into storage.
    document_path = tmp_path / "docs" / "combat.md"
    document_path.parent.mkdir()
    _ = document_path.write_text(
        "# Combat\n\n스태미나는 전투 자원이다.\n",
        encoding="utf-8",
    )
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        _ = reconcile_project(connection, tmp_path)

        # When: context is built before and after the evidence file changes.
        fresh_context = build_explore_context(
            "스태미나",
            connection=connection,
            project_root=tmp_path,
        )
        _ = document_path.write_text(
            "# Combat\n\n행동력은 전투 자원이다.\n",
            encoding="utf-8",
        )
        stale_context = build_explore_context(
            "스태미나",
            connection=connection,
            project_root=tmp_path,
        )
        _ = reconcile_project(connection, tmp_path)
        reconciled_context = build_explore_context(
            "행동력",
            connection=connection,
            project_root=tmp_path,
        )

    # Then: only the changed file state shows a stale banner.
    assert "Stale/degraded" not in fresh_context
    assert "Stale/degraded" in stale_context
    assert "docs/combat.md" in stale_context
    assert "content differs from stored hash" in stale_context
    assert "Stale/degraded" not in reconciled_context


def test_reconcile_when_unsupported_files_exist_reports_without_ingestion(
    tmp_path: Path,
) -> None:
    # Given: a project containing supported text plus unsupported binary formats.
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "notes.txt").write_text("스태미나 메모\n", encoding="utf-8")
    _ = (docs_dir / "design.docx").write_bytes(b"PK\x03\x04")
    _ = (docs_dir / "rules.pdf").write_bytes(b"%PDF-1.7")
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        # When: sync scans and reconciles the project.
        before = freshness_report(connection, tmp_path)
        _ = reconcile_project(connection, tmp_path)
        rows = cast(
            "list[sqlite3.Row]",
            connection.execute("select path from documents order by path").fetchall(),
        )

    # Then: unsupported files are reported but never ingested.
    assert tuple(file.path.as_posix() for file in before.unsupported) == (
        "docs/design.docx",
        "docs/rules.pdf",
    )
    assert [text_cell(row, "path") for row in rows] == ["docs/notes.txt"]


def test_reconcile_when_supported_symlink_points_outside_project_skips_ingestion(
    tmp_path: Path,
) -> None:
    # Given: a project-local TXT symlink points at a secret outside the root.
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "notes.txt").write_text("in-root note\n", encoding="utf-8")
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_dir.mkdir()
    outside_document = outside_dir / "secret.txt"
    _ = outside_document.write_text("SECRET_FROM_OUTSIDE\n", encoding="utf-8")
    (docs_dir / "linked.txt").symlink_to(outside_document)
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        # When: sync scans and reconciles the project.
        scan = scan_project(tmp_path)
        _ = reconcile_project(connection, tmp_path)
        rows = cast(
            "list[sqlite3.Row]",
            connection.execute(
                "select path, raw_text from documents order by path",
            ).fetchall(),
        )

    # Then: only in-root supported text is scanned and indexed.
    assert tuple(source.path.as_posix() for source in scan.supported) == (
        "docs/notes.txt",
    )
    assert [text_cell(row, "path") for row in rows] == ["docs/notes.txt"]
    assert all("SECRET_FROM_OUTSIDE" not in text_cell(row, "raw_text") for row in rows)
