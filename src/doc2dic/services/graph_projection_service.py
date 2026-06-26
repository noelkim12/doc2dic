"""Project stored glossary state into the internal AppGraph contract."""

import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from typing import Final, Literal, cast

from doc2dic.domain import (
    AppGraph,
    ConceptTermType,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
)
from doc2dic.services.review_state_machine import IssueStatus
from doc2dic.storage.repositories.graphs import GraphRepository
from doc2dic.storage.sqlite_rows import optional_text_cell, require_row, text_cell

type GraphRelation = Literal[
    "alias_of",
    "variant_of",
    "contradicts",
    "related_to",
    "depends_on",
    "part_of",
]

EPOCH_CREATED_AT: Final = "1970-01-01T00:00:00Z"


class GraphProjectionError(RuntimeError):
    """Raised when persisted data cannot be projected into the graph contract."""


@dataclass(frozen=True, slots=True)
class StoredEdge:
    """Intermediate concept edge with deterministic identity input."""

    source: str
    target: str
    relation: GraphRelation
    reason: str


class GraphProjectionService:
    """Build and persist deterministic graph snapshots from SQLite state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Store the SQLite connection used for projection."""
        self._connection: sqlite3.Connection
        self._connection = connection

    def current_graph(self) -> AppGraph:
        """Return the current deterministic AppGraph projection."""
        return AppGraph(nodes=self._nodes(), edges=self._edges())

    def persist_current_snapshot(self) -> GraphSnapshot:
        """Persist and return a deterministic snapshot for the current graph."""
        graph = self.current_graph()
        snapshot = GraphSnapshot(
            id=_snapshot_id(graph),
            createdAt=self._snapshot_created_at(),
            graph=graph,
        )
        GraphRepository(self._connection).upsert_snapshot(snapshot)
        return snapshot

    def _nodes(self) -> tuple[GraphNode, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select id, primary_term, term_type
                from concepts
                where status = 'active'
                order by id
                """,
            ).fetchall(),
        )
        return tuple(
            GraphNode(
                id=text_cell(row, "id"),
                label=text_cell(row, "primary_term"),
                termType=ConceptTermType(text_cell(row, "term_type")),
            )
            for row in rows
        )

    def _edges(self) -> tuple[GraphEdge, ...]:
        stored_edges = (
            *self._variant_edges(),
            *self._relation_edges(),
            *self._issue_edges(),
        )
        return tuple(
            GraphEdge(
                id=_edge_id(edge),
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
            )
            for edge in sorted(stored_edges, key=_edge_sort_key)
        )

    def _variant_edges(self) -> tuple[StoredEdge, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select id, concept_id
                from term_variants
                where status = 'active' and variant_type in ('alias', 'abbreviation')
                order by concept_id, id
                """,
            ).fetchall(),
        )
        return tuple(
            StoredEdge(
                source=text_cell(row, "concept_id"),
                target=text_cell(row, "concept_id"),
                relation="alias_of",
                reason=text_cell(row, "id"),
            )
            for row in rows
        )

    def _relation_edges(self) -> tuple[StoredEdge, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select id, source_concept_id, target_concept_id, relation_type
                from concept_relations
                where status = 'approved'
                order by source_concept_id, relation_type, target_concept_id, id
                """,
            ).fetchall(),
        )
        return tuple(
            StoredEdge(
                source=text_cell(row, "source_concept_id"),
                target=text_cell(row, "target_concept_id"),
                relation=_parse_relation(text_cell(row, "relation_type")),
                reason=text_cell(row, "id"),
            )
            for row in rows
        )

    def _issue_edges(self) -> tuple[StoredEdge, ...]:
        rows = cast(
            "list[sqlite3.Row]",
            self._connection.execute(
                """
                select id, issue_type, candidate_concept_id, target_concept_id
                from term_issues
                where status = ?
                  and candidate_concept_id is not null
                  and target_concept_id is not null
                order by candidate_concept_id, issue_type, target_concept_id, id
                """,
                (IssueStatus.OPEN.value,),
            ).fetchall(),
        )
        return tuple(
            edge
            for row in rows
            if (edge := _issue_edge_from_row(row)) is not None
        )

    def _snapshot_created_at(self) -> str:
        row = cast(
            "sqlite3.Row | None",
            self._connection.execute(
                """
                select max(value) as created_at
                from (
                  select updated_at as value from concepts
                  union all select created_at as value from term_variants
                  union all select analyzed_at as value from documents
                  union all select created_at as value from term_issues
                )
                """,
            ).fetchone(),
        )
        created_at = optional_text_cell(require_row(row), "created_at")
        return created_at or EPOCH_CREATED_AT


def _parse_relation(relation: str) -> GraphRelation:
    match relation:
        case "alias_of":
            return "alias_of"
        case "variant_of":
            return "variant_of"
        case "contradicts":
            return "contradicts"
        case "related_to":
            return "related_to"
        case "depends_on":
            return "depends_on"
        case "part_of":
            return "part_of"
        case _:
            message = f"unknown graph relation type: {relation}"
            raise GraphProjectionError(message)


def _issue_relation(issue_type: str) -> GraphRelation | None:
    match issue_type:
        case "alias_candidate" | "same_meaning_different_term":
            return "alias_of"
        case (
            "conflicting_definition"
            | "same_term_different_meaning"
            | "ambiguous_usage"
        ):
            return "contradicts"
        case "graph_relation_candidate":
            return "related_to"
        case "unknown_term" | "forbidden_term":
            return None
        case _:
            return None


def _issue_edge_from_row(row: sqlite3.Row) -> StoredEdge | None:
    relation = _issue_relation(text_cell(row, "issue_type"))
    if relation is None:
        return None
    return StoredEdge(
        source=text_cell(row, "candidate_concept_id"),
        target=text_cell(row, "target_concept_id"),
        relation=relation,
        reason=text_cell(row, "id"),
    )


def _edge_id(edge: StoredEdge) -> str:
    raw = f"{edge.source}:{edge.relation}:{edge.target}:{edge.reason}"
    return f"edge_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _edge_sort_key(edge: StoredEdge) -> tuple[str, str, str, str]:
    return (edge.source, edge.relation, edge.target, edge.reason)


def _snapshot_id(graph: AppGraph) -> str:
    raw = graph.model_dump_json(by_alias=True)
    return f"snapshot_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"
