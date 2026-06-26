"""Freshness models for project-local document sync."""

from dataclasses import dataclass
from pathlib import Path

from doc2dic.domain import DocumentMimeType
from doc2dic.services.document_parser import DocumentFormat


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A supported project file parsed during a safe sync scan."""

    path: Path
    absolute_path: Path
    title: str
    text: str
    content_hash: str
    mime_type: DocumentMimeType
    document_format: DocumentFormat


@dataclass(frozen=True, slots=True)
class UnsupportedFile:
    """A project file intentionally excluded from sync ingestion."""

    path: Path
    reason: str


@dataclass(frozen=True, slots=True)
class PendingFile:
    """A supported file not present in the documents repository."""

    path: Path


@dataclass(frozen=True, slots=True)
class StaleFile:
    """A stored document whose current file hash has changed."""

    path: Path
    reason: str


@dataclass(frozen=True, slots=True)
class MissingFile:
    """A stored project document whose source file is absent."""

    path: Path


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    """Computed sync freshness without mutating storage."""

    pending: tuple[PendingFile, ...]
    stale: tuple[StaleFile, ...]
    missing: tuple[MissingFile, ...]
    unsupported: tuple[UnsupportedFile, ...]

    def has_stale_banner(self) -> bool:
        """Return whether context should warn about freshness."""
        return bool(self.pending or self.stale or self.missing)


@dataclass(frozen=True, slots=True)
class ProjectScan:
    """Safe project scan result split by parser support."""

    supported: tuple[SourceFile, ...]
    unsupported: tuple[UnsupportedFile, ...]


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """Receipt for a safe document reconcile."""

    scanned: int
    ingested: int
    unsupported: tuple[UnsupportedFile, ...]
