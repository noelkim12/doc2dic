"""Input schemas for doc2dic MCP tools."""

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from doc2dic.domain import ConceptStatus, ConceptTermType


class ExploreToolInput(BaseModel):
    """Validated input for `doc2dic_explore`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    query: str = Field(default="", max_length=4096)
    project_path: Path = Field(default_factory=Path.cwd)


class AnalyzeToolInput(BaseModel):
    """Validated input for hidden legacy `doc2dic_analyze`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    document_path: Path
    project_path: Path = Field(default_factory=Path.cwd)


class SuggestTagsToolInput(BaseModel):
    """Validated input for `doc2dic_suggest_tags`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    query: str = Field(min_length=1, max_length=4096)
    project_path: Path = Field(default_factory=Path.cwd)


class StatusToolInput(BaseModel):
    """Validated input for the hidden `doc2dic_status` tool."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    project_path: Path = Field(default_factory=Path.cwd)


class CreateConceptToolInput(BaseModel):
    """Validated input for `doc2dic_create_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    primary_term: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=2000)
    term_type: ConceptTermType = ConceptTermType.UNKNOWN
    tags: tuple[str, ...] = ()
    physical_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
    source_document: str | None = None
    project_path: Path = Field(default_factory=Path.cwd)


class UpdateConceptToolInput(BaseModel):
    """Validated input for `doc2dic_update_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    concept_id: str = Field(min_length=1)
    primary_term: str | None = Field(default=None, min_length=1, max_length=160)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    term_type: ConceptTermType | None = None
    status: ConceptStatus | None = None
    tags: tuple[str, ...] | None = None
    physical_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
    source_document: str | None = None
    project_path: Path = Field(default_factory=Path.cwd)


class DeleteConceptToolInput(BaseModel):
    """Validated input for `doc2dic_delete_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    concept_id: str = Field(min_length=1)
    confirm: bool = False
    project_path: Path = Field(default_factory=Path.cwd)
