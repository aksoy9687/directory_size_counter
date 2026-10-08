"""Core walker that aggregates byte and file counts per subdirectory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator, List, Optional


@dataclass
class DirectorySummary:
    """Aggregated counts for a single directory and everything below it.

    Attributes:
        path: Absolute or relative path of the directory this summary describes.
        size: Total size in bytes of every file reachable from this directory.
            For a symlink, the *target's* size is reported when the target is
            a file (following the symlink); broken or directory symlinks
            contribute nothing. This matches `os.path.getsize` semantics.
        file_count: Number of files (not directories) reachable from here.
        subdir_summaries: One summary per immediate child directory, in the
            order returned by `os.scandir`. The walk is deterministic because
            scandir returns entries in filesystem order; if you need sorted
            output, sort `subdir_summaries` on `path` afterwards.
    """

    path: str
    size: int
    file_count: int
    subdir_summaries: List["DirectorySummary"]


def _iter_dir(path: str) -> Iterator[os.DirEntry]:
    """Iterate directory entries, silently skipping names we cannot stat.

    Permission errors, broken symlinks, and other OS errors on individual
    entries are swallowed so that a partial tree still produces a summary
    rather than aborting. A directory that itself cannot be opened propagates
    the error from `os.scandir`.
    """
    try:
        entries = list(os.scandir(path))
    except OSError:
        return
    yield from entries


def _aggregate(path: str, follow_symlinks: bool) -> DirectorySummary:
    """Recursively build a summary for a directory on disk."""
    total_size = 0
    total_files = 0
    subdirs: List[DirectorySummary] = []

    for entry in _iter_dir(path):
        try:
            is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
            is_file = entry.is_file(follow_symlinks=follow_symlinks)
        except OSError:
            # Broken symlink or stale NFS handle. Skip the entry entirely.
            continue

        if is_dir:
            child_summary = _aggregate(entry.path, follow_symlinks)
            total_size += child_summary.size
            total_files += child_summary.file_count
            subdirs.append(child_summary)
        elif is_file:
            try:
                total_size += entry.stat(follow_symlinks=follow_symlinks).st_size
                total_files += 1
            except OSError:
                # File vanished or is unreadable; skip without aborting.
                pass

    return DirectorySummary(
        path=path,
        size=total_size,
        file_count=total_files,
        subdir_summaries=subdirs,
    )


def walk(path: str, follow_symlinks: bool = False) -> DirectorySummary:
    """Walk a directory tree and aggregate per-subdirectory byte and file counts.

    Args:
        path: Directory to walk. Must exist.
        follow_symlinks: When True, symlinks to directories are traversed as
            if they were real directories. The caller is responsible for
            avoiding cycles; when False (default) cycles cannot arise because
            symlinks are treated as regular files (the link itself).

    Returns:
        A DirectorySummary for the top-level directory whose `subdir_summaries`
        contains one entry per immediate child directory, recursively.

    Raises:
        NotADirectoryError: If `path` does not name a directory.
        FileNotFoundError: If `path` does not exist.
    """
    if not os.path.isdir(path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"No such directory: {path!r}")
        raise NotADirectoryError(f"Not a directory: {path!r}")
    return _aggregate(os.path.abspath(path), follow_symlinks)
