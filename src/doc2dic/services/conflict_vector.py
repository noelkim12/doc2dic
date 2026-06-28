"""Semantic vector query support for conflict candidate analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from doc2dic.domain import EmbeddingOwnerType
from doc2dic.services.document_conflict_models import ActiveConcept
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.embedding_config import embedding_provider_from_project
from doc2dic.services.embedding_index import index_active_concept_embeddings
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingSuccess,
    EmbeddingVector,
)
from doc2dic.storage.json_codec import tuple_from_json_text
from doc2dic.storage.repositories.embeddings import EmbeddingRepository
from doc2dic.storage.sqlite_rows import text_cell
from doc2dic.storage.vector_store import VectorStore
from doc2dic.storage.vector_types import VectorQueryResult

if TYPE_CHECKING:
    import sqlite3

    from doc2dic.services.document_check import CheckResult
    from doc2dic.services.document_glossary import GlossaryTerm
    from doc2dic.services.llm_service import LLMTermCandidate

_TOP_K: Final = 3
_NO_CANDIDATES_REASON: Final = "no semantic vector query candidates"


@dataclass(frozen=True, slots=True)
class SemanticConceptMatch:
    """Nearest concept id resolved for one LLM candidate."""

    candidate_index: int
    concept_id: str


@dataclass(frozen=True, slots=True)
class ConflictVectorQueryResult:
    """Vector query output plus candidate-to-concept semantic matches."""

    matches: tuple[SemanticConceptMatch, ...]
    vector_candidates: VectorQueryResult


@dataclass(frozen=True, slots=True)
class CandidateVectorQuery:
    candidate_index: int
    text: str


@dataclass(frozen=True, slots=True)
class ConflictVectorDependencies:
    """Resolved dependencies for candidate semantic vector queries."""

    embedding_service: EmbeddingService
    vector_store: VectorStore


def default_conflict_vector_dependencies(
    connection: sqlite3.Connection,
) -> ConflictVectorDependencies:
    """Build project-aware embedding/vector dependencies for conflict analysis."""
    return ConflictVectorDependencies(
        embedding_service=EmbeddingService(embedding_provider_from_project(connection)),
        vector_store=VectorStore(connection),
    )


def disabled_vector_query_result(reason: str) -> VectorQueryResult:
    """Return a vector-query-compatible disabled result."""
    return VectorQueryResult(enabled=False, reason=reason, matches=())


def load_active_concepts(connection: sqlite3.Connection) -> tuple[ActiveConcept, ...]:
    """Load active concepts needed for candidate related-concept matching."""
    rows = cast(
        "list[sqlite3.Row]",
        connection.execute(
            """
            select id, primary_term, tags_json
            from concepts
            where status = 'active'
            order by id
            """,
        ).fetchall(),
    )
    return tuple(
        ActiveConcept(
            concept_id=text_cell(row, "id"),
            primary_term=text_cell(row, "primary_term"),
            tags=tuple_from_json_text(text_cell(row, "tags_json")),
        )
        for row in rows
    )


def matching_terms(
    terms: tuple[GlossaryTerm, ...],
    surface: str,
) -> tuple[GlossaryTerm, ...]:
    """Return active glossary terms whose normalized label matches a candidate."""
    normalized = normalize_term_text(surface)
    return tuple(term for term in terms if term.normalized_label == normalized)


def related_concept(
    concepts: tuple[ActiveConcept, ...],
    candidate: LLMTermCandidate,
    matched_terms: tuple[GlossaryTerm, ...],
    semantic_concept_id: str | None,
) -> ActiveConcept | None:
    """Resolve semantic concept first only when exact term matching is undecided."""
    if len(matched_terms) == 0 and semantic_concept_id is not None:
        for concept in concepts:
            if concept.concept_id == semantic_concept_id:
                return concept
    candidate_tags = frozenset(candidate.tags)
    for concept in concepts:
        if len(candidate_tags & frozenset(concept.tags)) > 0:
            return concept
    return None


def query_conflict_vector_candidates(
    connection: sqlite3.Connection,
    check: CheckResult,
    candidates: tuple[LLMTermCandidate, ...],
    *,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
) -> ConflictVectorQueryResult:
    """Index active concepts, query candidate embeddings, and map hits to concepts."""
    queries = _candidate_queries(check, candidates)
    if not queries:
        return _no_candidate_result()

    index_result = index_active_concept_embeddings(
        connection,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    if not index_result.enabled:
        return ConflictVectorQueryResult(
            matches=(),
            vector_candidates=disabled_vector_query_result(index_result.reason),
        )

    embedding_result = embedding_service.embed_texts(
        tuple(query.text for query in queries),
        input_type=EmbeddingInputType.QUERY,
    )
    match embedding_result:
        case EmbeddingFailure(message=message):
            return ConflictVectorQueryResult(
                matches=(),
                vector_candidates=disabled_vector_query_result(message),
            )
        case EmbeddingSuccess(embeddings=embeddings):
            return _query_vectors(
                EmbeddingRepository(connection),
                vector_store=vector_store,
                queries=queries,
                embeddings=embeddings,
            )


def _candidate_queries(
    check: CheckResult,
    candidates: tuple[LLMTermCandidate, ...],
) -> tuple[CandidateVectorQuery, ...]:
    queries: list[CandidateVectorQuery] = []
    for candidate_index, candidate in enumerate(candidates):
        quote = _first_bounded_quote(check, candidate)
        if quote is not None:
            queries.append(
                CandidateVectorQuery(
                    candidate_index=candidate_index,
                    text="\n".join(
                        (
                            f"Surface: {candidate.surface}",
                            f"Definition: {candidate.definition}",
                            f"Evidence: {quote}",
                        ),
                    ),
                ),
            )
    return tuple(queries)


def _first_bounded_quote(check: CheckResult, candidate: LLMTermCandidate) -> str | None:
    for evidence in candidate.evidence:
        for chunk in check.chunks:
            if evidence.quote in chunk.raw_text:
                return evidence.quote
    return None


def _query_vectors(
    repository: EmbeddingRepository,
    *,
    vector_store: VectorStore,
    queries: tuple[CandidateVectorQuery, ...],
    embeddings: tuple[EmbeddingVector, ...],
) -> ConflictVectorQueryResult:
    semantic_matches: list[SemanticConceptMatch] = []
    first_enabled: VectorQueryResult | None = None
    last_disabled = disabled_vector_query_result("no enabled semantic vector query")
    for query, embedding in zip(queries, embeddings, strict=True):
        result = vector_store.query_top_k(vector=embedding.values, top_k=_TOP_K)
        if result.enabled and first_enabled is None:
            first_enabled = result
        if not result.enabled:
            last_disabled = result
        concept_id = _nearest_concept_id(repository, result)
        if concept_id is not None:
            semantic_matches.append(
                SemanticConceptMatch(
                    candidate_index=query.candidate_index,
                    concept_id=concept_id,
                ),
            )
    return ConflictVectorQueryResult(
        matches=tuple(semantic_matches),
        vector_candidates=first_enabled or last_disabled,
    )


def _nearest_concept_id(
    repository: EmbeddingRepository,
    result: VectorQueryResult,
) -> str | None:
    if not result.enabled:
        return None
    for vector_match in result.matches:
        embedding = repository.get_embedding(vector_match.embedding_id)
        if embedding is not None and embedding.owner_type == EmbeddingOwnerType.CONCEPT:
            return embedding.owner_id
    return None


def _no_candidate_result() -> ConflictVectorQueryResult:
    return ConflictVectorQueryResult(
        matches=(),
        vector_candidates=disabled_vector_query_result(_NO_CANDIDATES_REASON),
    )


__all__ = [
    "ConflictVectorDependencies",
    "ConflictVectorQueryResult",
    "SemanticConceptMatch",
    "default_conflict_vector_dependencies",
    "disabled_vector_query_result",
    "load_active_concepts",
    "matching_terms",
    "query_conflict_vector_candidates",
    "related_concept",
]
