from pathlib import Path

from doc2dic.mcp.tools import (
    run_doc2dic_create_concept,
    run_doc2dic_delete_concept,
    run_doc2dic_update_concept,
)
from doc2dic.storage.migrations import migrate_database


def _init_project(tmp_path: Path) -> str:
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    return str(tmp_path)


def test_create_concept_succeeds_and_reports_id(tmp_path: Path) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="플레이어 생존 수치",
        physical_name="hp",
        project_path=project,
    )

    assert "# doc2dic concept created" in response
    assert "concept_" in response
    assert "hp" in response


def test_create_concept_duplicate_physical_name_returns_guidance(
    tmp_path: Path,
) -> None:
    project = _init_project(tmp_path)
    _ = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        physical_name="hp",
        project_path=project,
    )

    response = run_doc2dic_create_concept(
        primary_term="생명력",
        definition="다른 정의",
        physical_name="HP",
        project_path=project,
    )

    assert "# doc2dic MCP guidance" in response
    assert "duplicate" in response


def test_create_concept_invalid_physical_name_returns_guidance(
    tmp_path: Path,
) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        physical_name="2hp",
        project_path=project,
    )

    assert "invalid input" in response


def test_create_concept_missing_project_returns_guidance(tmp_path: Path) -> None:
    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=str(tmp_path),
    )

    assert "not initialized" in response


def test_update_concept_changes_definition(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="옛 정의",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_update_concept(
        concept_id=concept_id,
        definition="새 정의",
        project_path=project,
    )

    assert "# doc2dic concept updated" in response
    assert concept_id in response


def test_update_concept_not_found_returns_guidance(tmp_path: Path) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_update_concept(
        concept_id="concept_missing",
        definition="x",
        project_path=project,
    )

    assert "not found" in response
    assert "concept_missing" in response


def test_delete_concept_requires_confirm(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_delete_concept(
        concept_id=concept_id,
        confirm=False,
        project_path=project,
    )

    assert "not performed" in response
    assert "confirm" in response


def test_delete_concept_with_confirm_succeeds(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_delete_concept(
        concept_id=concept_id,
        confirm=True,
        project_path=project,
    )

    assert "# doc2dic concept deleted" in response
    assert concept_id in response


def _extract_concept_id(text: str) -> str:
    for token in text.replace("`", " ").split():
        if token.startswith("concept_"):
            return token
    msg = f"no concept id in: {text}"
    raise AssertionError(msg)
