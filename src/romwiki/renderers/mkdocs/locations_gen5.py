from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.components import (
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    summary_section,
)
from romwiki.renderers.mkdocs.locations import (
    _append_connections,
    _append_items,
    _append_static_encounters,
    _append_trainers,
    _append_warps,
    _filename,
)
from romwiki.renderers.mkdocs.references import ROUTES, ReferenceIndex, entity_reference


def render_gen5_location_pages(
    dataset: dict[str, Any],
    output_root: Path,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                _filename(record["header_id"])
                for record in records
                if only_pages is None
                or _filename(record["header_id"]).removesuffix(".md") in only_pages
            ),
        },
    )
    name_counts = Counter(record["name"] for record in records)
    fallback_links = []
    catalog_records = []
    page_count = 0
    sorted_records = sorted(records, key=lambda item: (item["name"], item["header_id"]))
    for index, record in enumerate(sorted_records):
        filename = _filename(record["header_id"])
        previous = sorted_records[index - 1] if index else None
        following = (
            sorted_records[index + 1] if index + 1 < len(sorted_records) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_gen5_location(record, previous, following, references),
            )
            page_count += 1
        label = record["name"]
        if name_counts[label] > 1:
            label = f"{label} (header {record['header_id']})"
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "location", record["header_id"], label, record["header_id"]
                ),
                "locations/index.md",
            )
        )
        catalog_records.append(
            {
                "id": record["header_id"],
                "label": label,
                "url": filename.removesuffix(".md") + "/",
                "features": [
                    *(
                        ["encounters"]
                        if record["encounter_map_index"] is not None
                        else []
                    ),
                    *(["trainers"] if record["trainers"] else []),
                    *(["warps"] if record["warps"] else []),
                    *(["static-encounters"] if record["static_encounters"] else []),
                    *(["connections"] if record["connections"] else []),
                    *(["items"] if record["items"] else []),
                ],
                "search_text": record["name"].lower(),
            }
        )
    write_catalog(output_root, "locations", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Locations",
            "Map header names and wild-encounter cross-references extracted "
            "from the ROM.",
            "locations",
            fallback_links,
        ),
    )
    return page_count


def _render_gen5_location(
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    references: ReferenceIndex | None = None,
) -> str:
    facts = [f"<div><dt>Header ID</dt><dd>{record['header_id']}</dd></div>"]
    if record["encounter_map_index"] is not None:
        facts.append(
            "<div><dt>Wild encounters</dt><dd>"
            f"map index {record['encounter_map_index']}</dd></div>"
        )
    lines = [
        f"# {record['name']}",
        "",
        *summary_section("rw-location-summary", facts),
    ]
    if record["encounter_map_index"] is not None:
        lines.extend(
            [
                "## Wild encounters",
                "",
                "This location's wild encounters come from Wild Encounters "
                f"table index `{record['encounter_map_index']}`. Not linked "
                "directly to a specific encounter-area page here, since a "
                "single table index can expand into up to 4 seasonal areas — "
                "search the Wild Encounters catalog for this index instead.",
                "",
            ]
        )
    source_file = f"locations/{_filename(record['header_id'])}"
    _append_connections(lines, record["connections"], source_file)
    _append_trainers(lines, record["trainers"], source_file)
    _append_warps(lines, record["warps"], source_file)
    _append_items(lines, record["items"], source_file, references)
    _append_static_encounters(
        lines, record["static_encounters"], source_file, references
    )
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Header ID", f"`{record['header_id']}`"),
                        ("Matrix ID", f"`{record['matrix_id']}`"),
                    )
                ),
                "Source: exact ROM map header record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`.",
                "The display name, wild-encounter cross-reference, real "
                "trainers (both sight-triggered and scripted), real warps, "
                "real outdoor connections, real field items (visible and "
                "hidden), and real static encounters are decoded. "
                "Location-linked shops aren't decoded yet.",
            ]
        )
    )
    lines.extend(
        record_navigation_for(
            "location",
            f"locations/{_filename(record['header_id']).removesuffix('.md')}/",
            previous,
            following,
            aria_label="Location navigation",
            identity=lambda value: value["header_id"],
            route_key=lambda value: value["header_id"],
            label=lambda value: value["name"],
        )
    )
    return "\n".join(lines)
