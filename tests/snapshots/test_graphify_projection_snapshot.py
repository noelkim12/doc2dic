import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tests.unit.services.test_graph_projection_service import seed_graph_fixture

from doc2dic.services.graphify_export_service import GraphifyExportService
from doc2dic.storage import initialize_project_storage, open_database


@dataclass(frozen=True, slots=True)
class ExpectedConceptBody:
    concept_id: str
    title: str
    term_type: str
    definition: str
    tags: tuple[str, ...]
    variants: tuple[str, ...]


def test_graphify_export_when_repeated_has_stable_projection_and_corpus(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)
    with open_database(db_path) as connection:
        seed_graph_fixture(connection)
        first = GraphifyExportService(connection, tmp_path).export_graphify()
        second = GraphifyExportService(connection, tmp_path).export_graphify()

    projection = cast(
        "dict[str, object]",
        json.loads((first.snapshot_dir / "graphify_projection.json").read_text()),
    )
    extraction = cast(
        "dict[str, object]",
        json.loads((first.snapshot_dir / "graphify_extraction.json").read_text()),
    )

    assert first.snapshot_dir == second.snapshot_dir
    assert projection == {
        "graph": _expected_graph_body(),
        "documents": [
            {
                "path": "glossary_export/concepts/concept_combat_stamina.md",
                "title": "combat.stamina",
                "body": _concept_body(
                    ExpectedConceptBody(
                        concept_id="concept_combat_stamina",
                        title="combat.stamina",
                        term_type="resource",
                        definition="Resource spent by combat actions.",
                        tags=("combat",),
                        variants=(
                            "combat.stamina (primary, active)",
                            "STA (alias, active)",
                        ),
                    ),
                ),
            },
            {
                "path": "glossary_export/concepts/concept_dodge_roll.md",
                "title": "Dodge Roll",
                "body": _concept_body(
                    ExpectedConceptBody(
                        concept_id="concept_dodge_roll",
                        title="Dodge Roll",
                        term_type="action",
                        definition="Movement action that spends stamina.",
                        tags=("combat",),
                        variants=("Dodge Roll (primary, active)",),
                    ),
                ),
            },
            {
                "path": "glossary_export/concepts/concept_entry_stamina.md",
                "title": "Entry Stamina",
                "body": _concept_body(
                    ExpectedConceptBody(
                        concept_id="concept_entry_stamina",
                        title="Entry Stamina",
                        term_type="resource",
                        definition="Resource spent to enter a dungeon.",
                        tags=("economy",),
                        variants=("Entry Stamina (primary, active)",),
                    ),
                ),
            },
        ],
    }
    assert extraction["input_tokens"] == 0
    assert extraction["output_tokens"] == 0
    assert (first.snapshot_dir / "app_graph.json").exists()
    documents = cast("list[dict[str, str]]", projection["documents"])
    assert (
        first.snapshot_dir
        / "glossary_export"
        / "concepts"
        / "concept_combat_stamina.md"
    ).read_text(encoding="utf-8") == documents[0]["body"]


def _concept_body(expected: ExpectedConceptBody) -> str:
    tag_lines = "\n".join(f"- {tag}" for tag in expected.tags)
    variant_lines = "\n".join(f"- {variant}" for variant in expected.variants)
    return (
        "---\n"
        f"id: {expected.concept_id}\n"
        "type: concept\n"
        "status: active\n"
        f"term_type: {expected.term_type}\n"
        "---\n\n"
        f"# {expected.title}\n\n"
        "## Definition\n\n"
        f"{expected.definition}\n\n"
        "## Tags\n\n"
        f"{tag_lines}\n\n"
        "## Variants\n\n"
        f"{variant_lines}\n"
    )


def _expected_graph_body() -> dict[str, object]:
    return {
        "nodes": [
            {
                "id": "concept_combat_stamina",
                "label": "combat.stamina",
                "nodeType": "concept",
                "termType": "resource",
            },
            {
                "id": "concept_dodge_roll",
                "label": "Dodge Roll",
                "nodeType": "concept",
                "termType": "action",
            },
            {
                "id": "concept_entry_stamina",
                "label": "Entry Stamina",
                "nodeType": "concept",
                "termType": "resource",
            },
        ],
        "edges": [
            {
                "id": "edge_57fd1a699b04e044",
                "source": "concept_combat_stamina",
                "target": "concept_combat_stamina",
                "relation": "alias_of",
            },
            {
                "id": "edge_05cf9aad12334eed",
                "source": "concept_combat_stamina",
                "target": "concept_entry_stamina",
                "relation": "contradicts",
            },
            {
                "id": "edge_2344f86414a866c6",
                "source": "concept_combat_stamina",
                "target": "concept_dodge_roll",
                "relation": "depends_on",
            },
            {
                "id": "edge_ff73d3d909435021",
                "source": "concept_dodge_roll",
                "target": "concept_combat_stamina",
                "relation": "derives_from",
            },
            {
                "id": "edge_377971ef0d78dc87",
                "source": "concept_entry_stamina",
                "target": "concept_combat_stamina",
                "relation": "value_of",
            },
        ],
    }
