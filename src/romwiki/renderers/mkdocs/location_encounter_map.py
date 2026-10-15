from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from romwiki.pipeline.semantics.encounter_identity import (
    SAFARI_ZONE_ROUTE,
    encounter_route_key,
)
from romwiki.pipeline.transforms.relationships import (
    LocationEncounterReference,
    RelationshipIndex,
)
from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    encounter_record_comparison,
    grouped_comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.components import (
    display_name,
    escape_heading,
    escape_table_cell,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    summary_section,
    summary_section_link,
)
from romwiki.renderers.mkdocs.conditional_encounters import (
    conditional_encounter_label,
    conditional_encounter_provenance,
)
from romwiki.renderers.mkdocs.location_components import (
    LOCATION_CATALOG_DESCRIPTION,
    append_connections,
    append_items,
    append_mart_references,
    append_npc_trades,
    append_pokemon_gifts,
    append_script_awarded_items,
    append_shops,
    append_static_encounters,
    append_trainers,
    append_warps,
    item_event_coverage_notice,
    location_filename,
    location_label,
    section_name_provenance_facts,
)
from romwiki.renderers.mkdocs.location_features import encounter_map_feature_rows
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    encounter_route_kind,
    entity_reference,
)
from romwiki.schema.rendering import LocationDataset


def render_encounter_map_location_pages(
    dataset: LocationDataset,
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    encounter_comparison: dict[str, Any] | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = cast(list[dict[str, Any]], dataset["records"])
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                location_filename(record["header_id"])
                for record in records
                if only_pages is None
                or location_filename(record["header_id"]).removesuffix(".md")
                in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    sorted_records = sorted(
        records,
        key=lambda item: (
            item["name"],
            item.get("section_name") or "",
            item["header_id"],
        ),
    )
    same_name_groups: dict[str, list[dict[str, Any]]] = {}
    for record in sorted_records:
        same_name_groups.setdefault(record["name"], []).append(record)
    for index, record in enumerate(sorted_records):
        change = record_comparison(comparison, record["header_id"])
        filename = location_filename(record["header_id"])
        encounters = (
            relationships.location_encounters.get(record["header_id"], ())
            if relationships
            else ()
        )
        conditional_encounters = (
            relationships.location_conditional_encounters.get(record["header_id"], ())
            if relationships
            else ()
        )
        conditional_area_ids = {
            encounter["area_id"] for encounter in conditional_encounters
        }
        ordinary_encounters = tuple(
            encounter
            for encounter in encounters
            if encounter.area_id not in conditional_area_ids
        )
        previous = sorted_records[index - 1] if index else None
        following = (
            sorted_records[index + 1] if index + 1 < len(sorted_records) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_encounter_map_location(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    previous,
                    following,
                    references,
                    ordinary_encounters,
                    conditional_encounters,
                    encounter_comparison,
                    same_name_groups[record["name"]],
                    relationships.location_labels if relationships else None,
                    record["header_id"] in relationships.location_safari_zone_headers
                    if relationships
                    else False,
                ),
            )
            page_count += 1
        route_id = filename.removesuffix(".md")
        fallback_label = f"{location_label(record)} — {route_id}"
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
        feature_rows = [
            row
            for row in encounter_map_feature_rows(
                record,
                has_ordinary_encounters=bool(ordinary_encounters),
                conditional_encounters=conditional_encounters,
            )
            if row[3]
        ]
        catalog_records.append(
            add_change_status(
                {
                    "id": record["header_id"],
                    "route_id": route_id,
                    "label": record["name"],
                    "location_name": record["name"],
                    "section_name": record.get("section_name"),
                    "url": route_id + "/",
                    "features": [key for key, *_ in feature_rows],
                    "feature_anchors": {
                        key: anchor for key, _, anchor, *_ in feature_rows
                    },
                    "search_text": (
                        f"{record['name']} {record.get('section_name') or ''} "
                        f"{record.get('internal_name') or ''} {route_id}".lower()
                    ),
                },
                change,
            )
        )
    write_catalog(output_root, "locations", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Locations",
            LOCATION_CATALOG_DESCRIPTION + item_event_coverage_notice(records),
            "locations",
            fallback_links,
        ),
    )
    return page_count


def _render_encounter_map_location(
    record: dict[str, Any],
    change: dict[str, Any] | None,
    baseline_name: str | None,
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    references: ReferenceIndex | None = None,
    encounters: tuple[LocationEncounterReference, ...] = (),
    conditional_encounters: tuple[dict[str, Any], ...] = (),
    encounter_comparison: dict[str, Any] | None = None,
    same_name_records: list[dict[str, Any]] | None = None,
    location_labels: Mapping[int, str] | None = None,
    is_safari_zone_map: bool = False,
) -> str:
    source_file = f"locations/{location_filename(record['header_id'])}"
    facts = [f"<div><dt>Map header</dt><dd>header-{record['header_id']:03}</dd></div>"]
    if record.get("section_name"):
        facts[0:0] = [
            f"<div><dt>Location</dt><dd>{escape_table_cell(record['name'])}</dd></div>",
            f"<div><dt>Section</dt><dd>{escape_table_cell(record['section_name'])}</dd></div>",
        ]
    for catalog_key, label, anchor, present, value in encounter_map_feature_rows(
        record,
        has_ordinary_encounters=bool(encounters),
        conditional_encounters=conditional_encounters,
    ):
        if not present:
            continue
        display_value = (
            f"map index {record['encounter_map_index']}"
            if catalog_key == "encounters" and encounters
            else value
        )
        facts.append(
            f"<div><dt>{label}</dt><dd>"
            f"{summary_section_link(display_value, anchor)}</dd></div>"
        )
    lines = [
        f"# {escape_heading(location_label(record))}",
        "",
        *summary_section("rw-location-summary", facts),
    ]
    if is_safari_zone_map:
        safari_link = ROUTES.markdown_link(
            entity_reference(
                "encounter_variant",
                SAFARI_ZONE_ROUTE,
                "Safari Zone encounters",
                SAFARI_ZONE_ROUTE,
            ),
            source_file,
        )
        lines.extend(
            [
                "## Wild encounters",
                "",
                "This map is one of the Safari Zone's physical positions. Which "
                f"area type currently occupies it is player-configurable; see "
                f"{safari_link} for every area's encounter tables.",
                "",
            ]
        )
    elif encounters or conditional_encounters:
        lines.extend(["## Wild encounters", ""])
        _append_encounter_variants(
            lines, encounters, conditional_encounters, source_file, record["name"]
        )
    append_items(lines, record["items"], source_file, references)
    append_script_awarded_items(
        lines, record.get("script_awarded_items", []), source_file, references
    )
    append_shops(lines, record.get("shops", []), source_file, references)
    append_mart_references(lines, record.get("mart_references", []), source_file)
    append_npc_trades(lines, record.get("npc_trades", []), source_file, references)
    append_static_encounters(
        lines, record["static_encounters"], source_file, references
    )
    append_pokemon_gifts(
        lines, record.get("pokemon_gifts", []), source_file, references
    )
    append_trainers(lines, record["trainers"], source_file)
    append_warps(lines, record["warps"], source_file, location_labels)
    append_connections(lines, record["connections"], source_file, location_labels)
    _append_same_name_locations(lines, record, same_name_records or [], source_file)
    lines.extend(
        grouped_comparison_section(
            [
                ("Location", change),
                *(
                    (
                        conditional_encounter_label(encounter),
                        encounter_record_comparison(encounter_comparison, encounter),
                    )
                    for encounter in conditional_encounters
                ),
            ],
            baseline_name,
            source_file,
            references,
        )
    )
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Map header", f"`header-{record['header_id']:03}`"),
                        *(section_name_provenance_facts(record)),
                        *(
                            (("Internal map", f"`{record['internal_name']}`"),)
                            if record.get("internal_name")
                            else ()
                        ),
                        ("Matrix ID", f"`{record['matrix_id']}`"),
                        *(
                            (
                                (
                                    "Overworld event member",
                                    f"`{record['overworld_file_id']}`",
                                ),
                            )
                            if record.get("overworld_file_id") is not None
                            else ()
                        ),
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
                "real outdoor connections, and real field items (visible and "
                "hidden) are decoded. Literal script-awarded items remain a "
                "separate source. Static encounters are listed when the "
                "profile supplies verified script offsets. "
                "Script-linked shops are decoded from their real local "
                "dispatcher functions.",
                *(
                    fact
                    for encounter in conditional_encounters
                    for fact in conditional_encounter_provenance(encounter)
                ),
            ]
        )
    )
    lines.extend(
        record_navigation_for(
            "location",
            f"locations/{location_filename(record['header_id']).removesuffix('.md')}/",
            previous,
            following,
            aria_label="Location navigation",
            identity=lambda value: value["header_id"],
            route_key=lambda value: value["header_id"],
            label=location_label,
        )
    )
    return "\n".join(lines)


def _append_encounter_variants(
    lines: list[str],
    encounters: tuple[LocationEncounterReference, ...],
    conditional_encounters: tuple[dict[str, Any], ...],
    source_file: str,
    location_name: str,
) -> None:
    """Append one Wild encounters table covering both ordinary methods and
    map-owned conditional sources (Headbutt/Hidden Grotto/Daily Swarm), each
    linking out to its own encounters/ page. A single shared table -- rather
    than one per source -- avoids stacking multiple differently-shaped tables
    under the same heading.
    """
    grouped: dict[int | str, list[LocationEncounterReference]] = {}
    for encounter in encounters:
        grouped.setdefault(encounter.encounter_route_key, []).append(encounter)
    lines.extend(
        [
            "| Seasons | Encounter area | Version |",
            "| ------- | -------------- | ------- |",
        ]
    )
    for route_key, related in grouped.items():
        encounter = related[0]
        label = location_name
        seasons = list(
            dict.fromkeys(
                display_name(value.season)
                for value in related
                if value.season is not None
            )
        )
        all_versions = list(
            dict.fromkeys(
                display_name(version) for value in related for version in value.versions
            )
        )
        link = ROUTES.markdown_link(
            entity_reference(
                encounter_route_kind(route_key),
                encounter.area_id,
                label,
                route_key,
            ),
            source_file,
        )
        versions = (
            " / ".join(display_name(value) for value in encounter.versions) or "—"
        )
        lines.append(
            f"| {' / '.join(seasons) or 'All'} | "
            f"{link} | {' / '.join(all_versions) or versions} |"
        )
    for conditional_encounter in conditional_encounters:
        route_key = encounter_route_key(conditional_encounter)
        link = ROUTES.markdown_link(
            entity_reference(
                encounter_route_kind(route_key),
                conditional_encounter["area_id"],
                conditional_encounter_label(conditional_encounter),
                route_key,
            ),
            source_file,
        )
        lines.append(f"| — | {link} | — |")
    lines.append("")


def _append_same_name_locations(
    lines: list[str],
    record: dict[str, Any],
    same_name_records: list[dict[str, Any]],
    source_file: str,
) -> None:
    related = [
        candidate
        for candidate in same_name_records
        if candidate["header_id"] != record["header_id"]
    ]
    if not related:
        return
    lines.extend(
        [
            "## Same-name locations",
            "",
            (
                "These ROM map-header records share the same display name. "
                "They may represent different rooms or map sections."
            ),
            "",
            "| Location | Section | Map ID | Encounter ID |",
            "| -------- | ------- | ------ | ------------ |",
        ]
    )
    for candidate in related:
        header_id = candidate["header_id"]
        link = ROUTES.markdown_link(
            entity_reference("location", header_id, candidate["name"], header_id),
            source_file,
        )
        encounter_index = candidate.get("encounter_map_index")
        lines.append(
            f"| {link} | {candidate.get('section_name') or '—'} | "
            f"`header-{header_id:03}` | "
            f"{encounter_index if encounter_index is not None else '—'} |"
        )
    lines.append("")
