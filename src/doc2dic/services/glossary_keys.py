"""Glossary normalization and stable identifier helpers."""

import re
from hashlib import sha256
from typing import Final

from doc2dic.services.glossary_models import CreateRelationInput

SLUG_PATTERN: Final = re.compile(r"[^a-z0-9]+")


def normalize_label(label: str) -> str:
    """Return a stable duplicate-detection label."""
    normalized = " ".join(label.casefold().strip().split())
    if normalized == "":
        msg = "label cannot be empty"
        raise ValueError(msg)
    return normalized


def prefixed_id(prefix: str, label: str) -> str:
    """Return a contract-compatible deterministic id."""
    slug = SLUG_PATTERN.sub("_", label.casefold()).strip("_")
    base = slug or sha256(label.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{base}"


def relation_id(command: CreateRelationInput) -> str:
    """Return a deterministic relation id for one source/type/target tuple."""
    raw = (
        f"{command.source_concept_id}:"
        f"{command.relation_type}:"
        f"{command.target_concept_id}"
    )
    return f"relation_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Return unique lowercase tag labels in user-provided order."""
    return tuple(dict.fromkeys(tag.strip().casefold() for tag in tags if tag.strip()))
