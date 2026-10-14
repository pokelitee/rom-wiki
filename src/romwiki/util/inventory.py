from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

_INVENTORY_LOCK = threading.Lock()
# Filesystem timestamps are coarse, so a same-size rewrite within this window
# can keep its old modification time; such files must be read, not trusted
# from a (size, mtime) cache.
_RACY_MTIME_WINDOW_NS = 2_000_000_000


def modified_too_recently(mtime_ns: int) -> bool:
    """Whether a (size, mtime) cache entry for this file could be stale."""
    return time.time_ns() - mtime_ns < _RACY_MTIME_WINDOW_NS


def read_inventory_state(path: Path, *, schema_version: int) -> dict[str, str] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    files = value.get("files")
    if (
        value.get("schema_version") != schema_version
        or not isinstance(files, dict)
        or not files
        or not all(
            isinstance(relative, str)
            and isinstance(metadata, str)
            and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts
            for relative, metadata in files.items()
        )
    ):
        return None
    return files


def inventory_fingerprint(inventory: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(inventory.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def file_path_inventory(
    root: Path, *, excluded_top_level: frozenset[str] = frozenset()
) -> dict[str, str]:
    if not root.is_dir():
        return {}
    paths: list[str] = []
    for directory, child_directories, names in os.walk(root):
        if Path(directory) == root:
            child_directories[:] = [
                name for name in child_directories if name not in excluded_top_level
            ]
            names = [name for name in names if name not in excluded_top_level]
        paths.extend(
            (Path(directory) / name).relative_to(root).as_posix() for name in names
        )
    return dict.fromkeys(sorted(paths), "present")


def file_metadata_inventory(
    root: Path, *, excluded_top_level: frozenset[str] = frozenset()
) -> dict[str, str]:
    if not root.is_dir():
        return {}
    with _INVENTORY_LOCK:
        return {
            relative: f"{stat.st_size}:{stat.st_mtime_ns}"
            for relative, _, stat in _walk_files(root, excluded_top_level)
        }


def file_content_inventory(
    root: Path, *, excluded_top_level: frozenset[str] = frozenset()
) -> dict[str, str]:
    """Map each file under `root` to its SHA-256, independent of timestamps."""
    if not root.is_dir():
        return {}
    with _INVENTORY_LOCK:
        files = _walk_files(root, excluded_top_level)
    return {
        relative: hashlib.sha256(path.read_bytes()).hexdigest()
        for relative, path, _ in files
    }


def _walk_files(
    root: Path, excluded_top_level: frozenset[str]
) -> list[tuple[str, Path, os.stat_result]]:
    files: list[tuple[str, Path, os.stat_result]] = []
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                if not prefix and entry.name in excluded_top_level:
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append((Path(entry.path), relative))
                elif entry.is_file():
                    files.append(
                        (relative.replace(os.sep, "/"), Path(entry.path), entry.stat())
                    )
    return sorted(files, key=lambda value: value[0])
