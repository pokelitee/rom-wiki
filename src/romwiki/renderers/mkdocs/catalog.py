from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_catalog(output_root: Path, kind: str, records: list[dict[str, Any]]) -> None:
    payload = {"schema_version": 1, "kind": kind, "records": records}
    value = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    write_text(output_root / "catalog.json", value)


def prune_catalog_pages(output_root: Path, filenames: set[str]) -> None:
    for path in output_root.glob("*.md"):
        if path.name not in filenames:
            path.unlink()


def catalog_index(
    title: str,
    description: str,
    kind: str,
    fallback_links: list[str],
) -> str:
    lines = [
        f"# {title}",
        "",
        description,
        "",
        f'<div class="rw-catalog" data-rw-catalog="catalog.json" data-rw-kind="{kind}">',
        '<p class="rw-catalog__status" data-rw-catalog-status>Loading catalog&hellip;</p>',
        "</div>",
        "",
        '<div class="rw-catalog-fallback" data-rw-catalog-fallback>',
        "",
        "## All records",
        "",
        *fallback_links,
        "",
        "</div>",
        "",
    ]
    return "\n".join(lines)


def write_text(path: Path, value: str) -> None:
    """Write ``value`` to ``path``, leaving an unchanged file's mtime alone.

    Writes to a sibling ``.tmp`` file first and renames it into place so
    readers never observe a partially written file. Skipping the write
    entirely when the content already matches avoids bumping the mtime of
    unchanged pages, which matters for tools like mkdocs `--dirty` that
    decide what to reprocess by file modification time.
    """
    if path.is_file() and path.read_text(encoding="utf-8") == value:
        return
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
