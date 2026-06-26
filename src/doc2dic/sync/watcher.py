"""Optional watcher seam for local sync refresh loops."""

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from doc2dic.sync.scanner import SKIPPED_DIR_NAMES

type RawWatchChange = tuple[str, str]
type WatchBatch = Iterable[RawWatchChange]
type WatchProvider = Callable[[Path], Iterator[WatchBatch]]


def changed_project_paths(
    project_root: Path,
    watch: WatchProvider,
) -> Iterator[tuple[Path, ...]]:
    """Yield changed project paths from an injected watchfiles-compatible provider."""
    for changes in watch(project_root):
        paths = tuple(
            Path(raw_path)
            for _change, raw_path in changes
            if _is_watch_candidate(Path(raw_path))
        )
        if paths:
            yield paths


def _is_watch_candidate(path: Path) -> bool:
    return not any(part in SKIPPED_DIR_NAMES for part in path.parts)
