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


# Filter field count per catalog kind, so the loading skeleton's control
# row previews roughly the number of fields the interactive catalog renders.
# Mirrors "filters" (plus the injected change-status filter and two fields
# per "ranges" entry) for each kind in
# sites/shared/overrides/assets/javascripts/catalog/config.js — keep in sync
# when that config changes.
_SKELETON_FILTER_COUNTS = {
    "pokemon": 8,
    "abilities": 5,
    "items": 11,
    "moves": 8,
    "trainers": 10,
    "locations": 4,
    "encounters": 7,
}
_SKELETON_ROWS = 10


def _catalog_skeleton(kind: str) -> list[str]:
    filter_count = _SKELETON_FILTER_COUNTS.get(kind, 5)
    return [
        '<div class="rw-catalog__skeleton" data-rw-catalog-skeleton aria-hidden="true">',
        '<div class="rw-skeleton__controls">',
        *(
            '<span class="rw-skeleton__field"></span>'
            for _ in range(filter_count)
        ),
        "</div>",
        '<span class="rw-skeleton__bar"></span>',
        '<div class="rw-skeleton__table">',
        _skeleton_table_row(head=True),
        *(_skeleton_table_row() for _ in range(_SKELETON_ROWS)),
        "</div>",
        "</div>",
    ]


def _skeleton_table_row(*, head: bool = False) -> str:
    row_class = "rw-skeleton__table-row"
    if head:
        row_class += " rw-skeleton__table-row--head"
    return f'<div class="{row_class}"><span class="rw-skeleton__cell"></span></div>'


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
        f'<div class="rw-catalog" data-rw-catalog="catalog.json" data-rw-kind="{kind}" aria-busy="true">',
        '<p class="rw-catalog__status" data-rw-catalog-status role="status" aria-live="polite">'
        '<span class="rw-visually-hidden">Loading catalog&hellip;</span></p>',
        *_catalog_skeleton(kind),
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
