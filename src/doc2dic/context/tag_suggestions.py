"""Deterministic tag suggestions for glossary term creation."""

import re
import sqlite3
from dataclasses import dataclass
from typing import Final

from doc2dic.domain import Concept, EmbeddingOwnerType
from doc2dic.services.embedding_config import embedding_provider_from_project
from doc2dic.services.embedding_index import index_active_concept_embeddings
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingInputType,
    EmbeddingService,
    EmbeddingSuccess,
)
from doc2dic.services.glossary_service import GlossaryService
from doc2dic.storage.repositories.embeddings import EmbeddingRepository
from doc2dic.storage.vector_store import VectorStore

TOKEN_PATTERN: Final = re.compile(r"[\w가-힣]+", re.UNICODE)
DEFAULT_SUGGESTION_LIMIT: Final = 8
SOURCE_CONCEPT_LIMIT: Final = 3
VECTOR_CANDIDATE_LIMIT: Final = 5


@dataclass(frozen=True, slots=True)
class TagSuggestion:
    """One existing tag recommendation with its glossary evidence."""

    label: str
    score: int
    source_concepts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticConceptEvidence:
    """One concept found through semantic vector search."""

    concept_id: str
    score: int


@dataclass(frozen=True, slots=True)
class SemanticTagEvidence:
    """Vector candidate status and source concepts."""

    enabled: bool
    reason: str
    concepts: tuple[SemanticConceptEvidence, ...]


def build_tag_suggestions(
    query: str,
    *,
    connection: sqlite3.Connection,
    embedding_service: EmbeddingService | None = None,
    vector_store: VectorStore | None = None,
) -> str:
    """Return Markdown tag suggestions from existing glossary concepts."""
    concepts = GlossaryService(connection).list_concepts()
    semantic_evidence = _semantic_tag_evidence(
        query,
        connection=connection,
        embedding_service=embedding_service
        or EmbeddingService(embedding_provider_from_project(connection)),
        vector_store=vector_store or VectorStore(connection),
    )
    suggestions = _suggestions(query, concepts, semantic_evidence)
    all_tags = _all_tags(concepts)
    lines = [
        "# doc2dic tag suggestions",
        "",
        f"- Query: `{_inline(query)}`",
        f"- Existing tags considered: {len(all_tags)}",
        f"- Vector candidates: {_vector_status(semantic_evidence)}",
        "",
    ]
    if len(all_tags) == 0:
        lines.extend([
            "## Suggested tags",
            (
                "- No existing tags are stored yet. "
                "Add a new normalized tag if it helps review."
            ),
        ])
    elif len(suggestions) == 0:
        lines.extend([
            "## Suggested tags",
            "- No strong existing-tag match was found for this term.",
            "",
            "## Existing tags",
            *[f"- `{tag}`" for tag in all_tags],
        ])
    else:
        lines.extend(["## Suggested tags", *_suggestion_lines(suggestions)])
    lines.extend([
        "",
        "## Review boundary",
        "- This tool does not mutate the glossary or approve terms automatically.",
        (
            "- Use the review workflow before adding aliases, "
            "forbidden terms, or concepts."
        ),
    ])
    return "\n".join(lines)


def _suggestions(
    query: str,
    concepts: tuple[Concept, ...],
    semantic_evidence: SemanticTagEvidence,
) -> tuple[TagSuggestion, ...]:
    query_tokens = _tokens(query)
    scored: dict[str, tuple[int, list[str]]] = {}
    for concept in concepts:
        concept_score = _concept_score(query_tokens, concept)
        for tag in concept.tags:
            tag_score = concept_score + _tag_score(query_tokens, tag)
            if tag_score <= 0:
                continue
            current_score, sources = scored.get(tag, (0, []))
            if concept.primary_term not in sources:
                sources.append(concept.primary_term)
            scored[tag] = (current_score + tag_score, sources)
    concepts_by_id = {concept.id: concept for concept in concepts}
    for evidence in semantic_evidence.concepts:
        concept = concepts_by_id.get(evidence.concept_id)
        if concept is not None:
            for tag in concept.tags:
                current_score, sources = scored.get(tag, (0, []))
                if concept.primary_term not in sources:
                    sources.append(concept.primary_term)
                scored[tag] = (current_score + evidence.score, sources)
    suggestions = tuple(
        TagSuggestion(
            label=label,
            score=score,
            source_concepts=tuple(sources[:SOURCE_CONCEPT_LIMIT]),
        )
        for label, (score, sources) in scored.items()
    )
    return tuple(
        sorted(suggestions, key=lambda item: (-item.score, item.label))[
            :DEFAULT_SUGGESTION_LIMIT
        ],
    )


def _concept_score(query_tokens: frozenset[str], concept: Concept) -> int:
    concept_tokens = _tokens(
        f"{concept.primary_term} {concept.definition} {concept.term_type.value}",
    ) | frozenset(concept.tags)
    return len(query_tokens & concept_tokens) * 2


def _tag_score(query_tokens: frozenset[str], tag: str) -> int:
    tag_tokens = _tokens(tag)
    if tag in query_tokens or len(query_tokens & tag_tokens) > 0:
        return 3
    return 0


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)
    )


def _all_tags(concepts: tuple[Concept, ...]) -> tuple[str, ...]:
    return tuple(sorted({tag for concept in concepts for tag in concept.tags}))


def _semantic_tag_evidence(
    query: str,
    *,
    connection: sqlite3.Connection,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
) -> SemanticTagEvidence:
    if _inline(query) == "":
        return SemanticTagEvidence(enabled=False, reason="empty query", concepts=())
    index_result = index_active_concept_embeddings(
        connection,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    if not index_result.enabled:
        return SemanticTagEvidence(
            enabled=False,
            reason=index_result.reason,
            concepts=(),
        )
    embedding_result = embedding_service.embed_texts(
        (_inline(query),),
        input_type=EmbeddingInputType.QUERY,
    )
    match embedding_result:
        case EmbeddingFailure(message=message):
            return SemanticTagEvidence(enabled=False, reason=message, concepts=())
        case EmbeddingSuccess(embeddings=embeddings):
            if len(embeddings) != 1:
                return SemanticTagEvidence(
                    enabled=False,
                    reason="provider returned unexpected embedding count",
                    concepts=(),
                )
            vector_result = vector_store.query_top_k(
                vector=embeddings[0].values,
                top_k=VECTOR_CANDIDATE_LIMIT,
            )
            if not vector_result.enabled:
                return SemanticTagEvidence(
                    enabled=False,
                    reason=vector_result.reason,
                    concepts=(),
                )
            repository = EmbeddingRepository(connection)
            concepts: list[SemanticConceptEvidence] = []
            for match in vector_result.matches:
                embedding = repository.get_embedding(match.embedding_id)
                if (
                    embedding is not None
                    and embedding.owner_type == EmbeddingOwnerType.CONCEPT
                ):
                    concepts.append(
                        SemanticConceptEvidence(
                            concept_id=embedding.owner_id,
                            score=_semantic_score(match.distance),
                        ),
                    )
            return SemanticTagEvidence(
                enabled=True,
                reason=vector_result.reason,
                concepts=tuple(concepts),
            )


def _semantic_score(distance: float) -> int:
    return max(1, round(10 / (1 + max(distance, 0.0))))


def _vector_status(evidence: SemanticTagEvidence) -> str:
    if evidence.enabled:
        return "enabled"
    return f"disabled ({evidence.reason})"


def _suggestion_lines(suggestions: tuple[TagSuggestion, ...]) -> list[str]:
    lines: list[str] = []
    for index, suggestion in enumerate(suggestions, start=1):
        lines.extend([
            f"{index}. `{suggestion.label}`",
            f"   - Score: {suggestion.score}",
            f"   - Source concepts: {', '.join(suggestion.source_concepts)}",
        ])
    return lines


def _inline(text: str) -> str:
    return " ".join(text.replace("`", "'").split())
