"""Safe Markdown/TXT project scanner for sync freshness."""

import os
from hashlib import sha256
from pathlib import Path
from typing import Final

from doc2dic.services.document_parser import (
    MARKDOWN_SUFFIXES,
    TEXT_SUFFIXES,
    UNSUPPORTED_SUFFIXES,
    UnsupportedDocumentFormatError,
    parse_document,
)
from doc2dic.sync.models import ProjectScan, SourceFile, UnsupportedFile

SKIPPED_DIR_NAMES: Final = frozenset(
    {
        ".doc2dic",
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "target",
        "venv",
    },
)


def scan_project(project_root: Path) -> ProjectScan:
    """Return supported and intentionally unsupported project files."""
    root = project_root.resolve(strict=False)
    supported: list[SourceFile] = []
    unsupported: list[UnsupportedFile] = []
    for absolute_path in _candidate_paths(root):
        relative_path = absolute_path.relative_to(root)
        try:
            _ = absolute_path.resolve(strict=False).relative_to(root)
        except ValueError:
            continue
        suffix = absolute_path.suffix.casefold()
        if suffix in UNSUPPORTED_SUFFIXES:
            unsupported.append(
                UnsupportedFile(relative_path, f"{suffix} is not supported"),
            )
            continue
        if suffix not in MARKDOWN_SUFFIXES and suffix not in TEXT_SUFFIXES:
            continue
        try:
            parsed = parse_document(absolute_path)
        except UnsupportedDocumentFormatError as error:
            unsupported.append(UnsupportedFile(relative_path, str(error)))
            continue
        supported.append(
            SourceFile(
                path=relative_path,
                absolute_path=absolute_path,
                title=parsed.title,
                text=parsed.text,
                content_hash=sha256(parsed.text.encode()).hexdigest(),
                mime_type=parsed.mime_type,
                document_format=parsed.document_format,
            ),
        )
    return ProjectScan(tuple(supported), tuple(unsupported))


def _candidate_paths(project_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIR_NAMES)
        current_dir = Path(dirpath)
        paths.extend(current_dir / filename for filename in sorted(filenames))
    return tuple(paths)
