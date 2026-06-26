"""Validate deterministic MVP sample fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]

ROOT: Final = Path(__file__).resolve().parents[2]
DOCS_DIR: Final = ROOT / "samples" / "docs"
EXPECTED_DIR: Final = ROOT / "samples" / "expected"
CONTRACTS_DIR: Final = ROOT / "contracts"
MAX_QUOTE_CHARS: Final = 96
EXPECTED_ISSUE_TYPES: Final = {
    "same_term_different_meaning",
    "same_meaning_different_term",
}
ISSUE_TYPE_TO_CONTRACT_TYPE: Final = {
    "same_term_different_meaning": "conflicting_definition",
    "same_meaning_different_term": "alias_candidate",
}
FIXTURE_CREATED_AT: Final = "2026-06-25T00:00:00Z"
FORBIDDEN_PROVIDER_MARKERS: Final = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "api_key",
    "gpt-",
    "claude-",
    "gemini-",
)


def load_json_object(path: Path) -> JsonObject:
    data = cast("JsonValue", json.loads(path.read_text(encoding="utf-8")))
    assert isinstance(data, dict), f"{path} must contain a JSON object"
    return data


def text_field(record: JsonObject, key: str) -> str:
    value = record[key]
    assert isinstance(value, str), f"{key} must be a string"
    return value


def optional_text_field(record: JsonObject, key: str) -> str | None:
    value = record.get(key)
    assert value is None or isinstance(value, str), f"{key} must be a string or null"
    return value


def object_list(record: JsonObject, key: str) -> list[JsonObject]:
    value = record[key]
    assert isinstance(value, list), f"{key} must be a list"
    objects: list[JsonObject] = []
    for item in value:
        assert isinstance(item, dict), f"{key} entries must be objects"
        objects.append(item)
    return objects


def text_list(record: JsonObject, key: str) -> list[str]:
    value = record[key]
    assert isinstance(value, list), f"{key} must be a list"
    items: list[str] = []
    for item in value:
        assert isinstance(item, str), f"{key} entries must be strings"
        items.append(item)
    return items


def schema_string_set(schema: JsonObject, property_name: str, key: str) -> set[str]:
    properties = schema["properties"]
    assert isinstance(properties, dict)
    property_schema = properties[property_name]
    assert isinstance(property_schema, dict)
    values = property_schema[key]
    assert isinstance(values, list)
    result: set[str] = set()
    for value in values:
        assert isinstance(value, str)
        result.add(value)
    return result


def schema_required_fields(schema: JsonObject) -> set[str]:
    values = schema["required"]
    assert isinstance(values, list)
    fields: set[str] = set()
    for value in values:
        assert isinstance(value, str)
        fields.add(value)
    return fields


def schema_pattern(schema: JsonObject, property_name: str) -> str:
    properties = schema["properties"]
    assert isinstance(properties, dict)
    property_schema = properties[property_name]
    assert isinstance(property_schema, dict)
    pattern = property_schema["pattern"]
    assert isinstance(pattern, str)
    return pattern


def contract_id(value: str, prefix: str) -> str:
    return f"{prefix}_{value.removeprefix(prefix).replace('.', '_')}"


def contract_issue_from_fixture(issue: JsonObject) -> JsonObject:
    """Convert semantic fixture issues to the frozen TermIssue contract shape."""
    semantic_type = text_field(issue, "issue_type")
    evidence_items: list[JsonValue] = []
    issue_id_slug = text_field(issue, "issue_id").replace(".", "_")
    for index, evidence in enumerate(object_list(issue, "evidence"), start=1):
        evidence_items.append(
            {
                "id": f"evidence_{issue_id_slug}_{index}",
                "kind": "quote",
                "sourceDocumentId": contract_id(
                    text_field(evidence, "document_id"),
                    "doc",
                ),
                "quote": text_field(evidence, "quote"),
                "confidence": 1,
            }
        )

    concept_ids = text_list(issue, "concept_ids")
    return {
        "id": contract_id(text_field(issue, "issue_id"), "issue"),
        "issueType": ISSUE_TYPE_TO_CONTRACT_TYPE[semantic_type],
        "status": "open",
        "surface": text_field(issue, "candidate_term"),
        "candidateConceptId": contract_id(concept_ids[0], "concept"),
        "targetConceptId": contract_id(concept_ids[-1], "concept"),
        "evidence": evidence_items,
        "createdAt": FIXTURE_CREATED_AT,
        "resolvedAt": None,
        "version": 0,
        "appliedIdempotencyKey": None,
    }


def assert_matches_term_issue_schema(issue: JsonObject, schema: JsonObject) -> None:
    assert set(issue) <= set(schema_required_fields(schema)) | {
        "candidateConceptId",
        "targetConceptId",
        "resolvedAt",
        "appliedIdempotencyKey",
    }
    assert schema_required_fields(schema) <= set(issue)
    assert re.fullmatch(schema_pattern(schema, "id"), text_field(issue, "id"))
    assert text_field(issue, "issueType") in schema_string_set(
        schema,
        "issueType",
        "enum",
    )
    assert text_field(issue, "status") in schema_string_set(schema, "status", "enum")
    assert 1 <= len(text_field(issue, "surface")) <= 160
    for concept_key in ("candidateConceptId", "targetConceptId"):
        concept_id = optional_text_field(issue, concept_key)
        assert concept_id is not None
        assert re.fullmatch(schema_pattern(schema, concept_key), concept_id)
    assert text_field(issue, "createdAt") == FIXTURE_CREATED_AT
    assert isinstance(issue["version"], int)


def assert_bounded_evidence(issue: JsonObject, docs_by_path: JsonObject) -> None:
    for evidence in object_list(issue, "evidence"):
        quote = text_field(evidence, "quote")
        path = text_field(evidence, "path")
        document_text = text_field(docs_by_path, path)

        assert 0 < len(quote) <= MAX_QUOTE_CHARS
        assert quote in document_text
        assert quote.strip() != document_text.strip()
        assert "raw_document" not in evidence


def assert_rejects_full_document_evidence(
    issue: JsonObject,
    docs_by_path: JsonObject,
) -> None:
    try:
        assert_bounded_evidence(issue, docs_by_path)
    except AssertionError:
        return
    message = "full document evidence was accepted"
    raise AssertionError(message)


def issue_types(issues: Iterable[JsonObject]) -> set[str]:
    found: set[str] = set()
    for issue in issues:
        found.add(text_field(issue, "issue_type"))
    return found


def test_sample_docs_exist_and_are_utf8() -> None:
    required_terms = {
        "combat_core.md": ("스태미나", "경직", "스턴"),
        "dungeon_draft.md": ("스태미나", "입장 피로도", "입장권"),
        "ui_terms.md": ("스태미나", "입장 피로도", "던전 입장"),
    }

    for filename, terms in required_terms.items():
        text = (DOCS_DIR / filename).read_text(encoding="utf-8")
        assert text.startswith("# ")
        for term in terms:
            assert term in text


def test_expected_json_files_parse_and_use_deterministic_mock_provider() -> None:
    expected_files = ("term_candidates.json", "issues.json", "graph.json")

    for filename in expected_files:
        payload = load_json_object(EXPECTED_DIR / filename)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        assert payload["fixture_version"] == 1
        assert payload["provider"] == "deterministic_mock"
        for marker in FORBIDDEN_PROVIDER_MARKERS:
            assert marker not in serialized


def test_expected_issue_types_counts_and_recommendations() -> None:
    payload = load_json_object(EXPECTED_DIR / "issues.json")
    summary = payload["summary"]
    assert isinstance(summary, dict)
    counts = summary["counts_by_type"]
    assert isinstance(counts, dict)
    issues = object_list(payload, "issues")

    assert summary["total"] == 2
    assert counts["same_term_different_meaning"] == 1
    assert counts["same_meaning_different_term"] == 1
    assert issue_types(issues) == EXPECTED_ISSUE_TYPES
    for issue in issues:
        assert text_field(issue, "recommendation")


def test_evidence_quotes_are_bounded_and_do_not_embed_full_documents() -> None:
    docs_by_path: JsonObject = {
        f"samples/docs/{path.name}": path.read_text(encoding="utf-8")
        for path in DOCS_DIR.glob("*.md")
    }
    issues = object_list(load_json_object(EXPECTED_DIR / "issues.json"), "issues")

    for issue in issues:
        assert_bounded_evidence(issue, docs_by_path)

    full_document_issue: JsonObject = {
        "evidence": [
            {
                "path": "samples/docs/combat_core.md",
                "quote": text_field(docs_by_path, "samples/docs/combat_core.md"),
            },
        ],
    }
    assert_rejects_full_document_evidence(full_document_issue, docs_by_path)


def test_graph_projection_contains_expected_nodes_and_issue_edges() -> None:
    payload = load_json_object(EXPECTED_DIR / "graph.json")
    graph = payload["graph"]
    assert isinstance(graph, dict)
    nodes = object_list(graph, "nodes")
    edges = object_list(graph, "edges")

    node_ids = {text_field(node, "id") for node in nodes}
    edge_issue_ids = {
        text_field(edge, "issue_id") for edge in edges if "issue_id" in edge
    }

    assert {
        "concept.combat_stamina",
        "concept.dungeon_entry_resource",
        "term.stamina",
        "term.entry_fatigue",
    } <= node_ids
    assert edge_issue_ids == {
        "issue.same-term.stamina.combat-vs-entry",
        "issue.same-meaning.entry-resource.stamina-fatigue",
    }


def test_fixture_issues_convert_to_term_issue_contract_schema() -> None:
    term_issue_schema = load_json_object(
        CONTRACTS_DIR / "schemas" / "term_issue.schema.json",
    )
    issue_evidence_schema = load_json_object(
        CONTRACTS_DIR / "schemas" / "issue_evidence.schema.json"
    )
    issues = object_list(load_json_object(EXPECTED_DIR / "issues.json"), "issues")

    assert issue_types(issues) == EXPECTED_ISSUE_TYPES
    for issue in issues:
        contract_issue = contract_issue_from_fixture(issue)
        assert_matches_term_issue_schema(contract_issue, term_issue_schema)
        for evidence in object_list(contract_issue, "evidence"):
            assert re.fullmatch(
                schema_pattern(issue_evidence_schema, "id"),
                text_field(evidence, "id"),
            )
            assert text_field(evidence, "kind") in schema_string_set(
                issue_evidence_schema,
                "kind",
                "enum",
            )
            assert re.fullmatch(
                schema_pattern(issue_evidence_schema, "sourceDocumentId"),
                text_field(evidence, "sourceDocumentId"),
            )
            assert 0 < len(text_field(evidence, "quote")) <= MAX_QUOTE_CHARS


def test_contract_schema_discovery_uses_nested_schema_directory() -> None:
    schema_paths = sorted((CONTRACTS_DIR / "schemas").glob("*.schema.json"))

    assert CONTRACTS_DIR / "schemas" / "term_issue.schema.json" in schema_paths
    assert CONTRACTS_DIR / "schemas" / "issue_evidence.schema.json" in schema_paths
