"""Term text normalization for deterministic document checks."""

import re
import unicodedata
from typing import Final

WHITESPACE_RE: Final = re.compile(r"\s+")
EDGE_PUNCTUATION: Final = " \t\r\n\"'`.,;:!?()[]{}<>"


def normalize_term_text(text: str) -> str:
    """Return a stable comparison form for Korean and English term text."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    collapsed = WHITESPACE_RE.sub(" ", normalized)
    return collapsed.strip(EDGE_PUNCTUATION)
