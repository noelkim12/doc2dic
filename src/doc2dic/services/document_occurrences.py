"""Exact occurrence detection for deterministic document checks."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from doc2dic.domain import DocumentChunk, TermOccurrence
from doc2dic.services.document_glossary import GlossaryTerm


@dataclass(frozen=True, slots=True)
class DetectedOccurrence:
    """An exact surface occurrence matched against the glossary."""

    term: GlossaryTerm
    chunk: DocumentChunk
    surface: str
    offset_start: int
    offset_end: int


def detect_occurrences(
    chunks: Iterable[DocumentChunk],
    terms: Iterable[GlossaryTerm],
) -> tuple[DetectedOccurrence, ...]:
    """Find exact glossary labels in chunk text with stable offsets."""
    detections: list[DetectedOccurrence] = []
    for chunk in chunks:
        for term in terms:
            pattern = re.compile(re.escape(term.label), flags=re.IGNORECASE)
            detections.extend(
                DetectedOccurrence(
                    term=term,
                    chunk=chunk,
                    surface=match.group(0),
                    offset_start=match.start(),
                    offset_end=match.end(),
                )
                for match in pattern.finditer(chunk.raw_text)
            )
    return tuple(detections)


def term_occurrences(
    document_id: str,
    detections: Iterable[DetectedOccurrence],
) -> tuple[TermOccurrence, ...]:
    """Convert detections into persisted term occurrence rows."""
    return tuple(
        TermOccurrence(
            id=f"occ_{_digest(document_id, detection)}",
            document_id=document_id,
            chunk_id=detection.chunk.id,
            concept_id=detection.term.concept_id,
            surface=detection.surface,
            offset_start=detection.offset_start,
            offset_end=detection.offset_end,
            confidence=1.0,
        )
        for detection in detections
    )


def _digest(document_id: str, detection: DetectedOccurrence) -> str:
    raw = "\u241f".join(
        (
            document_id,
            detection.chunk.id,
            detection.term.concept_id,
            detection.surface,
            str(detection.offset_start),
        ),
    )
    return sha256(raw.encode()).hexdigest()[:16]
