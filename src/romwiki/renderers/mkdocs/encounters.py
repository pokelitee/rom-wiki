from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from romwiki.engines.registry import GEN5_ENGINES
from romwiki.pipeline.encounter_identity import encounter_route_key
from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.components import (
    display_name,
    pokemon_table,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_type_cell,
    rom_record_source,
    sprite_with_link,
    summary_section,
    summary_section_link,
    table_sprite_cell,
    version_variant_records,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    unique_references,
)

# Generation V's own display labels for its seven encounter methods
# (Gen5Constants.encounterTypeNames, Ajarmar/universal-pokemon-randomizer-zx).
_GEN5_METHOD_LABELS = {
    "grass_cave": "Grass/Cave",
    "doubles_grass": "Doubles Grass",
    "shaking_spots": "Shaking Spots",
    "surfing": "Surfing",
    "surfing_spots": "Surfing Spots",
    "fishing": "Fishing",
    "fishing_spots": "Fishing Spots",
}


def render_encounter_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    if dataset.get("engine") in GEN5_ENGINES:
        return _render_gen5_encounter_pages(
            dataset,
            output_root,
            comparison,
            references,
            only_pages=only_pages,
        )
    records = [record for record in dataset["records"] if record["active"]]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"area-{record['area_id']:03}.md"
                for record in records
                if only_pages is None or f"area-{record['area_id']:03}" in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    linked = [record for record in records if record.get("locations")]
    unlinked = [record for record in records if not record.get("locations")]
    name_counts = Counter(record["name"] for record in linked)
    sorted_linked = sorted(linked, key=lambda item: (item["name"], item["area_id"]))
    for index, record in enumerate(sorted_linked):
        change = record_comparison(comparison, record["area_id"])
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
    if unlinked:
        for index, record in enumerate(unlinked):
            change = record_comparison(comparison, record["area_id"])
            filename = f"area-{record['area_id']:03}.md"
            previous = unlinked[index - 1] if index else None
            following = unlinked[index + 1] if index + 1 < len(unlinked) else None
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
            fallback_links.append(
                "- "
                + ROUTES.markdown_link(
                    entity_reference(
                        "encounter",
                        record["area_id"],
                        record["name"],
                        record["area_id"],
                    ),
                    "encounters/index.md",
                )
            )
            catalog_records.append(
                _catalog_record(
                    record, filename.removesuffix(".md") + "/", False, change
                )
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


def _catalog_record(
    record: dict[str, Any],
    filename: str,
    referenced: bool,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methods = []
    levels = []
    species = []
    pokemon_refs = []
    method_pokemon = {}
    for label, key in (
        ("walking", "walking"),
        ("surf", "surf"),
        ("old rod", "old_rod"),
        ("good rod", "good_rod"),
        ("super rod", "super_rod"),
    ):
        method = record[key]
        if not method["rate"]:
            continue
        methods.append(label)
        method_species = []
        for slot in method["slots"]:
            pokemon = slot.get("pokemon")
            if pokemon:
                species.append(pokemon["name"])
                method_species.append(pokemon["name"])
                pokemon_refs.append(_pokemon_reference(pokemon))
            if "level" in slot:
                levels.append(slot["level"])
            else:
                levels.extend((slot["minimum_level"], slot["maximum_level"]))
        method_pokemon[label] = list(dict.fromkeys(method_species))
    special_pokemon = _special_pokemon(record["special"])
    special_species = [pokemon["name"] for pokemon in special_pokemon]
    pokemon_refs.extend(_pokemon_reference(pokemon) for pokemon in special_pokemon)
    species.extend(special_species)
    levels.extend(
        entry["level"]
        for group in (
            record["special"]["swarm"],
            record["special"]["day"],
            record["special"]["night"],
            *record["special"]["dual_slot"].values(),
        )
        for entry in group
        if entry["pokemon"]
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
            "methods": methods,
            "pokemon": list(dict.fromkeys(species)),
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(pokemon_refs)
            ],
            "method_pokemon": method_pokemon,
            "min_level": min(levels) if levels else None,
            "max_level": max(levels) if levels else None,
            "referenced": referenced,
            "search_text": " ".join(
                (record["name"], route_id, *location_names, *species)
            ).lower(),
        },
        change,
    )


def _special_pokemon(special: dict[str, Any]) -> list[dict[str, Any]]:
    slotted_groups = (
        special["swarm"],
        special["day"],
        special["night"],
        *(entries for entries in special["dual_slot"].values()),
    )
    pokemon = [
        entry["pokemon"]
        for group in slotted_groups
        for entry in group
        if entry["pokemon"]
    ]
    pokemon.extend(value for value in special["radar"] if value is not None)
    return _unique_pokemon(pokemon)


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
    _append_walking(lines, record["walking"], source_file, references)
    for heading, key in (
        ("Surf", "surf"),
        ("Old Rod", "old_rod"),
        ("Good Rod", "good_rod"),
        ("Super Rod", "super_rod"),
    ):
        _append_water(lines, heading, record[key], source_file, references)
    _append_special(lines, record["special"], source_file, references)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
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
        label
        for label, key in (
            ("Walking", "walking"),
            ("Surf", "surf"),
            ("Old Rod", "old_rod"),
            ("Good Rod", "good_rod"),
            ("Super Rod", "super_rod"),
        )
        if record[key]["rate"]
    ]
    locations = record.get("locations", [])
    facts = [
        f"<div><dt>Area ID</dt><dd>{record['area_id']}</dd></div>",
        (
            "<div><dt>Methods</dt><dd>"
            + (
                ", ".join(
                    summary_section_link(label, label.lower().replace(" ", "-"))
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
            "| Location | Header | Location name ID | Internal map |",
            "| -------- | -----: | ----------------: | ------------ |",
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
            f"| {location['header_id']} | "
            f"{location['location_name_id']} | "
            f"`{location['internal_name']}` |"
        )
    lines.append("")


def _merge_slots(
    slots: list[dict[str, Any]], level_keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Combine slots for the same species and level(s) into one row.

    The ROM assigns a species to multiple fixed-probability slots to give it
    a higher overall chance rather than storing a single percentage per
    species, so the same Pokémon at the same level(s) commonly repeats across
    several slots (see the Gen III/IV slot-chance tables). Slots that share a
    species but differ in level are kept separate, since that's a real
    distinction the table would otherwise hide.
    """
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for slot in slots:
        key = (slot["species_id"], *(slot[level_key] for level_key in level_keys))
        if key not in merged:
            merged[key] = dict(slot)
            order.append(key)
        else:
            merged[key]["chance"] += slot["chance"]
    return [merged[key] for key in order]


def _append_walking(
    lines: list[str],
    method: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not method["rate"]:
        return
    slots = _merge_slots(method["slots"], ("level",))
    lines.extend(["## Walking", "", f"Encounter rate: {method['rate']}", ""])
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Level | Chance |",
                "| ------- | ---- | ----: | -----: |",
            ],
            [
                (
                    f"| {sprite_with_link(table_sprite_cell((slot['pokemon'] or {}).get('sprite')), _pokemon_link(slot['pokemon'], source_file))} | "
                    f"{_slot_type_cell(slot['pokemon'], references)} | "
                    f"{slot['level']} | {slot['chance']}% |"
                )
                for slot in slots
            ],
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
    slots = _merge_slots(method["slots"], ("minimum_level", "maximum_level"))
    lines.extend([f"## {heading}", "", f"Encounter rate: {method['rate']}", ""])
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Levels | Chance |",
                "| ------- | ---- | -----: | -----: |",
            ],
            [
                (
                    f"| {sprite_with_link(table_sprite_cell((slot['pokemon'] or {}).get('sprite')), _pokemon_link(slot['pokemon'], source_file))} | "
                    f"{_slot_type_cell(slot['pokemon'], references)} | "
                    f"{_level_range(slot['minimum_level'], slot['maximum_level'])} | "
                    f"{slot['chance']}% |"
                )
                for slot in slots
            ],
        )
    )


def _append_special(
    lines: list[str],
    special: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    slotted_groups = [
        ("Swarm", special["swarm"]),
        ("Day replacements", special["day"]),
        ("Night replacements", special["night"]),
    ]
    slotted_groups.extend(
        (f"Dual-slot: {game.replace('-', ' ').title()}", entries)
        for game, entries in special["dual_slot"].items()
    )
    populated_slotted = [
        (label, [entry for entry in entries if entry["pokemon"]])
        for label, entries in slotted_groups
    ]
    populated_slotted = [
        (label, entries) for label, entries in populated_slotted if entries
    ]
    radar = _unique_pokemon(value for value in special["radar"] if value)
    unown_forms = special["unown_forms"]
    if not populated_slotted and not radar and not unown_forms:
        return
    lines.extend(["## Special encounters", ""])
    for label, entries in populated_slotted:
        lines.extend([f"**{label}:**", ""])
        lines.extend(
            pokemon_table(
                [
                    "| Pokémon | Type | Level | Chance |",
                    "| ------- | ---- | ----: | -----: |",
                ],
                [
                    (
                        f"| {sprite_with_link(table_sprite_cell(entry['pokemon'].get('sprite')), _pokemon_link(entry['pokemon'], source_file))} | "
                        f"{_slot_type_cell(entry['pokemon'], references)} | "
                        f"{entry['level']} | {entry['chance']}% |"
                    )
                    for entry in entries
                ],
            )
        )
    if radar:
        lines.extend(
            [
                "**Poké Radar:**",
                "",
                "Only appears for one specific Poké Radar shake outcome; most "
                "radar encounters instead continue the current chain's species "
                "rather than drawing from this table, so no fixed level or "
                "chance applies here.",
                "",
            ]
        )
        lines.extend(
            pokemon_table(
                ["| Pokémon | Type |", "| ------- | ---- |"],
                [
                    (
                        f"| {sprite_with_link(table_sprite_cell((value or {}).get('sprite')), _pokemon_link(value, source_file))} | "
                        f"{_slot_type_cell(value, references)} |"
                    )
                    for value in radar
                ],
            )
        )
    if unown_forms:
        lines.extend(
            [
                "**Unown forms:**",
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


def _slot_type_cell(
    pokemon: dict[str, Any] | None, references: ReferenceIndex | None
) -> str:
    return reference_type_cell("pokemon", (pokemon or {}).get("id"), references)


def _pokemon_link(pokemon: dict[str, Any] | None, source_file: str) -> str:
    if pokemon is None:
        return "None"
    return ROUTES.markdown_link(_pokemon_reference(pokemon), source_file)


def _level_range(minimum: int, maximum: int) -> str:
    return str(minimum) if minimum == maximum else f"{minimum}–{maximum}"


def _render_gen5_encounter_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None,
    references: ReferenceIndex | None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = sorted(
        (record for record in dataset["records"] if record["active"]),
        key=lambda record: record["area_id"],
    )
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{encounter_route_key(record)}.md"
                for record in records
                if _gen5_page_selected(record, only_pages)
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    for index, record in enumerate(records):
        change = record_comparison(comparison, record["area_id"])
        filename = f"{encounter_route_key(record)}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        if _gen5_page_selected(record, only_pages):
            write_text(
                output_root / filename,
                _render_gen5_area(
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
                    "encounter_variant",
                    record["area_id"],
                    record["name"],
                    encounter_route_key(record),
                ),
                "encounters/index.md",
            )
        )
        catalog_records.append(
            _gen5_catalog_record(record, filename.removesuffix(".md") + "/", change)
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


def _gen5_page_selected(
    record: dict[str, Any],
    only_pages: frozenset[str] | None,
) -> bool:
    return (
        only_pages is None
        or str(encounter_route_key(record)) in only_pages
        or f"area-{record['area_id']:03}" in only_pages
    )


def _gen5_catalog_record(
    record: dict[str, Any],
    filename: str,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methods = []
    levels = []
    species = []
    pokemon_refs = []
    method_pokemon = {}
    variant_records = version_variant_records(record)
    source_records = [value for _, value in variant_records]
    for source_record in source_records:
        for key, label in _GEN5_METHOD_LABELS.items():
            method = source_record[key]
            if not method["rate"]:
                continue
            methods.append(label)
            method_species = method_pokemon.setdefault(label, [])
            for slot in method["slots"]:
                pokemon = slot.get("pokemon")
                if pokemon:
                    species.append(pokemon["name"])
                    method_species.append(pokemon["name"])
                    pokemon_refs.append(_pokemon_reference(pokemon))
                levels.extend((slot["minimum_level"], slot["maximum_level"]))
    location_names = list(
        dict.fromkeys(
            name
            for source_record in source_records
            for name in source_record.get("location_names", [])
        )
    )
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["area_id"],
            "route_id": route_id,
            "label": record["name"],
            "url": filename,
            "locations": location_names,
            "methods": list(dict.fromkeys(methods)),
            "pokemon": list(dict.fromkeys(species)),
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "encounters/")
                for reference in unique_references(pokemon_refs)
            ],
            "method_pokemon": {
                label: list(dict.fromkeys(values))
                for label, values in method_pokemon.items()
            },
            "min_level": min(levels) if levels else None,
            "max_level": max(levels) if levels else None,
            "referenced": True,
            "search_text": " ".join(
                (record["name"], route_id, *location_names, *species)
            ).lower(),
        },
        change,
    )


def _render_gen5_area(
    record: dict[str, Any],
    change: dict[str, Any] | None,
    baseline_name: str | None,
    references: ReferenceIndex | None,
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> str:
    source_file = f"encounters/{encounter_route_key(record)}.md"
    lines = [
        f"# {record['name']}",
        "",
        *_gen5_area_summary(record),
    ]
    variant_records = version_variant_records(record)
    if variant_records[0][0] is not None:
        lines.extend(
            [
                '!!! info "Version differences"',
                "    Encounter tables on this page differ between the two versions.",
                "",
            ]
        )
        for version, version_record in variant_records:
            assert version is not None
            lines.extend([f"## {display_name(version)}", ""])
            for key, label in _GEN5_METHOD_LABELS.items():
                _append_gen5_method(
                    lines,
                    label,
                    version_record[key],
                    source_file,
                    references,
                    heading_level=3,
                )
    else:
        for key, label in _GEN5_METHOD_LABELS.items():
            _append_gen5_method(lines, label, record[key], source_file, references)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "Chance percentages are not stored in the ROM's encounter tables — "
                "only each slot's species and level(s) are ROM data — they are "
                "fixed, publicly documented Generation III+ engine weights applied "
                "by slot position.",
                "Location names come from the ROM's own map header table and are "
                "cross-referenced to location pages by the shared wild-encounter "
                "table index.",
            ]
        )
    )
    _append_gen5_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _gen5_area_summary(record: dict[str, Any]) -> list[str]:
    methods = [
        label for key, label in _GEN5_METHOD_LABELS.items() if record[key]["rate"]
    ]
    facts = [
        f"<div><dt>Area ID</dt><dd>{record['area_id']}</dd></div>",
        f"<div><dt>Map index</dt><dd>{record['map_index']}</dd></div>",
        "<div><dt>Methods</dt><dd>"
        + (", ".join(methods) if methods else "None")
        + "</dd></div>",
    ]
    if record.get("season"):
        facts.insert(
            2, f"<div><dt>Season</dt><dd>{record['season'].title()}</dd></div>"
        )
    return summary_section("rw-encounter-summary", facts)


def _append_gen5_method(
    lines: list[str],
    heading: str,
    method: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    *,
    heading_level: int = 2,
) -> None:
    if not method["rate"]:
        return
    slots = _merge_slots(method["slots"], ("minimum_level", "maximum_level"))
    lines.extend(
        [
            f"{'#' * heading_level} {heading}",
            "",
            f"Encounter rate: {method['rate']}",
            "",
        ]
    )
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Levels | Chance |",
                "| ------- | ---- | -----: | -----: |",
            ],
            [
                (
                    f"| {sprite_with_link(table_sprite_cell((slot['pokemon'] or {}).get('sprite')), _pokemon_link(slot['pokemon'], source_file))} | "
                    f"{_slot_type_cell(slot['pokemon'], references)} | "
                    f"{_level_range(slot['minimum_level'], slot['maximum_level'])} | "
                    f"{slot['chance']}% |"
                )
                for slot in slots
            ],
        )
    )


def _append_gen5_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
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
            label=lambda value: value["name"],
        )
    )
