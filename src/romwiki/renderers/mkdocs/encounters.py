from __future__ import annotations

from pathlib import Path
from typing import Any
from collections import Counter

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    write_catalog,
    write_text as _write_text,
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
) -> int:
    records = [record for record in dataset["records"] if record["active"]]
    output_root.mkdir(parents=True, exist_ok=True)
    fallback_links = []
    catalog_records = []
    linked = [record for record in records if record.get("locations")]
    unlinked = [record for record in records if not record.get("locations")]
    name_counts = Counter(record["name"] for record in linked)
    for record in sorted(linked, key=lambda item: (item["name"], item["area_id"])):
        change = record_comparison(comparison, record["area_id"])
        filename = f"area-{record['area_id']:03}.md"
        _write_text(
            output_root / filename,
            _render_area(
                record,
                change,
                comparison.get("baseline") if comparison else None,
                references,
            ),
        )
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
        for record in unlinked:
            change = record_comparison(comparison, record["area_id"])
            filename = f"area-{record['area_id']:03}.md"
            _write_text(
                output_root / filename,
                _render_area(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                ),
            )
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
    return len(records)


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
) -> str:
    source_file = f"encounters/area-{record['area_id']:03}.md"
    lines = [
        f"# {record['name']}",
        "",
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
                f"`{record['provenance']['member']}`."
            ),
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def _append_locations(
    lines: list[str], locations: list[dict[str, Any]], source_file: str
) -> None:
    if not locations:
        return
    lines.extend(["## Map headers", "", "| Header | Location | Internal map |", "| -----: | -------- | ------------ |"])
    for location in locations:
        reference = entity_reference(
            "location",
            location["header_id"],
            str(location["header_id"]),
            location.get("header_id"),
        )
        lines.append(
            f"| {ROUTES.markdown_link(reference, source_file)} "
            f"| {location['name']} | "
            f"`{location['internal_name']}` |"
        )
    lines.append("")


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
            "| Slot | Pokémon | Level |",
            "| ---: | ------- | ----: |",
        ]
    )
    for index, slot in enumerate(method["slots"]):
        lines.append(
            f"| {index + 1} | {_pokemon_link(slot['pokemon'], source_file)} | "
            f"{slot['level']} |"
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
            "| Slot | Pokémon | Levels |",
            "| ---: | ------- | -----: |",
        ]
    )
    for index, slot in enumerate(method["slots"]):
        levels = _level_range(slot["minimum_level"], slot["maximum_level"])
        lines.append(
            f"| {index + 1} | {_pokemon_link(slot['pokemon'], source_file)} | {levels} |"
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


