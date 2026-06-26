"""Graphify-compatible export adapter for derived glossary graph data."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from doc2dic.domain import AppGraph
from doc2dic.storage.json_codec import tuple_from_json_text
from doc2dic.storage.sqlite_rows import text_cell

GRAPHIFY_PACKAGE_NAME: Final = "graphifyy"
GRAPHIFY_EXECUTABLE_NAME: Final = "graphify"
PINNED_GRAPHIFY_VERSION: Final = "0.4.29"
GRAPHIFY_SCHEMA_DESCRIPTION: Final = (
    "graphify.validate extraction schema observed in graphifyy 0.4.29: "
    "nodes require id,label,file_type,source_file; edges require "
    "source,target,relation,confidence,source_file."
)
MAX_DOCUMENT_BODY_CHARS: Final = 4000


class GraphifyProjectionDocument(BaseModel):
    """Contract document exported beside the AppGraph projection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    path: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=MAX_DOCUMENT_BODY_CHARS)


class GraphifyProjection(BaseModel):
    """Frozen public Graphify projection contract payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    graph: AppGraph
    documents: tuple[GraphifyProjectionDocument, ...] = Field(default_factory=tuple)


class GraphifyNode(BaseModel):
    """Graphify extraction node compatible with graphify.validate."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str
    label: str
    file_type: Literal["document"] = "document"
    source_file: str
    source_location: str | None = None


class GraphifyEdge(BaseModel):
    """Graphify extraction edge compatible with graphify.validate."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    source: str
    target: str
    relation: str
    confidence: Literal["EXTRACTED"] = "EXTRACTED"
    confidence_score: float = 1.0
    source_file: str
    source_location: str | None = None
    weight: float = 1.0


class GraphifyExtraction(BaseModel):
    """Native graphify extraction JSON with no runtime dependency."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    nodes: tuple[GraphifyNode, ...] = Field(default_factory=tuple)
    edges: tuple[GraphifyEdge, ...] = Field(default_factory=tuple)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class VariantExport:
    """Term variant fields needed for corpus rendering."""

    label: str
    variant_type: str
    status: str


@dataclass(frozen=True, slots=True)
class ConceptExport:
    """Concept fields needed for Graphify projection rendering."""

    id: str
    primary_term: str
    definition: str
    term_type: str
    status: str
    tags: tuple[str, ...]
    variants: tuple[VariantExport, ...]


class GraphifyAdapter:
    """Convert SQLite glossary state into Graphify-friendly derived data."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used for deterministic export."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def projection_for_graph(self, graph: AppGraph) -> GraphifyProjection:
        """Return the public graphify projection contract for an AppGraph."""
        return GraphifyProjection(
            graph=graph,
            documents=tuple(
                _document_for_concept(concept) for concept in self._concepts()
            ),
        )

    def extraction_for_graph(self, graph: AppGraph) -> GraphifyExtraction:
        """Return native graphify extraction JSON for the same AppGraph."""
        source_files = {node.id: _source_file_for_node(node.id) for node in graph.nodes}
        return GraphifyExtraction(
            nodes=tuple(
                GraphifyNode(
                    id=node.id,
                    label=node.label,
                    source_file=source_files[node.id],
                )
                for node in graph.nodes
            ),
            edges=tuple(
                GraphifyEdge(
                    source=edge.source,
                    target=edge.target,
                    relation=edge.relation,
                    source_file=source_files[edge.source],
                )
                for edge in graph.edges
            ),
            input_tokens=0,
            output_tokens=0,
        )

    def _concepts(self) -> tuple[ConceptExport, ...]:
        variants = self._variants_by_concept()
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select id, primary_term, definition, term_type, status, tags_json
                from concepts
                where status = 'active'
                order by id
                """,
            ).fetchall(),
        )
        return tuple(_concept_from_row(row, variants) for row in rows)

    def _variants_by_concept(self) -> Mapping[str, tuple[VariantExport, ...]]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select concept_id, label, variant_type, status
                from term_variants
                where status in ('active', 'deprecated', 'forbidden')
                order by concept_id, variant_type desc, label, id
                """,
            ).fetchall(),
        )
        grouped: dict[str, list[VariantExport]] = {}
        for row in rows:
            concept_id = text_cell(row, "concept_id")
            grouped.setdefault(concept_id, []).append(
                VariantExport(
                    label=text_cell(row, "label"),
                    variant_type=text_cell(row, "variant_type"),
                    status=text_cell(row, "status"),
                ),
            )
        return {key: tuple(value) for key, value in grouped.items()}


def _concept_from_row(
    row: sqlite3.Row,
    variants: Mapping[str, tuple[VariantExport, ...]],
) -> ConceptExport:
    concept_id = text_cell(row, "id")
    return ConceptExport(
        id=concept_id,
        primary_term=text_cell(row, "primary_term"),
        definition=text_cell(row, "definition"),
        term_type=text_cell(row, "term_type"),
        status=text_cell(row, "status"),
        tags=tuple_from_json_text(text_cell(row, "tags_json")),
        variants=variants.get(concept_id, ()),
    )


def _document_for_concept(concept: ConceptExport) -> GraphifyProjectionDocument:
    body = _bounded_body(_concept_markdown(concept))
    return GraphifyProjectionDocument(
        path=_source_file_for_node(concept.id),
        title=concept.primary_term,
        body=body,
    )


def _source_file_for_node(node_id: str) -> str:
    return f"glossary_export/concepts/{node_id}.md"


def _concept_markdown(concept: ConceptExport) -> str:
    lines = [
        "---",
        f"id: {concept.id}",
        "type: concept",
        f"status: {concept.status}",
        f"term_type: {concept.term_type}",
        "---",
        "",
        f"# {concept.primary_term}",
        "",
        "## Definition",
        "",
        concept.definition,
        "",
        "## Tags",
        "",
        *[f"- {tag}" for tag in concept.tags],
        "",
        "## Variants",
        "",
        *[
            f"- {variant.label} ({variant.variant_type}, {variant.status})"
            for variant in concept.variants
        ],
    ]
    return "\n".join(lines) + "\n"


def _bounded_body(body: str) -> str:
    if len(body) <= MAX_DOCUMENT_BODY_CHARS:
        return body
    return body[: MAX_DOCUMENT_BODY_CHARS - 1].rstrip() + "\n"
