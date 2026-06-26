"""Markdown formatting for sync freshness banners."""

from typing import Final

from doc2dic.sync.models import FreshnessReport

MAX_BANNER_ITEMS: Final = 5


def stale_banner_lines(report: FreshnessReport) -> tuple[str, ...]:
    """Return Markdown lines for stale or pending evidence files."""
    if not report.has_stale_banner():
        return ()
    lines = [
        "- Stale/degraded: evidence files need reconcile before trusted edits.",
    ]
    lines.extend(
        f"  - pending: `{file.path.as_posix()}`"
        for file in report.pending[:MAX_BANNER_ITEMS]
    )
    lines.extend(
        f"  - stale: `{file.path.as_posix()}` ({file.reason})"
        for file in report.stale[:MAX_BANNER_ITEMS]
    )
    lines.extend(
        f"  - missing: `{file.path.as_posix()}`"
        for file in report.missing[:MAX_BANNER_ITEMS]
    )
    hidden_count = _hidden_count(report)
    if hidden_count > 0:
        lines.append(f"  - plus {hidden_count} more freshness item(s)")
    return tuple(lines)


def _hidden_count(report: FreshnessReport) -> int:
    shown = min(len(report.pending), MAX_BANNER_ITEMS)
    shown += min(len(report.stale), MAX_BANNER_ITEMS)
    shown += min(len(report.missing), MAX_BANNER_ITEMS)
    return len(report.pending) + len(report.stale) + len(report.missing) - shown
