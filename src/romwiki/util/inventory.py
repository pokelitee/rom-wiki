from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

_INVENTORY_LOCK = threading.Lock()


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
