"""Input schemas for doc2dic MCP tools."""

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ExploreToolInput(BaseModel):
    """Validated input for `doc2dic_explore`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    query: str = Field(default="", max_length=4096)
    project_path: Path = Field(default_factory=Path.cwd)


class StatusToolInput(BaseModel):
    """Validated input for the hidden `doc2dic_status` tool."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    project_path: Path = Field(default_factory=Path.cwd)
