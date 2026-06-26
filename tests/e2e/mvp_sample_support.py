from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from tests.integration.server.test_issues_api import request_app

from doc2dic.domain import (
    Concept,
    ConceptStatus,
    ConceptTermType,
    TermVariant,
    TermVariantStatus,
    TermVariantType,
)
from doc2dic.server.app import create_app
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage import open_database
from doc2dic.storage.repositories.concepts import ConceptRepository
from doc2dic.storage.sqlite_rows import int_cell, require_row, text_cell

if TYPE_CHECKING:
    import sqlite3

ROOT = Path(__file__).resolve().parents[2]
CREATED_AT = "2026-06-25T00:00:00Z"

type CountTable = Literal["concept_relations", "documents", "term_variants"]


@dataclass(frozen=True, slots=True)
class IssueIds:
    same_term: str
    same_meaning: str


def seed_sample_base_glossary(project_root: Path) -> None:
    with open_database(project_root / ".doc2dic" / "glossary.sqlite3") as connection:
        repository = ConceptRepository(connection)
        for concept in _sample_concepts():
            repository.upsert_concept(concept)
        for variant in _sample_variants():
            repository.upsert_variant(variant)


def open_issue_ids(project_root: Path) -> IssueIds:
    with open_database(project_root / ".doc2dic" / "glossary.sqlite3") as connection:
        same_term = _issue_id(connection, "same_term_different_meaning")
        same_meaning = _issue_id(connection, "same_meaning_different_term")
    return IssueIds(same_term=same_term, same_meaning=same_meaning)


def assert_graph_contains_split_path(graph_body: dict[str, object]) -> None:
    nodes = cast("list[dict[str, str]]", graph_body["nodes"])
    edges = cast("list[dict[str, str]]", graph_body["edges"])

    assert {node["id"] for node in nodes} >= {
        "concept_combat_stamina",
        "concept_entry_resource",
    }
    assert {
        (edge["source"], edge["relation"], edge["target"])
        for edge in edges
    } >= {
        ("concept_combat_stamina", "contradicts", "concept_entry_resource"),
        ("concept_entry_resource", "alias_of", "concept_entry_resource"),
    }


def assert_api_surfaces_are_contract_safe(project_root: Path) -> None:
    fastapi_app = create_app(project_root=project_root)
    assert "/api/graphs/graphify/import" not in fastapi_app.openapi()["paths"]
    assert not (
        ROOT / "src" / "doc2dic" / "services" / "graphify_import_service.py"
    ).exists()

    concept_response = request_app(
        fastapi_app,
        "get",
        "/api/concepts/concept_entry_resource",
    )
    graph_response = request_app(fastapi_app, "get", "/api/graphs/current")
    concept_body = cast("dict[str, object]", json.loads(concept_response.body))
    graph_body = cast("dict[str, object]", json.loads(graph_response.body))
    variants = cast("list[str]", concept_body["variants"])

    assert concept_response.status_code == 200
    assert graph_response.status_code == 200
    assert concept_body["primaryTerm"] == "던전 입장 자원"
    assert "variant_entry_stamina" in variants
    assert len(variants) == 2
    assert all(isinstance(variant_id, str) for variant_id in variants)
    assert_graph_contains_split_path(graph_body)


def assert_graphify_export_without_runtime(project_root: Path) -> None:
    snapshot_dirs = sorted((project_root / ".doc2dic" / "graph_snapshots").iterdir())
    snapshot_dir = snapshot_dirs[-1]
    runtime_status = cast(
        "dict[str, object]",
        json.loads((snapshot_dir / "runtime_status.json").read_text(encoding="utf-8")),
    )
    projection = cast(
        "dict[str, object]",
        json.loads(
            (snapshot_dir / "graphify_projection.json").read_text(encoding="utf-8"),
        ),
    )
    projection_graph = cast("dict[str, object]", projection["graph"])
    projection_nodes = cast("list[dict[str, object]]", projection_graph["nodes"])
    runtime_available = runtime_status["available"]

    if runtime_available is True:
        assert (snapshot_dir / "graph.html").exists()
    assert runtime_available is False
    assert runtime_status["reason"] == "graphify executable not found on PATH"
    assert (snapshot_dir / "graphify_extraction.json").exists()
    assert len(projection_nodes) >= 2


def assert_review_effects_persisted(project_root: Path) -> None:
    with open_database(project_root / ".doc2dic" / "glossary.sqlite3") as connection:
        assert _count(connection, "documents") == 2
        assert _count(connection, "concept_relations") == 1
        assert _count(connection, "term_variants") == 5


def _sample_concepts() -> tuple[Concept, ...]:
    return (
        Concept(
            id="concept_combat_stamina",
            primary_term="스태미나",
            definition="회피와 강공격에 소모되는 전투 자원.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("combat_resource", "combat"),
            variant_ids=("variant_combat_stamina",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_entry_resource",
            primary_term="던전 입장 자원",
            definition="던전 입장 가능 여부를 결정하는 별도 입장 자원.",
            term_type=ConceptTermType.RESOURCE,
            status=ConceptStatus.ACTIVE,
            tags=("entry_resource",),
            variant_ids=("variant_entry_stamina",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_hitstun",
            primary_term="경직",
            definition="피격 직후 이동과 공격 입력이 제한되는 상태.",
            term_type=ConceptTermType.STATE,
            status=ConceptStatus.ACTIVE,
            tags=("combat_status",),
            variant_ids=("variant_hitstun",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
        Concept(
            id="concept_stun",
            primary_term="스턴",
            definition="강한 충격 누적으로 모든 행동이 불가능한 상태.",
            term_type=ConceptTermType.STATE,
            status=ConceptStatus.ACTIVE,
            tags=("combat_status",),
            variant_ids=("variant_stun",),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        ),
    )


def _sample_variants() -> tuple[TermVariant, ...]:
    return (
        _variant("variant_combat_stamina", "concept_combat_stamina", "스태미나"),
        _variant("variant_entry_stamina", "concept_entry_resource", "스태미나"),
        _variant("variant_hitstun", "concept_hitstun", "경직"),
        _variant("variant_stun", "concept_stun", "스턴"),
    )


def _variant(variant_id: str, concept_id: str, label: str) -> TermVariant:
    return TermVariant(
        id=variant_id,
        concept_id=concept_id,
        label=label,
        normalized_label=normalize_term_text(label),
        variant_type=TermVariantType.PRIMARY,
        status=TermVariantStatus.ACTIVE,
        created_at=CREATED_AT,
    )


def _issue_id(connection: sqlite3.Connection, issue_type: str) -> str:
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            """
            select id from term_issues
            where status = ? and issue_type = ?
            order by id limit 1
            """,
            (IssueStatus.OPEN.value, issue_type),
        ).fetchone(),
    )
    return text_cell(require_row(row), "id")


def _count(connection: sqlite3.Connection, table: CountTable) -> int:
    match table:
        case "concept_relations":
            query = "select count(*) as count from concept_relations"
        case "documents":
            query = "select count(*) as count from documents"
        case "term_variants":
            query = "select count(*) as count from term_variants"
    row = cast("sqlite3.Row | None", connection.execute(query).fetchone())
    return int_cell(require_row(row), "count")
