"""Graph projection domain models."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from doc2dic.domain.concept import ConceptTermType


class GraphNode(BaseModel):
    """Concept node in the app graph."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )
    id: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=160)
    node_type: Literal["concept"] = Field(default="concept", alias="nodeType")
    term_type: ConceptTermType = Field(
        default=ConceptTermType.UNKNOWN,
        alias="termType",
    )


class GraphEdge(BaseModel):
    """Relationship edge in the app graph."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    id: str = Field(pattern=r"^edge_[A-Za-z0-9_-]+$")
    source: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    target: str = Field(pattern=r"^concept_[A-Za-z0-9_-]+$")
    relation: Literal[
        "alias_of",
        "variant_of",
        "contradicts",
        "related_to",
        "depends_on",
        "part_of",
    ]


class AppGraph(BaseModel):
    """Serializable graph projection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    nodes: tuple[GraphNode, ...] = Field(default_factory=tuple)
    edges: tuple[GraphEdge, ...] = Field(default_factory=tuple)


class GraphSnapshot(BaseModel):
    """Persisted graph projection snapshot."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
    )
    id: str = Field(pattern=r"^snapshot_[A-Za-z0-9_-]+$")
    created_at: str = Field(alias="createdAt")
    graph: AppGraph
