from __future__ import annotations

import os
import time
from pathlib import Path

# Filesystem timestamps are coarse, so a same-size rewrite within this window
# can keep its old modification time; such files must be read, not trusted
# from a (size, mtime) cache.
_RACY_MTIME_WINDOW_NS = 2_000_000_000


def modified_too_recently(mtime_ns: int) -> bool:
    """Whether a (size, mtime) cache entry for this file could be stale."""
    return time.time_ns() - mtime_ns < _RACY_MTIME_WINDOW_NS


def file_metadata_inventory(root: Path) -> dict[str, str]:
    """Map each file under `root` to its size and modification time."""
    if not root.is_dir():
        return {}
    inventory: dict[str, str] = {}
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                if entry.is_dir(follow_symlinks=False):
                    pending.append((Path(entry.path), relative))
                elif entry.is_file():
                    stat = entry.stat()
                    inventory[relative] = f"{stat.st_size}:{stat.st_mtime_ns}"
    return dict(sorted(inventory.items()))
