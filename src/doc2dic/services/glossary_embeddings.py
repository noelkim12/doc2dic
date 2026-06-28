"""Glossary-owned embedding indexing trigger."""

import sqlite3
from dataclasses import dataclass

from doc2dic.services.embedding_config import embedding_provider_from_project
from doc2dic.services.embedding_index import (
    ConceptEmbeddingIndexResult,
    index_active_concept_embeddings,
)
from doc2dic.services.embedding_service import EmbeddingService
from doc2dic.storage.vector_store import VectorStore


@dataclass(frozen=True, slots=True)
class ProjectGlossaryEmbeddingIndexer:
    """Index active concept embeddings for one project database."""

    connection: sqlite3.Connection

    def index_active_concepts(self) -> ConceptEmbeddingIndexResult:
        """Backfill or refresh embeddings for all active concepts."""
        return index_active_concept_embeddings(
            self.connection,
            embedding_service=EmbeddingService(
                embedding_provider_from_project(self.connection),
            ),
            vector_store=VectorStore(self.connection),
        )


__all__ = ["ProjectGlossaryEmbeddingIndexer"]
