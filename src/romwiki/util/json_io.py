"""Shared helpers for writing JSON data to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, value: Any) -> None:
    """Write ``value`` to ``path`` as pretty-printed, sorted JSON.

    Writes to a sibling ``.tmp`` file first and renames it into place so
    readers never observe a partially written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
