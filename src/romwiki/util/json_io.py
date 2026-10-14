"""Shared helpers for writing generated files to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_text_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, leaving an unchanged file's mtime alone.

    Writes to a sibling ``.tmp`` file first and renames it into place so
    readers never observe a partially written file. Leaves an existing file
    untouched (including its mtime) when its content already matches, so
    unchanged pages don't force unnecessary downstream rebuilds (e.g. mkdocs
    `--dirty`, which decides what to reprocess by file modification time).
    """
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """Atomically write bytes unless ``path`` already has identical content."""
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(path)


def write_json_atomic(path: Path, value: Any) -> None:
    """Write ``value`` to ``path`` as pretty-printed, sorted UTF-8 JSON."""
    write_text_atomic(
        path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
