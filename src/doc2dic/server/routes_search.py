"""Search routes for the local API contract."""

import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette import status

from doc2dic.domain.embedding import EmbeddingOwnerType
from doc2dic.server.dependencies import DatabaseDep, get_database
from doc2dic.server.errors import error_response, not_implemented_response
from doc2dic.server.routes_concepts import ConceptPayload, _concept_payload
from doc2dic.services.embedding_config import embedding_provider_from_project
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingInputType,
    EmbeddingService,
)
from doc2dic.services.glossary_embeddings import ProjectGlossaryEmbeddingIndexer
from doc2dic.services.glossary_service import (
    GlossaryItemNotFoundError,
    GlossaryService,
)
from doc2dic.storage.repositories.embeddings import EmbeddingRepository
from doc2dic.storage.vector_store import VectorStore
from doc2dic.storage.vector_types import VectorMatch

router = APIRouter(
    prefix="/api/search",
    tags=["search"],
    dependencies=[Depends(get_database)],
)

MAX_QUERY_CHARS = 2000
# 1st-stage retrieval width. Equal to RESULT_LIMIT for the MVP; a Phase 2
# reranker widens this and re-orders candidates before truncating to
# RESULT_LIMIT, without changing the response schema.
CANDIDATE_LIMIT = 50
RESULT_LIMIT = 50


class SimilarConceptMatch(BaseModel):
    """One similar-concept hit with its vector distance and similarity."""

    concept: ConceptPayload
    distance: float
    similarity: float


@router.get("/concepts")
def search_concepts(q: str) -> JSONResponse:
    """Return the pending concept search stub."""
    _ = q
    return not_implemented_response()


@router.get("/similar-concepts", response_model=None)
def search_similar_concepts(
    text: str,
    database: DatabaseDep,
) -> tuple[SimilarConceptMatch, ...] | JSONResponse:
    """Return concepts whose embeddings are nearest to the query text."""
    query = text.strip()
    if not query:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_query",
            "Search text must not be empty.",
        )
    if len(query) > MAX_QUERY_CHARS:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_query",
            f"Search text must be at most {MAX_QUERY_CHARS} characters.",
        )

    provider = embedding_provider_from_project(database)
    embed_result = EmbeddingService(provider).embed_texts(
        (query,), input_type=EmbeddingInputType.QUERY
    )
    if isinstance(embed_result, EmbeddingFailure):
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            embed_result.code.value,
            embed_result.message,
        )

    vector = embed_result.embeddings[0].values
    query_result = VectorStore(database).query_top_k(
        vector=vector, top_k=CANDIDATE_LIMIT
    )
    if not query_result.enabled:
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "vector_search_unavailable",
            query_result.reason,
        )

    return _rank_similar_concepts(database, query_result.matches)


def _rank_similar_concepts(
    database: sqlite3.Connection,
    matches: tuple[VectorMatch, ...],
) -> tuple[SimilarConceptMatch, ...]:
    """Resolve vector matches to concepts, scored and capped to RESULT_LIMIT."""
    embeddings = EmbeddingRepository(database)
    service = GlossaryService(database, ProjectGlossaryEmbeddingIndexer(database))
    results: list[SimilarConceptMatch] = []
    for match in matches:
        embedding = embeddings.get_embedding(match.embedding_id)
        if embedding is None or embedding.owner_type != EmbeddingOwnerType.CONCEPT:
            continue
        try:
            concept = service.get_concept(embedding.owner_id)
        except GlossaryItemNotFoundError:
            continue
        results.append(
            SimilarConceptMatch(
                concept=_concept_payload(concept),
                distance=match.distance,
                similarity=1.0 / (1.0 + match.distance),
            )
        )
        if len(results) >= RESULT_LIMIT:
            break
    return tuple(results)
