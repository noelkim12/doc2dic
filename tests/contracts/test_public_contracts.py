# pyright: basic
# ruff: noqa: ANN401, C901, EM101, EM102, PLR0911, PLR0912, TRY003

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas"


class ContractValidationError(AssertionError):
    pass


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / name).open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


SCHEMAS = {
    path.name: load_schema(path.name)
    for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
}


def type_matches(value: Any, expected_type: str) -> bool:
    match expected_type:
        case "object":
            return isinstance(value, dict)
        case "array":
            return isinstance(value, list)
        case "string":
            return isinstance(value, str)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        case "boolean":
            return isinstance(value, bool)
        case "null":
            return value is None
        case unreachable:
            raise ContractValidationError(f"Unsupported schema type: {unreachable}")


def validate_value(value: Any, schema: dict[str, Any]) -> None:
    if "$ref" in schema:
        validate_value(value, SCHEMAS[schema["$ref"]])
        return

    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(type_matches(value, candidate) for candidate in expected):
            raise ContractValidationError(f"Expected one of {expected}, got {value!r}")
    elif isinstance(expected, str) and not type_matches(value, expected):
        raise ContractValidationError(f"Expected {expected}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise ContractValidationError(f"Unexpected enum value: {value!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ContractValidationError("String shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ContractValidationError("String longer than maxLength")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise ContractValidationError(f"Pattern mismatch: {value!r}")

    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractValidationError("Number below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractValidationError("Number above maximum")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractValidationError("Array shorter than minItems")
        serialized_items = {json.dumps(item, sort_keys=True) for item in value}
        if schema.get("uniqueItems") and len(serialized_items) != len(value):
            raise ContractValidationError("Array items are not unique")
        if "items" in schema:
            for item in value:
                validate_value(item, schema["items"])

    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = required.difference(value)
        if missing:
            raise ContractValidationError(f"Missing required keys: {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value).difference(properties)
            if extra:
                raise ContractValidationError(f"Unexpected keys: {sorted(extra)}")
        for key, item in value.items():
            if key in properties:
                validate_value(item, properties[key])


VALID_PAYLOADS: dict[str, dict[str, Any]] = {
    "concept.schema.json": {
        "id": "concept_dash",
        "primaryTerm": "Dash",
        "definition": "A short movement burst.",
        "termType": "action",
        "status": "active",
        "tags": ["movement"],
        "variants": ["variant_dash_alias"],
        "createdAt": "2026-06-25T00:00:00Z",
        "updatedAt": "2026-06-25T00:00:00Z",
    },
    "term_variant.schema.json": {
        "id": "variant_dash_alias",
        "conceptId": "concept_dash",
        "label": "quick step",
        "variantType": "alias",
        "status": "active",
        "createdAt": "2026-06-25T00:00:00Z",
    },
    "document.schema.json": {
        "id": "doc_design",
        "path": "docs/design.md",
        "title": "Design",
        "contentHash": "0123456789abcdef",
        "mimeType": "text/markdown",
        "chunkIds": ["chunk_design_intro"],
        "analyzedAt": "2026-06-25T00:00:00Z",
    },
    "document_chunk.schema.json": {
        "id": "chunk_design_intro",
        "documentId": "doc_design",
        "sectionTitle": "Intro",
        "ordinal": 0,
        "textPreview": "Dash is a short movement burst.",
        "contentHash": "fedcba9876543210",
    },
    "term_occurrence.schema.json": {
        "id": "occ_dash_1",
        "documentId": "doc_design",
        "chunkId": "chunk_design_intro",
        "conceptId": "concept_dash",
        "surface": "Dash",
        "offsetStart": 0,
        "offsetEnd": 4,
        "confidence": 0.95,
    },
    "issue_evidence.schema.json": {
        "id": "evidence_dash_quote",
        "kind": "quote",
        "sourceDocumentId": "doc_design",
        "chunkId": "chunk_design_intro",
        "quote": "Dash is a short movement burst.",
        "confidence": 0.9,
    },
    "term_issue.schema.json": {
        "id": "issue_dash_alias",
        "issueType": "alias_candidate",
        "status": "open",
        "surface": "quick step",
        "candidateConceptId": "concept_dash",
        "targetConceptId": "concept_dash",
        "evidence": [],
        "createdAt": "2026-06-25T00:00:00Z",
        "resolvedAt": None,
        "version": 0,
        "appliedIdempotencyKey": None,
    },
    "issue_action_request.schema.json": {
        "expectedVersion": 0,
        "idempotencyKey": "review-issue-dash-alias-0",
        "action": "resolve_as_alias",
        "conceptId": "concept_dash",
        "variant": "quick step",
    },
    "issue_action_payload.schema.json": {
        "outcome": "applied",
        "issue": {},
        "variantId": "variant_dash_alias",
    },
    "app_graph.schema.json": {
        "nodes": [
            {
                "id": "concept_dash",
                "label": "Dash",
                "nodeType": "concept",
                "termType": "action",
            },
        ],
        "edges": [
            {
                "id": "edge_dash_related",
                "source": "concept_dash",
                "target": "concept_stamina",
                "relation": "related_to",
            },
        ],
    },
    "graph_snapshot.schema.json": {
        "id": "snapshot_current",
        "createdAt": "2026-06-25T00:00:00Z",
        "graph": {},
    },
    "graphify_projection.schema.json": {
        "graph": {},
        "documents": [
            {
                "path": "virtual/dash.md",
                "title": "Dash",
                "body": "# Dash\nA short movement burst.",
            },
        ],
    },
    "llm_term_candidates.schema.json": {
        "candidates": [
            {
                "surface": "Dash",
                "definition": "A short movement burst.",
                "term_type": "action",
                "tags": ["movement"],
                "evidence": [
                    {
                        "quote": "Dash is a short movement burst.",
                        "section_title": "Intro",
                    },
                ],
                "confidence": 0.86,
            },
        ],
    },
    "llm_conflict_classification.schema.json": {
        "classification": "alias_candidate",
        "target_concept_id": "concept_dash",
        "reason": "Both names describe the same movement action.",
        "recommendation": "Add quick step as an alias.",
        "confidence": 0.8,
    },
}
VALID_PAYLOADS["term_issue.schema.json"]["evidence"] = [
    VALID_PAYLOADS["issue_evidence.schema.json"],
]
VALID_PAYLOADS["issue_action_payload.schema.json"]["issue"] = VALID_PAYLOADS[
    "term_issue.schema.json"
]
VALID_PAYLOADS["graph_snapshot.schema.json"]["graph"] = VALID_PAYLOADS[
    "app_graph.schema.json"
]
VALID_PAYLOADS["graphify_projection.schema.json"]["graph"] = VALID_PAYLOADS[
    "app_graph.schema.json"
]


@pytest.mark.parametrize(("schema_name", "payload"), sorted(VALID_PAYLOADS.items()))
def test_valid_contract_payloads(schema_name: str, payload: dict[str, Any]) -> None:
    validate_value(payload, SCHEMAS[schema_name])


def test_invalid_issue_status_is_rejected() -> None:
    payload = copy.deepcopy(VALID_PAYLOADS["term_issue.schema.json"])
    payload["status"] = "pending"
    with pytest.raises(ContractValidationError):
        validate_value(payload, SCHEMAS["term_issue.schema.json"])


@pytest.mark.parametrize(
    "issue_type",
    ["same_term_different_meaning", "same_meaning_different_term", "ambiguous_usage"],
)
def test_plan_issue_types_are_valid(issue_type: str) -> None:
    payload = copy.deepcopy(VALID_PAYLOADS["term_issue.schema.json"])
    payload["issueType"] = issue_type
    validate_value(payload, SCHEMAS["term_issue.schema.json"])


def test_issue_action_request_requires_version_and_idempotency() -> None:
    payload = copy.deepcopy(VALID_PAYLOADS["issue_action_request.schema.json"])
    del payload["expectedVersion"]
    with pytest.raises(ContractValidationError):
        validate_value(payload, SCHEMAS["issue_action_request.schema.json"])


def test_review_action_openapi_paths_are_bodyful() -> None:
    with (ROOT / "contracts" / "openapi.yaml").open(encoding="utf-8") as openapi_file:
        openapi = yaml.safe_load(openapi_file)
    for path in (
        "/api/issues/{issue_id}/accept",
        "/api/issues/{issue_id}/dismiss",
        "/api/issues/{issue_id}/resolve-as-new-concept",
        "/api/issues/{issue_id}/resolve-as-alias",
        "/api/issues/{issue_id}/resolve-as-forbidden",
    ):
        operation = openapi["paths"][path]["post"]
        request_content = operation["requestBody"]["content"]
        response_content = operation["responses"]["200"]["content"]
        request_schema = request_content["application/json"]["schema"]
        response_schema = response_content["application/json"]["schema"]
        assert request_schema == {"$ref": "./schemas/issue_action_request.schema.json"}
        assert response_schema == {"$ref": "./schemas/issue_action_payload.schema.json"}


def test_missing_candidate_evidence_is_rejected() -> None:
    payload = copy.deepcopy(VALID_PAYLOADS["llm_term_candidates.schema.json"])
    payload["candidates"][0]["evidence"] = []
    with pytest.raises(ContractValidationError):
        validate_value(payload, SCHEMAS["llm_term_candidates.schema.json"])


def test_unknown_graph_edge_relation_is_rejected() -> None:
    payload = copy.deepcopy(VALID_PAYLOADS["app_graph.schema.json"])
    payload["edges"][0]["relation"] = "causes"
    with pytest.raises(ContractValidationError):
        validate_value(payload, SCHEMAS["app_graph.schema.json"])


def test_openapi_names_match_planned_local_surface() -> None:
    with (ROOT / "contracts" / "openapi.yaml").open(encoding="utf-8") as openapi_file:
        openapi = yaml.safe_load(openapi_file)
    assert set(openapi["paths"]) == {
        "/api/health",
        "/api/concepts",
        "/api/concepts/{concept_id}",
        "/api/concepts/{concept_id}/variants",
        "/api/variants/{variant_id}",
        "/api/documents/analyze-path",
        "/api/documents",
        "/api/documents/{document_id}",
        "/api/documents/{document_id}/occurrences",
        "/api/issues",
        "/api/issues/{issue_id}",
        "/api/issues/{issue_id}/accept",
        "/api/issues/{issue_id}/dismiss",
        "/api/issues/{issue_id}/resolve-as-new-concept",
        "/api/issues/{issue_id}/resolve-as-alias",
        "/api/issues/{issue_id}/resolve-as-forbidden",
        "/api/search/concepts",
        "/api/search/similar-concepts",
        "/api/graphs/current",
        "/api/graphs/rebuild",
        "/api/graphs/snapshots",
        "/api/graphs/snapshots/{snapshot_id}",
        "/api/graphs/graphify/export",
    }
    assert "/api/graphs/graphify/import" not in openapi["paths"]
