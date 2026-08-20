from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment.special_encounters import special_encounter_groups
from romwiki.pipeline.semantics.encounter_identity import (
    CONDITIONAL_ENCOUNTER_SOURCES,
    MAP_OWNED_CONDITIONAL_SOURCES,
    SAFARI_ZONE_ROUTE,
    EncounterSourceType,
    conditional_encounter_key,
    encounter_route_key,
)
from romwiki.pipeline.transforms.relationships import (
    EncounterLocationReference,
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
    comparison_notes_section,
    comparison_section,
    encounter_record_comparison,
)
from romwiki.renderers.mkdocs.components import (
    MarkdownColumn,
    aggregate_slots,
    display_name,
    heading_anchor,
    level_range,
    markdown_table,
    markdown_table_from_cells,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_type_cell,
    rom_record_source,
    sprite_with_link,
    summary_section,
    summary_section_link,
    tab_dimension,
    table_sprite_cell,
    version_variant_records,
)
from romwiki.renderers.mkdocs.conditional_encounters import (
    append_daily_swarm,
    append_headbutt_encounters,
    append_hidden_grotto,
    append_safari_area,
    conditional_encounter_label,
    conditional_encounter_provenance,
    disambiguated_conditional_labels,
    safari_provenance,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    encounter_route_kind,
    entity_reference,
    unique_references,
)
from romwiki.schema.rendering import EncounterRenderRecord, RenderDataset
from romwiki.util.errors import SiteError

# Display labels for the seasonal encounter-method keys emitted by supporting engines.
_SEASONAL_METHOD_LABELS = {
    "grass_cave": "Grass/Cave",
    "doubles_grass": "Doubles Grass",
    "shaking_spots": "Shaking Spots",
    "surfing": "Surfing",
    "surfing_spots": "Surfing Spots",
    "fishing": "Fishing",
    "fishing_spots": "Fishing Spots",
}
_SEASONS = ("spring", "summer", "autumn", "winter")
_ENCOUNTER_SLOT_COLUMNS = (
    MarkdownColumn("Pokémon"),
    MarkdownColumn("Type"),
    MarkdownColumn("Levels", "right"),
    MarkdownColumn("Chance", "right"),
)


def render_encounter_pages(
    dataset: RenderDataset[EncounterRenderRecord],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    engine_id = dataset.get("engine")
    encounter_format = (
        get_engine(engine_id).formats.encounters if isinstance(engine_id, str) else None
    )
    seasonal = (
        encounter_format == "seasonal"
        if encounter_format is not None
        else bool(dataset.get("records")) and "season" in dataset["records"][0]
    )
    dataset_dict = cast(dict[str, Any], dataset)
    if seasonal:
        return _render_seasonal_encounter_pages(
            dataset_dict,
            output_root,
            comparison,
            references,
            relationships,
            only_pages=only_pages,
        )
    if encounter_format == "method-table":
        return _render_method_table_encounter_pages(
            dataset_dict,
            output_root,
            comparison,
            references,
            only_pages=only_pages,
        )
    all_records = cast(list[dict[str, Any]], dataset["records"])
    records = [record for record in all_records if record["active"]]
    safari_records = [
        record
        for record in records
        if record.get("source_type") == EncounterSourceType.SAFARI_ZONE
    ]
    conditional_records = sorted(
        (
            record
            for record in records
            if record.get("source_type") in MAP_OWNED_CONDITIONAL_SOURCES
        ),
        key=lambda item: (item.get("source_type"), item["area_id"]),
    )
    records = [
        record
        for record in records
        if record.get("source_type") not in CONDITIONAL_ENCOUNTER_SOURCES
    ]
    # Encounter table entries with no map header pointing at them are ROM
    # padding/unused data -- not a place a player can reach -- so they're
    # dropped rather than rendered under a fallback "Encounter Area NNN" name.
    linked = [record for record in records if record.get("locations")]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"area-{record['area_id']:03}.md"
                for record in linked
                if only_pages is None or f"area-{record['area_id']:03}" in only_pages
            ),
            *(
                (
                    f"{SAFARI_ZONE_ROUTE}.md",
                    *(f"{encounter_route_key(record)}.md" for record in safari_records),
                )
                if safari_records and _safari_page_selected(safari_records, only_pages)
                else ()
            ),
            *(
                f"{encounter_route_key(record)}.md"
                for record in conditional_records
                if _conditional_page_selected(record, only_pages)
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    name_counts = Counter(record["name"] for record in linked)
    sorted_linked = sorted(linked, key=lambda item: (item["name"], item["area_id"]))
    for index, record in enumerate(sorted_linked):
        change = encounter_record_comparison(comparison, record)
        filename = f"area-{record['area_id']:03}.md"
        previous = sorted_linked[index - 1] if index else None
        following = sorted_linked[index + 1] if index + 1 < len(sorted_linked) else None
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_area(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    previous,
                    following,
                ),
            )
            page_count += 1
        label = record["name"]
        if name_counts[label] > 1:
            internal_names = ", ".join(
                dict.fromkeys(
                    location["internal_name"] for location in record["locations"]
                )
            )
            label = f"{label} — {internal_names}"
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "encounter", record["area_id"], label, record["area_id"]
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _catalog_record(record, filename.removesuffix(".md") + "/", True, change)
        )
    if safari_records and _safari_page_selected(safari_records, only_pages):
        write_text(
            output_root / f"{SAFARI_ZONE_ROUTE}.md",
            _render_safari_zone_index(safari_records, references, relationships),
        )
        page_count += 1
        for index, record in enumerate(safari_records):
            filename = f"{encounter_route_key(record)}.md"
            if only_pages is None or filename.removesuffix(".md") in only_pages:
                write_text(
                    output_root / filename,
                    _render_safari_zone_area_page(
                        record,
                        comparison,
                        comparison.get("baseline") if comparison else None,
                        references,
                        _conditional_sibling(safari_records, index, -1),
                        _conditional_sibling(safari_records, index, 1),
                    ),
                )
                page_count += 1
    for record in safari_records:
        route_id = conditional_encounter_key(record)
        change = encounter_record_comparison(comparison, record)
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    encounter_route_kind(encounter_route_key(record)),
                    record["area_id"],
                    record["name"],
                    encounter_route_key(record),
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _safari_catalog_record(
                record,
                _encounter_catalog_url(record),
                change,
                route_id=route_id,
            )
        )
    page_count += _render_conditional_encounter_records(
        conditional_records,
        comparison,
        references,
        only_pages,
        output_root,
        fallback_links,
        catalog_records,
    )
    write_catalog(output_root, "encounters", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Wild encounters",
            "Exact encounter tables linked to their in-game map headers.",
            "encounters",
            fallback_links,
        ),
    )
    return page_count


def _safari_slots(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        slot
        for _, value in version_variant_records(record)
        for method in value["methods"].values()
        for slot in (
            *(slot for pool in method["base_pools"].values() for slot in pool),
            *(
                slot
                for encounter in method["block_encounters"]
                for slot in encounter["times"].values()
            ),
        )
    ]


def _safari_catalog_record(
    record: dict[str, Any],
    filename: str,
    change: dict[str, Any] | None,
    *,
    route_id: str,
) -> dict[str, Any]:
    slots = _safari_slots(record)
    names = list(dict.fromkeys(slot["pokemon"]["name"] for slot in slots))
    methods = [
        display_name(method)
        for method in next(iter(version_variant_records(record)))[1]["methods"]
    ]
    # `append_safari_area` renders each method as an unlabeled heading, so its
    # anchor is mkdocs' default slug of that same heading text -- mirroring how
    # `_MethodAccumulator.add` derives anchors for ordinary encounter methods.
    method_anchors = {label: heading_anchor(label) for label in methods}
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": record["name"],
            "url": filename,
            "locations": ["Safari Zone"],
            "methods": methods,
            "method_anchors": method_anchors,
            "pokemon": names,
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(
                    _pokemon_reference(slot["pokemon"]) for slot in slots
                )
            ],
            "method_pokemon": {
                display_name(method_name): list(
                    dict.fromkeys(
                        slot["pokemon"]["name"]
                        for _, value in version_variant_records(record)
                        for slot in (
                            *(
                                slot
                                for pool in value["methods"][method_name][
                                    "base_pools"
                                ].values()
                                for slot in pool
                            ),
                            *(
                                slot
                                for encounter in value["methods"][method_name][
                                    "block_encounters"
                                ]
                                for slot in encounter["times"].values()
                            ),
                        )
                    )
                )
                for method_name in next(iter(version_variant_records(record)))[1][
                    "methods"
                ]
            },
            "min_level": min(slot["level"] for slot in slots),
            "max_level": max(slot["level"] for slot in slots),
            "referenced": False,
            "search_text": " ".join((record["name"], *names, *methods)).lower(),
        },
        change,
    )


def _encounter_catalog_url(record: dict[str, Any]) -> str:
    route_key = encounter_route_key(record)
    reference = entity_reference(
        encounter_route_kind(route_key), record["area_id"], record["name"], route_key
    )
    href = ROUTES.published_href(reference, "encounters/")
    if href is None:
        raise SiteError(f"Encounter record {record['area_id']} has no route")
    return href


def _safari_page_selected(
    records: list[dict[str, Any]], only_pages: frozenset[str] | None
) -> bool:
    return (
        only_pages is None
        or SAFARI_ZONE_ROUTE in only_pages
        or any(
            conditional_encounter_key(record) in only_pages
            or f"area-{record['area_id']:03}" in only_pages
            for record in records
        )
    )


def _conditional_page_selected(
    record: dict[str, Any], only_pages: frozenset[str] | None
) -> bool:
    # area_id is assigned once across every encounter record in the dataset
    # (ordinary and conditional alike -- see extraction/encounters.py's
    # first_area_id accumulation), so this `area-NNN` form can't collide with
    # an unrelated record; it just lets a dev-pages.toml entry select a
    # conditional page by numeric ID instead of its route slug, the same
    # convenience `_safari_page_selected` already offered.
    return (
        only_pages is None
        or str(encounter_route_key(record)) in only_pages
        or f"area-{record['area_id']:03}" in only_pages
    )


def _conditional_sibling(
    records: list[dict[str, Any]], index: int, offset: int
) -> dict[str, Any] | None:
    """The adjacent same-source-type record for prev/next navigation.

    `records` is sorted by `(source_type, area_id)`, so a same-source-type
    neighbor is always adjacent when one exists.
    """
    neighbor_index = index + offset
    if not 0 <= neighbor_index < len(records):
        return None
    neighbor = records[neighbor_index]
    if neighbor.get("source_type") != records[index].get("source_type"):
        return None
    return neighbor


def _render_conditional_encounter_records(
    conditional_records: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    references: ReferenceIndex | None,
    only_pages: frozenset[str] | None,
    output_root: Path,
    fallback_links: list[str],
    catalog_records: list[dict[str, Any]],
) -> int:
    """Write each conditional encounter record's own page plus its catalog
    entry and index fallback link. Shared by the ordinary and seasonal
    render paths, which both attach the same map-owned conditional sources
    (Headbutt/Hidden Grotto/Daily Swarm) the same way.
    """
    baseline_name = comparison.get("baseline") if comparison else None
    labels = disambiguated_conditional_labels(conditional_records)
    page_count = 0
    for index, record in enumerate(conditional_records):
        change = encounter_record_comparison(comparison, record)
        route_key = encounter_route_key(record)
        filename = f"{route_key}.md"
        previous = _conditional_sibling(conditional_records, index, -1)
        following = _conditional_sibling(conditional_records, index, 1)
        if _conditional_page_selected(record, only_pages):
            write_text(
                output_root / filename,
                _render_conditional_encounter_page(
                    record,
                    comparison,
                    baseline_name,
                    references,
                    previous,
                    following,
                    labels,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    encounter_route_kind(route_key),
                    record["area_id"],
                    labels[record["area_id"]],
                    route_key,
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _conditional_catalog_record(
                record, f"{route_key}/", change, labels[record["area_id"]]
            )
        )
    return page_count


def _conditional_slots(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a conditional encounter record's Pokémon slots across every
    version variant, for building its catalog entry."""
    source_type = record.get("source_type")
    slots: list[dict[str, Any]] = []
    for _, value in version_variant_records(record):
        if source_type == EncounterSourceType.HEADBUTT:
            for pool in value["pools"].values():
                slots.extend(pool)
        elif source_type == EncounterSourceType.HIDDEN_GROTTO:
            slots.extend(value["pokemon"])
        elif source_type == EncounterSourceType.DAILY_SWARM:
            slots.append(value)
    return slots


def _conditional_slot_levels(slot: dict[str, Any]) -> tuple[int, int]:
    if "level" in slot:
        return slot["level"], slot["level"]
    return slot["minimum_level"], slot["maximum_level"]


def _conditional_catalog_record(
    record: dict[str, Any],
    filename: str,
    change: dict[str, Any] | None,
    label: str,
) -> dict[str, Any]:
    slots = _conditional_slots(record)
    names = list(dict.fromkeys(slot["pokemon"]["name"] for slot in slots))
    location = record.get("location") or {}
    location_name = location.get("name")
    route_id = filename.removesuffix("/")
    levels = [_conditional_slot_levels(slot) for slot in slots]
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": label,
            "url": filename,
            "locations": [location_name] if location_name else [],
            "methods": [],
            "method_anchors": {},
            "pokemon": names,
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(
                    _pokemon_reference(slot["pokemon"]) for slot in slots
                )
            ],
            "method_pokemon": {},
            "min_level": min((minimum for minimum, _ in levels), default=None),
            "max_level": max((maximum for _, maximum in levels), default=None),
            "referenced": True,
            "search_text": " ".join(
                (
                    label,
                    route_id,
                    *((location_name,) if location_name else ()),
                    *names,
                )
            ).lower(),
        },
        change,
    )


def _conditional_location_lines(record: dict[str, Any], source_file: str) -> list[str]:
    """Build the "Map headers" section for a conditional encounter page.

    Returned as its own line list (rather than appended in place) so the
    caller can splice it in right after the page's intro -- the same
    position ordinary and seasonal encounter pages already put their own
    Map headers section, before the encounter tables rather than after them.
    """
    location = record.get("location")
    if not isinstance(location, dict):
        return []
    reference = entity_reference(
        "location", location["header_id"], location["name"], location["header_id"]
    )
    return [
        "## Map headers",
        "",
        "| Location | Map ID | Internal ID |",
        "| -------- | ------ | ----------- |",
        f"| {ROUTES.markdown_link(reference, source_file)} "
        f"| `header-{location['header_id']:03}` | `{location['internal_name']}` |",
        "",
    ]


def _append_conditional_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    labels: dict[int, str] | None = None,
) -> None:
    route_key = encounter_route_key(record)

    def label(value: Mapping[str, Any]) -> str:
        if labels is not None and value["area_id"] in labels:
            return labels[value["area_id"]]
        return conditional_encounter_label(value)

    lines.extend(
        record_navigation_for(
            encounter_route_kind(route_key),
            f"encounters/{route_key}/",
            previous,
            following,
            aria_label="Wild encounter navigation",
            identity=lambda value: value["area_id"],
            route_key=encounter_route_key,
            label=label,
        )
    )


def _render_conditional_encounter_page(
    record: dict[str, Any],
    comparison: dict[str, Any] | None,
    baseline_name: str | None,
    references: ReferenceIndex | None,
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    labels: dict[int, str],
) -> str:
    route_key = encounter_route_key(record)
    source_file = f"encounters/{route_key}.md"
    lines: list[str] = []
    location_lines = _conditional_location_lines(record, source_file)
    source_type = record.get("source_type")
    if source_type == EncounterSourceType.HEADBUTT:
        append_headbutt_encounters(
            lines,
            record,
            source_file,
            references,
            heading_level=1,
            extra_intro_lines=tuple(location_lines),
        )
    elif source_type == EncounterSourceType.HIDDEN_GROTTO:
        append_hidden_grotto(
            lines,
            record,
            source_file,
            references,
            heading_level=1,
            heading=labels[record["area_id"]],
            extra_intro_lines=tuple(location_lines),
        )
    elif source_type == EncounterSourceType.DAILY_SWARM:
        append_daily_swarm(
            lines,
            record,
            source_file,
            references,
            heading_level=1,
            extra_intro_lines=tuple(location_lines),
        )
    else:
        raise SiteError(f"Unsupported conditional encounter source: {source_type!r}")
    lines.extend(
        comparison_section(
            encounter_record_comparison(comparison, record),
            baseline_name,
            source_file,
            references,
        )
    )
    lines.extend(provenance_section(conditional_encounter_provenance(record)))
    _append_conditional_record_navigation(lines, record, previous, following, labels)
    return "\n".join(lines).rstrip() + "\n"


def _render_safari_zone_index(
    records: list[dict[str, Any]],
    references: ReferenceIndex | None,
    relationships: RelationshipIndex | None = None,
) -> str:
    """Render the Safari Zone overview page.

    Each area's full encounter data is rendered on its own page (see
    `_render_safari_zone_area_page`) rather than combined here, since the
    combined page's image count pushed several sites over the site audit's
    HTML page-size limit.
    """
    source_file = f"encounters/{SAFARI_ZONE_ROUTE}.md"
    lines = [
        "# Safari Zone encounters",
        "",
        "Safari area types can be moved among the zone's physical positions. "
        "The sections below therefore describe area configurations rather than "
        "assigning them to fixed map headers.",
        "",
    ]
    header_links = _safari_physical_maps(records, relationships, source_file)
    if header_links:
        lines.extend(
            [
                f"These area types occupy {len(header_links)} physical maps: "
                + " / ".join(header_links)
                + ". Which map currently holds which area is player-configurable "
                "and not decoded here.",
                "",
            ]
        )
    lines.extend(["## Areas", ""])
    lines.extend(
        "- "
        + ROUTES.markdown_link(
            entity_reference(
                encounter_route_kind(encounter_route_key(record)),
                record["area_id"],
                record["area_name"],
                encounter_route_key(record),
            ),
            source_file,
        )
        for record in records
    )
    lines.extend(["", *provenance_section(safari_provenance(records))])
    return "\n".join(lines).rstrip() + "\n"


def _render_safari_zone_area_page(
    record: dict[str, Any],
    comparison: dict[str, Any] | None,
    baseline_name: str | None,
    references: ReferenceIndex | None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> str:
    source_file = f"encounters/{encounter_route_key(record)}.md"
    lines: list[str] = []
    append_safari_area(lines, record, source_file, heading_level=1)
    lines.extend(
        comparison_section(
            encounter_record_comparison(comparison, record),
            baseline_name,
            source_file,
            references,
        )
    )
    lines.extend(provenance_section(safari_provenance([record])))
    _append_conditional_record_navigation(lines, record, previous, following)
    return "\n".join(lines).rstrip() + "\n"


def _safari_physical_maps(
    records: list[dict[str, Any]],
    relationships: RelationshipIndex | None,
    source_file: str,
) -> list[str]:
    if not records or relationships is None:
        return []
    return [
        ROUTES.markdown_link(
            entity_reference(
                "location", header_id, f"header-{header_id:03}", header_id
            ),
            source_file,
        )
        for header_id in sorted(relationships.location_safari_zone_headers)
    ]


class _MethodAccumulator:
    """Collects per-method encounter slots into the fields shared by the
    standard and seasonal encounter catalog records, so the two builders
    don't each hand-roll the same species/level/anchor bookkeeping.
    """

    def __init__(self) -> None:
        self.methods: list[str] = []
        self.method_anchors: dict[str, str] = {}
        self.method_pokemon: dict[str, list[str]] = {}
        self.species: list[str] = []
        self.pokemon_refs: list[Any] = []
        self.levels: list[int] = []

    def add(self, label: str, anchor: str, method: dict[str, Any] | None) -> None:
        if not method or not method.get("rate"):
            return
        self.methods.append(label)
        self.method_anchors[label] = anchor
        method_species = self.method_pokemon.setdefault(label, [])
        for slot in method["slots"]:
            pokemon = slot.get("pokemon")
            if pokemon:
                self.species.append(pokemon["name"])
                method_species.append(pokemon["name"])
                self.pokemon_refs.append(_pokemon_reference(pokemon))
            if "level" in slot:
                self.levels.append(slot["level"])
            else:
                self.levels.extend((slot["minimum_level"], slot["maximum_level"]))

    def method_pokemon_deduped(self) -> dict[str, list[str]]:
        return {
            label: list(dict.fromkeys(values))
            for label, values in self.method_pokemon.items()
        }


def _catalog_record(
    record: dict[str, Any],
    filename: str,
    referenced: bool,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accumulator = _MethodAccumulator()
    for label, key in (
        ("walking", "walking"),
        ("surf", "surf"),
        ("rock smash", "rock_smash"),
        ("old rod", "old_rod"),
        ("good rod", "good_rod"),
        ("super rod", "super_rod"),
    ):
        accumulator.add(
            label,
            heading_anchor(_method_heading(label, key, record)),
            record.get(key),
        )
    method_pokemon = accumulator.method_pokemon_deduped()
    special_pokemon = _special_pokemon(record["special"])
    special_species = [pokemon["name"] for pokemon in special_pokemon]
    accumulator.pokemon_refs.extend(
        _pokemon_reference(pokemon) for pokemon in special_pokemon
    )
    accumulator.species.extend(special_species)
    accumulator.levels.extend(
        slot["level"]
        for group in special_encounter_groups(record["special"])
        for slot in group.slots
        if slot.get("level") is not None
    )
    if special_species and "walking" in method_pokemon:
        method_pokemon["walking"] = list(
            dict.fromkeys((*method_pokemon["walking"], *special_species))
        )
    location_names = [location["name"] for location in record.get("locations", [])]
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": record["name"],
            "url": filename,
            "locations": list(dict.fromkeys(location_names)),
            "methods": accumulator.methods,
            "method_anchors": accumulator.method_anchors,
            "pokemon": list(dict.fromkeys(accumulator.species)),
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(accumulator.pokemon_refs)
            ],
            "method_pokemon": method_pokemon,
            "min_level": min(accumulator.levels) if accumulator.levels else None,
            "max_level": max(accumulator.levels) if accumulator.levels else None,
            "referenced": referenced,
            "search_text": " ".join(
                (record["name"], route_id, *location_names, *accumulator.species)
            ).lower(),
        },
        change,
    )


def _special_pokemon(special: dict[str, Any]) -> list[dict[str, Any]]:
    return _unique_pokemon(
        pokemon
        for group in special_encounter_groups(special)
        for slot in group.slots
        if isinstance((pokemon := slot.get("pokemon")), dict)
    )


def _unique_pokemon(pokemon: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """De-duplicate a Pokémon list, since the ROM's fixed-size special-encounter
    tuples (e.g. Poké Radar's 4-species table) commonly repeat the same species.
    """
    unique = []
    seen = set()
    for value in pokemon:
        identity = (value.get("id"), value.get("slug"), value["name"])
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(value)
    return unique


def _pokemon_reference(pokemon: dict[str, Any]):
    return entity_reference(
        "pokemon",
        pokemon.get("id", pokemon["slug"]),
        pokemon["name"],
        pokemon.get("slug"),
    )


def _method_heading(label: str, key: str, record: dict[str, Any]) -> str:
    """The exact heading text `_render_area` emits for a given method."""
    if key == "walking" and record.get("walking_variants"):
        return "Walking (Morning)"
    return label.title()


def _render_area(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> str:
    source_file = f"encounters/area-{record['area_id']:03}.md"
    lines = [
        f"# {record['name']}",
        "",
        *_area_summary(record),
    ]
    _append_locations(lines, record.get("locations", []), source_file)
    walking_variants = record.get("walking_variants")
    if walking_variants:
        for period in ("morning", "day", "night"):
            _append_walking(
                lines,
                walking_variants[period],
                source_file,
                references,
                heading=f"Walking ({period.title()})",
            )
    else:
        _append_walking(lines, record["walking"], source_file, references)
    for heading, key in (
        ("Surf", "surf"),
        ("Rock Smash", "rock_smash"),
        ("Old Rod", "old_rod"),
        ("Good Rod", "good_rod"),
        ("Super Rod", "super_rod"),
    ):
        if key in record:
            _append_water(lines, heading, record[key], source_file, references)
    _append_special(lines, record["special"], source_file, references)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    if walking_variants:
        lines.extend(
            provenance_section(
                [
                    rom_record_source(
                        record["provenance"]["archive"],
                        record["provenance"]["member"],
                    ),
                    "Chance percentages are fixed engine weights applied by slot "
                    "position; the ROM encounter records store rates, species, "
                    "and levels.",
                    "Morning, day, and night walking lists and the radio, swarm, "
                    "and fishing replacement species are distinct HGSS fields.",
                ]
            )
        )
        _append_record_navigation(lines, record, previous, following)
        return "\n".join(lines)
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Unown table ID", f"`{record['unown_table_id']}`"),
                        (
                            "Encounter form rates",
                            f"`{record['encounter_form_rates']}`",
                        ),
                    )
                ),
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "Chance percentages are not stored in the ROM's encounter tables — "
                "only each slot's species and level(s) are ROM data — they are "
                "fixed, publicly documented Generation III/IV engine weights "
                "applied by slot position.",
                "Swarm, Day/Night, and Dual-slot replacements substitute a walking "
                "slot's species only; the level and chance shown for them are the "
                "replaced slot's own level and chance, per "
                f"{record['bonus_slot_methodology_source']}.",
                "Encounter form rates is a raw ROM value whose exact purpose isn't "
                "fully understood; it is not a Pokémon species reference (unlike "
                "most other numeric fields on this page) and stays constant across "
                "every encounter area regardless of location.",
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _area_summary(record: dict[str, Any]) -> list[str]:
    methods = [
        (label, key)
        for label, key in (
            ("walking", "walking"),
            ("surf", "surf"),
            ("rock smash", "rock_smash"),
            ("old rod", "old_rod"),
            ("good rod", "good_rod"),
            ("super rod", "super_rod"),
        )
        if record.get(key, {}).get("rate")
    ]
    locations = record.get("locations", [])
    facts = [
        f"<div><dt>Area ID</dt><dd>{record['area_id']}</dd></div>",
        (
            "<div><dt>Methods</dt><dd>"
            + (
                ", ".join(
                    summary_section_link(
                        label.title(),
                        heading_anchor(_method_heading(label, key, record)),
                    )
                    for label, key in methods
                )
                if methods
                else "None"
            )
            + "</dd></div>"
        ),
    ]
    if locations:
        facts.append(
            "<div><dt>Map headers</dt><dd>"
            f"{summary_section_link(len(locations), 'map-headers')}</dd></div>"
        )
    return summary_section(
        "rw-encounter-summary",
        facts,
    )


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "encounter",
            f"encounters/area-{record['area_id']:03}/",
            previous,
            following,
            aria_label="Wild encounter navigation",
            identity=lambda value: value["area_id"],
            route_key=lambda value: value["area_id"],
            label=lambda value: value["name"],
        )
    )


def _append_locations(
    lines: list[str], locations: list[dict[str, Any]], source_file: str
) -> None:
    if not locations:
        return
    lines.extend(
        [
            "## Map headers",
            "",
            "| Location | Map ID | Name ID | Internal ID |",
            "| -------- | ------ | ------: | ----------- |",
        ]
    )
    for location in locations:
        reference = entity_reference(
            "location",
            location["header_id"],
            location["name"],
            location.get("header_id"),
        )
        lines.append(
            f"| {ROUTES.markdown_link(reference, source_file)} "
            f"| `header-{location['header_id']:03}` | "
            f"{location['location_name_id']} | "
            f"`{location['internal_name']}` |"
        )
    lines.append("")


def _append_walking(
    lines: list[str],
    method: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    heading: str = "Walking",
) -> None:
    if not method["rate"]:
        return
    slots = aggregate_slots(method["slots"], "level")
    lines.extend([f"## {heading}", "", f"Encounter rate: {method['rate']}", ""])
    lines.extend(
        markdown_table_from_cells(
            _ENCOUNTER_SLOT_COLUMNS,
            (
                (
                    sprite_with_link(
                        table_sprite_cell((slot["pokemon"] or {}).get("sprite")),
                        _pokemon_link(slot["pokemon"], source_file),
                    ),
                    _slot_type_cell(slot["pokemon"], references),
                    level_range(slot["minimum_level"], slot["maximum_level"]),
                    f"{slot['chance']}%",
                )
                for slot in slots
            ),
        )
    )


def _append_water(
    lines: list[str],
    heading: str,
    method: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not method["rate"]:
        return
    slots = aggregate_slots(method["slots"], "minimum_level", "maximum_level")
    lines.extend([f"## {heading}", "", f"Encounter rate: {method['rate']}", ""])
    lines.extend(
        markdown_table_from_cells(
            _ENCOUNTER_SLOT_COLUMNS,
            (
                (
                    sprite_with_link(
                        table_sprite_cell((slot["pokemon"] or {}).get("sprite")),
                        _pokemon_link(slot["pokemon"], source_file),
                    ),
                    _slot_type_cell(slot["pokemon"], references),
                    level_range(slot["minimum_level"], slot["maximum_level"]),
                    f"{slot['chance']}%",
                )
                for slot in slots
            ),
        )
    )


def _append_special(
    lines: list[str],
    special: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    groups = special_encounter_groups(special)
    unown_forms = special.get("unown_forms") or []
    if not groups and not unown_forms:
        return
    lines.extend(["## Special encounters", ""])
    for group in groups:
        lines.extend([f"### {group.label}", ""])
        if group.key == "radar":
            lines.extend(
                [
                    "Only appears for one specific Poké Radar shake outcome; most "
                    "radar encounters instead continue the current chain's species "
                    "rather than drawing from this table, so no fixed level or "
                    "chance applies here.",
                    "",
                ]
            )
        if group.slotted:
            entries = aggregate_slots(list(group.slots), "level")
            lines.extend(
                markdown_table_from_cells(
                    _ENCOUNTER_SLOT_COLUMNS,
                    (
                        (
                            sprite_with_link(
                                table_sprite_cell(entry["pokemon"].get("sprite")),
                                _pokemon_link(entry["pokemon"], source_file),
                            ),
                            _slot_type_cell(entry["pokemon"], references),
                            level_range(entry["minimum_level"], entry["maximum_level"]),
                            f"{entry['chance']}%",
                        )
                        for entry in entries
                    ),
                )
            )
            continue
        pokemon = _unique_pokemon(
            value
            for slot in group.slots
            if isinstance((value := slot.get("pokemon")), dict)
        )
        lines.extend(
            markdown_table(
                ["| Pokémon | Type |", "| ------- | ---- |"],
                [
                    f"| {sprite_with_link(table_sprite_cell(value.get('sprite')), _pokemon_link(value, source_file))} | "
                    f"{_slot_type_cell(value, references)} |"
                    for value in pokemon
                ],
            )
        )
    if unown_forms:
        lines.extend(
            [
                "### Unown forms",
                "",
                "Unown always shows the generic sprite in the tables above — "
                "the ROM's encounter slots only store species and level, "
                "never which letter. The letter is chosen per individual "
                "Pokémon when it's encountered and isn't derivable from this "
                "data. This room's Unown table does constrain which letters "
                "are possible here:",
                "",
                ", ".join(unown_forms),
                "",
            ]
        )


# Generation III has no seasons and no Generation IV-only bonus-slot
# mechanics (swarm/day/night/radar/dual-slot/Unown) -- every method stores
# an explicit min/max level range per slot (see `schema/encounters.py`'s
# `MethodEncounterArea`), so this renders each present method with the same
# generic `_append_water` table the conditional path already uses for its
# own min/max-level methods (surf/rod), rather than reusing the Generation
# IV-shaped `_render_area`/`_catalog_record`, which assume fields (`special`,
# `walking_variants`, `unown_table_id`) this engine's records never have.
_METHOD_TABLE_LABELS = {
    "land": "Land",
    "water": "Water",
    "rock_smash": "Rock Smash",
    "fishing": "Fishing",
}


def _render_method_table_encounter_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None,
    references: ReferenceIndex | None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    # Unlike the conditional path, an area with no map header pointing at
    # it is still rendered here: this engine has no location/map-header
    # system implemented yet, so every record legitimately has empty
    # `locations` (see `pipeline/extraction/encounters.py`'s method-table
    # branch) -- that's not evidence of unused ROM padding the way it is
    # for the NDS engines the conditional path was written for.
    records = [record for record in dataset["records"] if record["active"]]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"area-{record['area_id']:03}"
                for record in records
                if only_pages is None or f"area-{record['area_id']:03}" in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    sorted_records = sorted(records, key=lambda item: (item["name"], item["area_id"]))
    for index, record in enumerate(sorted_records):
        change = encounter_record_comparison(comparison, record)
        filename = f"area-{record['area_id']:03}.md"
        previous = sorted_records[index - 1] if index else None
        following = (
            sorted_records[index + 1] if index + 1 < len(sorted_records) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_method_table_area(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    previous,
                    following,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "encounter", record["area_id"], record["name"], record["area_id"]
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _method_table_catalog_record(
                record, filename.removesuffix(".md") + "/", True, change
            )
        )
    write_catalog(output_root, "encounters", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Wild encounters",
            "Exact encounter tables decoded from the ROM's own wild-encounter archive.",
            "encounters",
            fallback_links,
        ),
    )
    return page_count


def _method_table_catalog_record(
    record: dict[str, Any],
    filename: str,
    referenced: bool,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accumulator = _MethodAccumulator()
    for key, label in _METHOD_TABLE_LABELS.items():
        accumulator.add(label, heading_anchor(label), record.get(key))
    method_pokemon = accumulator.method_pokemon_deduped()
    location_names = [location["name"] for location in record.get("locations", [])]
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": record["name"],
            "url": filename,
            "locations": list(dict.fromkeys(location_names)),
            "methods": accumulator.methods,
            "method_anchors": accumulator.method_anchors,
            "pokemon": list(dict.fromkeys(accumulator.species)),
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(accumulator.pokemon_refs)
            ],
            "method_pokemon": method_pokemon,
            "min_level": min(accumulator.levels) if accumulator.levels else None,
            "max_level": max(accumulator.levels) if accumulator.levels else None,
            "referenced": referenced,
            "search_text": " ".join(
                (record["name"], route_id, *location_names, *accumulator.species)
            ).lower(),
        },
        change,
    )


def _render_method_table_area(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> str:
    source_file = f"encounters/area-{record['area_id']:03}.md"
    lines = [
        f"# {record['name']}",
        "",
        *_method_table_area_summary(record),
    ]
    _append_locations(lines, record.get("locations", []), source_file)
    for key, label in _METHOD_TABLE_LABELS.items():
        if key in record:
            _append_water(lines, label, record[key], source_file, references)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "Chance percentages are not stored in the ROM's encounter tables — "
                "only each slot's species and level range are ROM data — they are "
                "fixed, publicly documented Generation III engine weights applied "
                "by slot position.",
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _method_table_area_summary(record: dict[str, Any]) -> list[str]:
    methods = [
        label
        for key, label in _METHOD_TABLE_LABELS.items()
        if record.get(key, {}).get("rate")
    ]
    locations = record.get("locations", [])
    facts = [
        f"<div><dt>Area ID</dt><dd>{record['area_id']}</dd></div>",
        (
            "<div><dt>Methods</dt><dd>"
            + (
                ", ".join(
                    summary_section_link(label, heading_anchor(label))
                    for label in methods
                )
                if methods
                else "None"
            )
            + "</dd></div>"
        ),
    ]
    if locations:
        facts.append(
            "<div><dt>Map headers</dt><dd>"
            f"{summary_section_link(len(locations), 'map-headers')}</dd></div>"
        )
    return summary_section("rw-encounter-summary", facts)


def _slot_type_cell(
    pokemon: dict[str, Any] | None, references: ReferenceIndex | None
) -> str:
    return reference_type_cell("pokemon", (pokemon or {}).get("id"), references)


def _pokemon_link(pokemon: dict[str, Any] | None, source_file: str) -> str:
    if pokemon is None:
        return "None"
    return ROUTES.markdown_link(_pokemon_reference(pokemon), source_file)


def _render_seasonal_encounter_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None,
    references: ReferenceIndex | None,
    relationships: RelationshipIndex | None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    active_records = [record for record in dataset["records"] if record["active"]]
    conditional_records = sorted(
        (
            record
            for record in active_records
            if record.get("source_type") in MAP_OWNED_CONDITIONAL_SOURCES
        ),
        key=lambda item: (item.get("source_type"), item["area_id"]),
    )
    active_records = [
        record
        for record in active_records
        if record.get("source_type") not in CONDITIONAL_ENCOUNTER_SOURCES
    ]
    grouped: dict[int, list[dict[str, Any]]] = {}
    for record in active_records:
        grouped.setdefault(record["map_index"], []).append(record)
    groups = [
        sorted(values, key=_seasonal_record_sort_key)
        for _, values in sorted(grouped.items())
    ]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{encounter_route_key(records[0])}.md"
                for records in groups
                if _seasonal_page_selected(records, only_pages)
            ),
            *(
                f"{encounter_route_key(record)}.md"
                for record in conditional_records
                if _conditional_page_selected(record, only_pages)
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    locations_by_route: dict[int | str, tuple[EncounterLocationReference, ...]] = {}
    same_name_groups: dict[str, list[list[dict[str, Any]]]] = {}
    for group in groups:
        record = group[0]
        route_key = encounter_route_key(record)
        locations = (
            relationships.encounter_locations.get(route_key, ())
            if relationships
            else ()
        )
        locations_by_route[route_key] = locations
        same_name_groups.setdefault(
            _seasonal_display_name(record, locations), []
        ).append(group)
    for index, group in enumerate(groups):
        record = group[0]
        filename = f"{encounter_route_key(record)}.md"
        locations = locations_by_route[encounter_route_key(record)]
        record_name = _seasonal_display_name(record, locations)
        previous = groups[index - 1][0] if index else None
        following = groups[index + 1][0] if index + 1 < len(groups) else None
        if _seasonal_page_selected(group, only_pages):
            write_text(
                output_root / filename,
                _render_seasonal_area(
                    group,
                    comparison,
                    comparison.get("baseline") if comparison else None,
                    references,
                    locations,
                    previous,
                    following,
                    same_name_groups[record_name],
                    locations_by_route,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "encounter_variant",
                    record["area_id"],
                    record_name,
                    encounter_route_key(record),
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _seasonal_catalog_record(
                group,
                filename.removesuffix(".md") + "/",
                encounter_record_comparison(comparison, record),
                locations,
            )
        )
    page_count += _render_conditional_encounter_records(
        conditional_records,
        comparison,
        references,
        only_pages,
        output_root,
        fallback_links,
        catalog_records,
    )
    write_catalog(output_root, "encounters", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Wild encounters",
            "Exact encounter tables decoded from the ROM's own wild-encounter archive.",
            "encounters",
            fallback_links,
        ),
    )
    return page_count


def _seasonal_page_selected(
    records: list[dict[str, Any]],
    only_pages: frozenset[str] | None,
) -> bool:
    record = records[0]
    return (
        only_pages is None
        or str(encounter_route_key(record)) in only_pages
        or any(f"area-{value['area_id']:03}" in only_pages for value in records)
    )


def _seasonal_record_sort_key(record: dict[str, Any]) -> tuple[int, int]:
    season = record.get("season")
    return (
        _SEASONS.index(season) if season in _SEASONS else len(_SEASONS),
        record["area_id"],
    )


def _seasonal_catalog_record(
    records: list[dict[str, Any]],
    filename: str,
    change: dict[str, Any] | None = None,
    locations: tuple[EncounterLocationReference, ...] = (),
) -> dict[str, Any]:
    record = records[0]
    accumulator = _MethodAccumulator()
    source_records = [
        value
        for seasonal_record in records
        for _, value in version_variant_records(seasonal_record)
    ]
    for source_record in source_records:
        for key, label in _SEASONAL_METHOD_LABELS.items():
            accumulator.add(label, heading_anchor(label), source_record[key])
    location_names = list(
        dict.fromkeys(
            [location.location_name for location in locations]
            + [
                name
                for source_record in source_records
                for name in source_record.get("location_names", [])
            ]
        )
    )
    record_name = _seasonal_display_name(record, locations)
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": record_name,
            "url": filename,
            "locations": location_names,
            "methods": list(dict.fromkeys(accumulator.methods)),
            "method_anchors": accumulator.method_anchors,
            "pokemon": list(dict.fromkeys(accumulator.species)),
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(accumulator.pokemon_refs)
            ],
            "method_pokemon": accumulator.method_pokemon_deduped(),
            "min_level": min(accumulator.levels) if accumulator.levels else None,
            "max_level": max(accumulator.levels) if accumulator.levels else None,
            "referenced": True,
            "search_text": " ".join(
                (record_name, route_id, *location_names, *accumulator.species)
            ).lower(),
        },
        change,
    )


def _render_seasonal_area(
    records: list[dict[str, Any]],
    comparison: dict[str, Any] | None,
    baseline_name: str | None,
    references: ReferenceIndex | None,
    locations: tuple[EncounterLocationReference, ...],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    same_name_groups: list[list[dict[str, Any]]],
    locations_by_route: Mapping[int | str, tuple[EncounterLocationReference, ...]],
) -> str:
    record = records[0]
    source_file = f"encounters/{encounter_route_key(record)}.md"
    lines = [
        f"# {_seasonal_display_name(record, locations)}",
        "",
        *_seasonal_area_summary(records, locations),
    ]
    _append_seasonal_locations(lines, locations, source_file)
    for key, label in _SEASONAL_METHOD_LABELS.items():
        if not any(
            version_record[key]["rate"]
            for seasonal_record in records
            for _, version_record in version_variant_records(seasonal_record)
        ):
            continue
        lines.extend([f"## {label}", ""])
        method_contents: list[tuple[str | None, str | None, list[str]]] = []
        for seasonal_record in records:
            for version, version_record in version_variant_records(seasonal_record):
                content: list[str] = []
                method = version_record[key]
                if method["rate"]:
                    _append_seasonal_method(
                        content,
                        label,
                        method,
                        source_file,
                        references,
                        heading_level=None,
                    )
                else:
                    content.extend(["No encounters.", ""])
                method_contents.append(
                    (version, seasonal_record.get("season"), content)
                )
        lines.extend(_season_version_tabs(method_contents))
    _append_same_name_encounters(
        lines,
        record,
        same_name_groups,
        locations_by_route,
        source_file,
    )
    comparisons = [
        (
            seasonal_record,
            encounter_record_comparison(comparison, seasonal_record),
        )
        for seasonal_record in records
    ]
    if any(change is not None for _, change in comparisons):
        change_contents: list[tuple[str | None, str | None, list[str]]] = []
        for seasonal_record, change in comparisons:
            version_comparisons = (change or {}).get("version_comparisons")
            if version_comparisons:
                for version, version_change in version_comparisons.items():
                    change_contents.append(
                        (
                            version,
                            seasonal_record.get("season"),
                            comparison_section(
                                version_change,
                                version_change.get("baseline") or baseline_name,
                                source_file,
                                references,
                                heading_level=None,
                                details=False,
                            ),
                        )
                    )
                continue
            change_contents.append(
                (
                    None,
                    seasonal_record.get("season"),
                    comparison_section(
                        change,
                        baseline_name,
                        source_file,
                        references,
                        heading_level=None,
                        details=False,
                    ),
                )
            )
        lines.extend(
            comparison_notes_section(
                _season_version_tabs(change_contents),
                [change for _, change in comparisons if change is not None],
            )
        )
    lines.extend(
        provenance_section(
            [
                *(
                    rom_record_source(
                        value["provenance"]["archive"],
                        value["provenance"]["member"],
                    )
                    for value in records
                ),
                "Chance percentages are not stored in the ROM's encounter tables — "
                "only each slot's species and level(s) are ROM data — they are "
                "fixed, publicly documented Generation III+ engine weights applied "
                "by slot position.",
                *(
                    [
                        "Location names and links come from the ROM's own map "
                        "header table, cross-referenced through the shared wild-"
                        "encounter table index."
                    ]
                    if locations
                    else [
                        "No location header was resolved for this encounter table; "
                        "no location link is guessed."
                    ]
                ),
            ]
        )
    )
    _append_seasonal_record_navigation(
        lines, record, previous, following, locations_by_route
    )
    return "\n".join(lines)


def _season_version_tabs(
    contents: list[tuple[str | None, str | None, list[str]]],
) -> list[str]:
    """Nest version tabs inside seasonal tabs without redundant dimensions."""
    if not contents:
        return []

    by_season: dict[str | None, list[tuple[str, list[str]]]] = {}
    for version, season, content in contents:
        by_season.setdefault(season, []).append(
            (display_name(version or "all"), content)
        )

    season_contents = [
        (display_name(season or "all"), tab_dimension(version_contents))
        for season, version_contents in by_season.items()
    ]
    if set(by_season) == {None}:
        return season_contents[0][1]
    return tab_dimension(season_contents)


def _seasonal_area_summary(
    records: list[dict[str, Any]],
    locations: tuple[EncounterLocationReference, ...],
) -> list[str]:
    record = records[0]
    methods = [
        label
        for key, label in _SEASONAL_METHOD_LABELS.items()
        if any(value[key]["rate"] for value in records)
    ]
    facts = [
        f"<div><dt>Area ID</dt><dd>{record['area_id']}</dd></div>",
        f"<div><dt>Map index</dt><dd>{record['map_index']}</dd></div>",
        "<div><dt>Methods</dt><dd>"
        + (
            ", ".join(
                summary_section_link(label, heading_anchor(label)) for label in methods
            )
            if methods
            else "None"
        )
        + "</dd></div>",
    ]
    seasons = [value["season"] for value in records if value.get("season")]
    if seasons:
        facts.insert(
            2,
            "<div><dt>Seasons</dt><dd>"
            + ", ".join(display_name(value) for value in seasons)
            + "</dd></div>",
        )
    if locations:
        facts.append(
            "<div><dt>Map headers</dt><dd>"
            f"{summary_section_link(len(locations), 'map-headers')}</dd></div>"
        )
    return summary_section("rw-encounter-summary", facts)


def _append_seasonal_locations(
    lines: list[str],
    locations: tuple[EncounterLocationReference, ...],
    source_file: str,
) -> None:
    if not locations:
        return
    lines.extend(
        [
            "## Map headers",
            "",
            "| Location | Section | Map ID | Version |",
            "| -------- | ------- | ------ | ------- |",
        ]
    )
    for location in locations:
        link = ROUTES.markdown_link(
            entity_reference(
                "location",
                location.header_id,
                location.location_name,
                location.header_id,
            ),
            source_file,
        )
        versions = (
            " / ".join(display_name(version) for version in location.versions) or "—"
        )
        lines.append(
            f"| {link} | {location.section_name or '—'} | "
            f"`header-{location.header_id:03}` | {versions} |"
        )
    lines.append("")


def _append_seasonal_method(
    lines: list[str],
    heading: str,
    method: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    heading_level: int | None = 2,
) -> None:
    if not method["rate"]:
        return
    slots = aggregate_slots(method["slots"], "minimum_level", "maximum_level")
    if heading_level is not None:
        lines.extend([f"{'#' * heading_level} {heading}", ""])
    lines.extend([f"Encounter rate: {method['rate']}", ""])
    lines.extend(
        markdown_table_from_cells(
            _ENCOUNTER_SLOT_COLUMNS,
            (
                (
                    sprite_with_link(
                        table_sprite_cell((slot["pokemon"] or {}).get("sprite")),
                        _pokemon_link(slot["pokemon"], source_file),
                    ),
                    _slot_type_cell(slot["pokemon"], references),
                    level_range(slot["minimum_level"], slot["maximum_level"]),
                    f"{slot['chance']}%",
                )
                for slot in slots
            ),
        )
    )


def _seasonal_display_name(
    record: Mapping[str, Any],
    locations: tuple[EncounterLocationReference, ...],
) -> str:
    names = list(dict.fromkeys(location.location_name for location in locations))
    return " / ".join(names) or record["name"]


def _append_seasonal_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    locations_by_route: Mapping[int | str, tuple[EncounterLocationReference, ...]],
) -> None:
    lines.extend(
        record_navigation_for(
            "encounter_variant",
            f"encounters/{encounter_route_key(record)}/",
            previous,
            following,
            aria_label="Wild encounter navigation",
            identity=encounter_route_key,
            route_key=encounter_route_key,
            label=lambda value: _seasonal_display_name(
                value,
                locations_by_route.get(encounter_route_key(value), ()),
            ),
        )
    )


def _append_same_name_encounters(
    lines: list[str],
    record: dict[str, Any],
    same_name_groups: list[list[dict[str, Any]]],
    locations_by_route: Mapping[int | str, tuple[EncounterLocationReference, ...]],
    source_file: str,
) -> None:
    related = [
        group[0]
        for group in same_name_groups
        if encounter_route_key(group[0]) != encounter_route_key(record)
    ]
    if not related:
        return
    lines.extend(
        [
            "## Same-name encounter areas",
            "",
            (
                "These encounter tables resolve to the same map-header display "
                "name. A shared name alone does not establish that two maps are "
                "the same area."
            ),
            "",
            "| Encounter area | ID |",
            "| -------------- | -- |",
        ]
    )
    for candidate in related:
        route_key = encounter_route_key(candidate)
        label = _seasonal_display_name(candidate, locations_by_route.get(route_key, ()))
        link = ROUTES.markdown_link(
            entity_reference(
                "encounter_variant", candidate["area_id"], label, route_key
            ),
            source_file,
        )
        lines.append(f"| {link} | `{route_key}` |")
    lines.append("")
