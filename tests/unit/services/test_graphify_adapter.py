import json
from pathlib import Path

from tests.unit.services.test_graph_projection_service import seed_graph_fixture

from doc2dic.services.graph_projection_service import GraphProjectionService
from doc2dic.services.graphify_adapter import (
    GRAPHIFY_EXECUTABLE_NAME,
    GRAPHIFY_PACKAGE_NAME,
    GRAPHIFY_SCHEMA_DESCRIPTION,
    PINNED_GRAPHIFY_VERSION,
    GraphifyAdapter,
)
from doc2dic.services.graphify_export_service import GraphifyRuntime
from doc2dic.storage import initialize_project_storage, open_database


def test_graphify_adapter_when_fixture_projected_builds_bounded_projection(
    tmp_path: Path,
) -> None:
    db_path = initialize_project_storage(tmp_path)
    with open_database(db_path) as connection:
        seed_graph_fixture(connection)
        graph = GraphProjectionService(connection).current_graph()

        projection = GraphifyAdapter(connection).projection_for_graph(graph)
        extraction = GraphifyAdapter(connection).extraction_for_graph(graph)

    assert GRAPHIFY_PACKAGE_NAME == "graphifyy"
    assert GRAPHIFY_EXECUTABLE_NAME == "graphify"
    assert PINNED_GRAPHIFY_VERSION == "0.4.29"
    assert "id,label,file_type,source_file" in GRAPHIFY_SCHEMA_DESCRIPTION
    assert projection.graph == graph
    assert [document.path for document in projection.documents] == [
        "glossary_export/concepts/concept_combat_stamina.md",
        "glossary_export/concepts/concept_dodge_roll.md",
        "glossary_export/concepts/concept_entry_stamina.md",
    ]
    assert "Resource spent by combat actions." in projection.documents[0].body
    assert len(projection.documents[0].body) <= 4000
    assert json.loads(extraction.model_dump_json())["nodes"][0] == {
        "id": "concept_combat_stamina",
        "label": "combat.stamina",
        "file_type": "document",
        "source_file": "glossary_export/concepts/concept_combat_stamina.md",
        "source_location": None,
    }
    assert json.loads(extraction.model_dump_json())["edges"][0] == {
        "source": "concept_combat_stamina",
        "target": "concept_combat_stamina",
        "relation": "alias_of",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "glossary_export/concepts/concept_combat_stamina.md",
        "source_location": None,
        "weight": 1.0,
    }


def test_graphify_runtime_when_executable_missing_reports_unavailable() -> None:
    status = GraphifyRuntime(executable_name="doc2dic-missing-graphify").detect()

    assert not status.available
    assert status.package_name == GRAPHIFY_PACKAGE_NAME
    assert status.executable_name == "doc2dic-missing-graphify"
    assert status.version is None
    assert status.reason == "graphify executable not found on PATH"
