# Directory Size Counter

Walks a directory tree and aggregates per-subdirectory byte counts and file counts into a nested `DirectorySummary`.

```python
from directory_size_counter import walk

summary = walk(".")
print(summary.path, summary.size, summary.file_count)
for sub in summary.subdir_summaries:
    print(" ", sub.path, sub.size, sub.file_count)
```

## Why this exists

I needed a deterministic, dependency-free way to report how much space each subdirectory of a tree consumes — bytes, file count, and the same structure one level down. `du` gives bytes but not file counts; `os.walk` gives structure but no aggregation. This library fills that gap by returning a recursive `DirectorySummary` you can traverse directly.

The trade-off: there is no filtering, no human-readable formatting, and no streaming. The whole tree is read into memory as a tree of dataclasses. For trees with millions of directories that is the wrong tool; for a few thousand it is fine and the code stays small.

## Exported names

- `walk(path: str, follow_symlinks: bool = False) -> DirectorySummary`
- `DirectorySummary` — a dataclass with `path: str`, `size: int`, `file_count: int`, `subdir_summaries: list[DirectorySummary]`.

## Edge cases you will hit

Symlinks are the awkward one. By default `follow_symlinks=False`, which means a symlink to a directory is **not** traversed and contributes nothing to counts — it is neither a file nor a directory from the walker's perspective. A symlink to a file is reported as a file with the **size of the link itself**, not the target (this matches `os.path.getsize` on the link). If you pass `follow_symlinks=True`, directory symlinks are followed and you are responsible for avoiding cycles; the library does not detect them.

Entries that cannot be stated (broken symlinks, files that vanish mid-walk, permission-denied entries) are silently skipped so a partial tree still produces a summary. A top-level path that does not exist raises `FileNotFoundError`; a path that is not a directory raises `NotADirectoryError`.

The order of `subdir_summaries` is filesystem order from `os.scandir`, not sorted. Sort on `path` if you need deterministic ordering across platforms.
