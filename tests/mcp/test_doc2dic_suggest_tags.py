import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import anyio

from doc2dic.context.tag_suggestions import build_tag_suggestions
from doc2dic.domain import ConceptTermType
from doc2dic.mcp.registry import SUGGEST_TAGS_TOOL_NAME
from doc2dic.mcp.server import Doc2DicMcpServer, build_doc2dic_mcp_server
from doc2dic.services.embedding_service import (
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingVector,
)
from doc2dic.services.glossary_service import CreateConceptInput, GlossaryService
from doc2dic.storage.connection import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.vector_store import VectorStore
from doc2dic.storage.vector_types import StoredVector


def test_doc2dic_suggest_tags_when_project_has_related_concepts_returns_evidence(
    tmp_path: Path,
) -> None:
    # Given: a temp doc2dic project with existing glossary concepts and tags.
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        _ = service.create_concept(
            CreateConceptInput(
                "Stamina",
                "Player resource spent for dungeon actions.",
                ConceptTermType.RESOURCE,
                ("combat", "resource"),
            ),
        )
        _ = service.create_concept(
            CreateConceptInput(
                "Mana",
                "Magic resource used by players.",
                ConceptTermType.RESOURCE,
                ("magic", "resource"),
            ),
        )
    server = build_doc2dic_mcp_server(tmp_path)

    # When: an agent asks for backend tag suggestions before saving a term.
    response = anyio.run(
        _call_tool_text,
        server,
        SUGGEST_TAGS_TOOL_NAME,
        {
            "query": "Energy: player resource consumed for combat actions",
            "project_path": str(tmp_path),
        },
    )

    # Then: the tool suggests existing tags with source concepts and no mutation.
    assert "# doc2dic tag suggestions" in response
    assert "`resource`" in response
    assert "`combat`" in response
    assert "Source concepts: Stamina" in response
    assert "This tool does not mutate the glossary" in response


def test_doc2dic_suggest_tags_when_project_has_no_tags_returns_guidance(
    tmp_path: Path,
) -> None:
    # Given: a temp doc2dic project with an initialized but empty glossary.
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    server = build_doc2dic_mcp_server(tmp_path)

    # When: an agent asks for tag suggestions before any tags exist.
    response = anyio.run(
        _call_tool_text,
        server,
        SUGGEST_TAGS_TOOL_NAME,
        {"query": "Energy resource", "project_path": str(tmp_path)},
    )

    # Then: the response explains that new tags may be needed without failing.
    assert "# doc2dic tag suggestions" in response
    assert "No existing tags are stored yet" in response
    assert "This tool does not mutate the glossary" in response


def test_build_tag_suggestions_when_vector_finds_related_concept_uses_its_tags(
    tmp_path: Path,
) -> None:
    # Given: concepts with tags where the query only semantically matches one concept.
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        _ = service.create_concept(
            CreateConceptInput(
                "Fireball",
                "Spell projectile that deals area damage.",
                ConceptTermType.UNKNOWN,
                ("magic", "combat"),
            ),
        )
        _ = service.create_concept(
            CreateConceptInput(
                "Backpack",
                "Inventory storage for collected items.",
                ConceptTermType.UNKNOWN,
                ("inventory",),
            ),
        )

        # When: vector search supplies the nearest concept for an otherwise weak term.
        response = build_tag_suggestions(
            "Arcane missile damage",
            connection=connection,
            embedding_service=EmbeddingService(_FakeEmbeddingProvider()),
            vector_store=VectorStore(connection, backend=_SqlVectorBackend()),
        )

    # Then: the suggested tags come from the semantically nearest concept evidence.
    assert "- Vector candidates: enabled" in response
    assert "`magic`" in response
    assert "`combat`" in response
    assert "Source concepts: Fireball" in response


async def _call_tool_text(
    server: Doc2DicMcpServer,
    tool_name: str,
    arguments: dict[str, str],
) -> str:
    content, structured = await server.call_tool(tool_name, arguments)
    assert content[0].text == structured["result"]
    return structured["result"]


@dataclass(frozen=True, slots=True)
class _FakeEmbeddingProvider:
    dimension: int = 2
    model: str = "fake-semantic-v1"
    provider_name: str = "fake"

    def embed_texts(
        self,
        texts: tuple[str, ...],
        _input_type: EmbeddingInputType,
    ) -> tuple[EmbeddingVector, ...]:
        return tuple(
            EmbeddingVector(text=text, model=self.model, values=_semantic_vector(text))
            for text in texts
        )


class _SqlVectorBackend:
    def __init__(self) -> None:
        self._vectors: dict[int, tuple[float, ...]] = {}

    def load(self, connection: sqlite3.Connection) -> None:
        _ = connection

    def create_table(self, connection: sqlite3.Connection, dimension: int) -> None:
        _ = dimension
        self._vectors.clear()
        _ = connection.execute("drop table if exists embedding_vectors")
        _ = connection.execute(
            "create table embedding_vectors(rowid integer primary key)",
        )

    def upsert_vector(
        self,
        connection: sqlite3.Connection,
        vector: StoredVector,
    ) -> None:
        self._vectors[vector.embedding_id] = vector.values
        _ = connection.execute(
            "insert or replace into embedding_vectors(rowid) values (?)",
            (vector.embedding_id,),
        )

    def query_top_k(
        self,
        connection: sqlite3.Connection,
        vector: Sequence[float],
        top_k: int,
    ) -> tuple[tuple[int, float], ...]:
        _ = connection
        ranked = sorted(
            (
                (embedding_id, _distance(vector, stored))
                for embedding_id, stored in self._vectors.items()
            ),
            key=lambda item: (item[1], item[0]),
        )
        return tuple(ranked[:top_k])


def _semantic_vector(text: str) -> tuple[float, float]:
    lowered = text.casefold()
    if "fireball" in lowered or "spell" in lowered or "arcane" in lowered:
        return (0.0, 0.0)
    if "backpack" in lowered or "inventory" in lowered:
        return (10.0, 10.0)
    return (50.0, 50.0)


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(
        (left_item - right_item) ** 2
        for left_item, right_item in zip(left, right, strict=True)
    )
