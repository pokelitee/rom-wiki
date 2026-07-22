from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from collections import Counter

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text as _write_text,
)
from romwiki.renderers.mkdocs.components import (
    record_nav_link,
    record_navigation,
    table_sprite_cell,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    unique_references,
)


def render_encounter_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
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
        following = (
            sorted_linked[index + 1] if index + 1 < len(sorted_linked) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            _write_text(
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
                dict.fromkeys(location["internal_name"] for location in record["locations"])
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
            _catalog_record(
                record, filename.removesuffix(".md") + "/", True, change
            )
        )
    if unlinked:
        for index, record in enumerate(unlinked):
            change = record_comparison(comparison, record["area_id"])
            filename = f"area-{record['area_id']:03}.md"
            previous = unlinked[index - 1] if index else None
            following = unlinked[index + 1] if index + 1 < len(unlinked) else None
            if only_pages is None or filename.removesuffix(".md") in only_pages:
                _write_text(
                    output_root / filename,
                    _render_area(
                        record,
                        change,
                        comparison.get("baseline") if comparison else None,
                        None,
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
    _write_text(
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
    if special_species and "walking" in method_pokemon:
        method_pokemon["walking"] = list(
            dict.fromkeys((*method_pokemon["walking"], *special_species))
        )
    location_names = [location["name"] for location in record.get("locations", [])]
    return add_change_status({
        "id": record["area_id"],
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
        "search_text": " ".join((record["name"], *location_names, *species)).lower(),
    }, change)


def _special_pokemon(special: dict[str, Any]) -> list[dict[str, Any]]:
    pokemon = []
    seen = set()
    groups = (
        special["swarm"],
        special["day"],
        special["night"],
        special["radar"],
        *(values for values in special["dual_slot"].values()),
    )
    for group in groups:
        for value in group:
            if value is None:
                continue
            identity = (value.get("id"), value.get("slug"), value["name"])
            if identity in seen:
                continue
            seen.add(identity)
            pokemon.append(value)
    return pokemon


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
        *comparison_section(change, baseline_name, source_file, references),
    ]
    _append_locations(lines, record.get("locations", []), source_file)
    _append_walking(lines, record["walking"], source_file)
    for heading, key in (
        ("Surf", "surf"),
        ("Old Rod", "old_rod"),
        ("Good Rod", "good_rod"),
        ("Super Rod", "super_rod"),
    ):
        _append_water(lines, heading, record[key], source_file)
    _append_special(lines, record["special"], source_file)
    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Data provenance</summary>",
            "",
            (
                "Source: exact ROM record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`. Chance percentages are not "
                "stored in the ROM's encounter tables — only each slot's species "
                "and level(s) are ROM data — they are fixed, publicly documented "
                "Generation III/IV engine weights applied by slot position."
            ),
            "",
            "</details>",
            "",
        ]
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
        ("Area ID", str(record["area_id"])),
        ("Methods", ", ".join(methods) if methods else "None"),
    ]
    if locations:
        facts.append(("Map headers", str(len(locations))))
    return [
        '<section class="rw-encounter-summary">',
        '<dl class="rw-summary__facts">',
        *(
            f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
            for label, value in facts
        ),
        "</dl>",
        "</section>",
        "",
    ]


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"encounters/area-{record['area_id']:03}/"
    previous_link = None
    if previous is not None:
        label = f"← {previous['name']}"
        href = ROUTES.published_href(
            entity_reference("encounter", previous["area_id"], label, previous["area_id"]),
            source_url,
        )
        previous_link = record_nav_link(href, label, "prev")
    following_link = None
    if following is not None:
        label = f"{following['name']} →"
        href = ROUTES.published_href(
            entity_reference("encounter", following["area_id"], label, following["area_id"]),
            source_url,
        )
        following_link = record_nav_link(href, label, "next")
    lines.extend(
        record_navigation(previous_link, following_link, "Wild encounter navigation")
    )


def _append_locations(
    lines: list[str], locations: list[dict[str, Any]], source_file: str
) -> None:
    if not locations:
        return
    lines.extend(["## Map headers", "", "| Location | Header | Internal map |", "| -------- | -----: | ------------ |"])
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
    lines: list[str], method: dict[str, Any], source_file: str
) -> None:
    if not method["rate"]:
        return
    lines.extend(
        [
            "## Walking",
            "",
            f"Encounter rate: {method['rate']}",
            "",
            "| <span class=\"rw-visually-hidden\">Sprite</span> | Pokémon | Level | Chance |",
            "| ---- | ------- | ----: | -----: |",
        ]
    )
    for slot in _merge_slots(method["slots"], ("level",)):
        lines.append(
            f"| {table_sprite_cell((slot['pokemon'] or {}).get('sprite'))} | "
            f"{_pokemon_link(slot['pokemon'], source_file)} | "
            f"{slot['level']} | {slot['chance']}% |"
        )
    lines.append("")


def _append_water(
    lines: list[str], heading: str, method: dict[str, Any], source_file: str
) -> None:
    if not method["rate"]:
        return
    lines.extend(
        [
            f"## {heading}",
            "",
            f"Encounter rate: {method['rate']}",
            "",
            "| <span class=\"rw-visually-hidden\">Sprite</span> | Pokémon | Levels | Chance |",
            "| ---- | ------- | -----: | -----: |",
        ]
    )
    for slot in _merge_slots(method["slots"], ("minimum_level", "maximum_level")):
        levels = _level_range(slot["minimum_level"], slot["maximum_level"])
        lines.append(
            f"| {table_sprite_cell((slot['pokemon'] or {}).get('sprite'))} | "
            f"{_pokemon_link(slot['pokemon'], source_file)} | {levels} | "
            f"{slot['chance']}% |"
        )
    lines.append("")


def _append_special(
    lines: list[str], special: dict[str, Any], source_file: str
) -> None:
    groups = [
        ("Swarm", special["swarm"]),
        ("Day replacements", special["day"]),
        ("Night replacements", special["night"]),
        ("Poké Radar", special["radar"]),
    ]
    groups.extend(
        (f"Dual-slot: {game.replace('-', ' ').title()}", pokemon)
        for game, pokemon in special["dual_slot"].items()
    )
    populated = [(label, values) for label, values in groups if any(values)]
    if not populated:
        return
    lines.extend(["## Special encounters", ""])
    for label, values in populated:
        names = ", ".join(
            _pokemon_link(value, source_file) for value in values if value
        )
        lines.append(f"- {label}: {names}")
    lines.append("")


def _pokemon_link(pokemon: dict[str, Any] | None, source_file: str) -> str:
    if pokemon is None:
        return "None"
    return ROUTES.markdown_link(_pokemon_reference(pokemon), source_file)


def _level_range(minimum: int, maximum: int) -> str:
    return str(minimum) if minimum == maximum else f"{minimum}–{maximum}"


