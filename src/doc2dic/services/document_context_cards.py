"""Bounded context cards for analysis providers."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

DEFAULT_MAX_DOCUMENT_CHARS: Final = 600
DEFAULT_MAX_QUOTE_CHARS: Final = 240
DEFAULT_MAX_GLOSSARY_TERMS: Final = 8
DEFAULT_MAX_TERM_CHARS: Final = 160
TRUNCATION_MARKER: Final = "..."


@dataclass(frozen=True, slots=True)
class ContextCardLimits:
    """Limits that prevent provider prompts from carrying full documents."""

    max_document_chars: int = DEFAULT_MAX_DOCUMENT_CHARS
    max_quote_chars: int = DEFAULT_MAX_QUOTE_CHARS
    max_glossary_terms: int = DEFAULT_MAX_GLOSSARY_TERMS
    max_term_chars: int = DEFAULT_MAX_TERM_CHARS


DEFAULT_CONTEXT_CARD_LIMITS: Final = ContextCardLimits()


@dataclass(frozen=True, slots=True)
class GlossaryContextTerm:
    """Small glossary row safe to include in provider context."""

    surface: str
    definition: str
    concept_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentContextInput:
    """Document data reduced into a bounded context card."""

    document_id: str
    path: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class GlossaryTermCard:
    """Bounded glossary entry passed to analysis providers."""

    surface: str
    definition: str
    concept_id: str | None


@dataclass(frozen=True, slots=True)
class DocumentContextCard:
    """Bounded document excerpt passed to analysis providers."""

    document_id: str
    path: str
    title: str
    excerpt: str
    omitted_characters: int


@dataclass(frozen=True, slots=True)
class AnalysisContextCards:
    """Provider-ready context without full raw source leakage."""

    document: DocumentContextCard
    glossary_terms: tuple[GlossaryTermCard, ...]


def build_context_cards(
    document: DocumentContextInput,
    glossary_terms: Sequence[GlossaryContextTerm] = (),
    limits: ContextCardLimits = DEFAULT_CONTEXT_CARD_LIMITS,
) -> AnalysisContextCards:
    """Build bounded document and glossary cards for LLM prompts."""
    return AnalysisContextCards(
        document=DocumentContextCard(
            document_id=document.document_id,
            path=document.path,
            title=_truncate(document.title, limits.max_term_chars),
            excerpt=_truncate(document.text, limits.max_document_chars),
            omitted_characters=max(0, len(document.text) - limits.max_document_chars),
        ),
        glossary_terms=tuple(
            GlossaryTermCard(
                surface=_truncate(term.surface, limits.max_term_chars),
                definition=_truncate(term.definition, limits.max_quote_chars),
                concept_id=term.concept_id,
            )
            for term in glossary_terms[: limits.max_glossary_terms]
        ),
    )


def bounded_evidence_quote(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_QUOTE_CHARS,
) -> str:
    """Return one bounded quote-sized text fragment."""
    return _truncate(_compact(text), max_chars)


def _truncate(text: str, max_chars: int) -> str:
    compacted = _compact(text)
    if len(compacted) <= max_chars:
        return compacted
    visible_chars = max(0, max_chars - len(TRUNCATION_MARKER))
    return f"{compacted[:visible_chars].rstrip()}{TRUNCATION_MARKER}"


def _compact(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())


__all__ = [
    "DEFAULT_CONTEXT_CARD_LIMITS",
    "AnalysisContextCards",
    "ContextCardLimits",
    "DocumentContextCard",
    "DocumentContextInput",
    "GlossaryContextTerm",
    "GlossaryTermCard",
    "bounded_evidence_quote",
    "build_context_cards",
]
