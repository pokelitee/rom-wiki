from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.pipeline.relationships import (
    LocationEncounterReference,
    RelationshipIndex,
)
from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.components import (
    display_name,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    summary_section,
)
from romwiki.renderers.mkdocs.locations import (
    _append_connections,
    _append_items,
    _append_shops,
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
    relationships: RelationshipIndex | None = None,
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
    fallback_links = []
    catalog_records = []
    page_count = 0
    sorted_records = sorted(records, key=lambda item: (item["name"], item["header_id"]))
    for index, record in enumerate(sorted_records):
        filename = _filename(record["header_id"])
        encounters = (
            relationships.location_encounters.get(record["header_id"], ())
            if relationships
            else ()
        )
        previous = sorted_records[index - 1] if index else None
        following = (
            sorted_records[index + 1] if index + 1 < len(sorted_records) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_gen5_location(
                    record,
                    previous,
                    following,
                    references,
                    encounters,
                ),
            )
            page_count += 1
        route_id = filename.removesuffix(".md")
        fallback_label = f"{record['name']} — {route_id}"
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "location",
                    record["header_id"],
                    fallback_label,
                    record["header_id"],
                ),
                "locations/index.md",
            )
        )
        catalog_records.append(
            {
                "id": record["header_id"],
                "route_id": route_id,
                "label": record["name"],
                "url": route_id + "/",
                "features": [
                    *(["encounters"] if encounters else []),
                    *(["trainers"] if record["trainers"] else []),
                    *(["warps"] if record["warps"] else []),
                    *(["static-encounters"] if record["static_encounters"] else []),
                    *(["connections"] if record["connections"] else []),
                    *(["items"] if record["items"] else []),
                    *(["shops"] if record.get("shops") else []),
                ],
                "search_text": f"{record['name']} {route_id}".lower(),
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
    encounters: tuple[LocationEncounterReference, ...] = (),
) -> str:
    source_file = f"locations/{_filename(record['header_id'])}"
    facts = [f"<div><dt>Header ID</dt><dd>{record['header_id']}</dd></div>"]
    if encounters:
        facts.append(
            "<div><dt>Wild encounters</dt><dd>"
            f"map index {record['encounter_map_index']}</dd></div>"
        )
    lines = [
        f"# {record['name']}",
        "",
        *summary_section("rw-location-summary", facts),
    ]
    if encounters:
        lines.extend(["## Wild encounters", ""])
        _append_encounter_variants(lines, encounters, source_file)
    _append_connections(lines, record["connections"], source_file)
    _append_trainers(lines, record["trainers"], source_file)
    _append_warps(lines, record["warps"], source_file)
    _append_items(lines, record["items"], source_file, references)
    _append_shops(lines, record.get("shops", []), source_file, references)
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
                        *(
                            (
                                (
                                    "Wild encounter table index",
                                    f"`{record['encounter_map_index']}`",
                                ),
                            )
                            if record["encounter_map_index"] is not None
                            else ()
                        ),
                    )
                ),
                "Source: exact ROM map header record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`.",
                "The display name, wild-encounter cross-reference, real "
                "trainers (both sight-triggered and scripted), real warps, "
                "real outdoor connections, real field items (visible and "
                "hidden), and real static encounters are decoded. "
                "Script-linked shops are decoded from their real local "
                "dispatcher functions.",
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


def _append_encounter_variants(
    lines: list[str],
    encounters: tuple[LocationEncounterReference, ...],
    source_file: str,
) -> None:
    if len(encounters) == 1 and encounters[0].season is None:
        encounter = encounters[0]
        lines.extend(
            [
                ROUTES.markdown_link(
                    entity_reference(
                        "encounter_variant",
                        encounter.area_id,
                        "View encounter table",
                        encounter.encounter_route_key,
                    ),
                    source_file,
                ),
                "",
            ]
        )
        return
    lines.extend(
        [
            "| Season | Encounter area | Version |",
            "| ------ | -------------- | ------- |",
        ]
    )
    for encounter in encounters:
        label = f"Map {encounter.map_index:03}" + (
            f" ({encounter.season.title()})" if encounter.season else ""
        )
        link = ROUTES.markdown_link(
            entity_reference(
                "encounter_variant",
                encounter.area_id,
                label,
                encounter.encounter_route_key,
            ),
            source_file,
        )
        versions = (
            " / ".join(display_name(value) for value in encounter.versions) or "—"
        )
        lines.append(
            f"| {encounter.season.title() if encounter.season else 'All'} | "
            f"{link} | {versions} |"
        )
    lines.append("")
