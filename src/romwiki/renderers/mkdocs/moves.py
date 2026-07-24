from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

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
    class_badge,
    display_name,
    empty_state,
    fact_grid,
    machine_link,
    name_table_source,
    pokemon_table,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_description,
    reference_source_link,
    reference_sprite_cell,
    reference_type_cell,
    rom_record_source,
    sprite_with_link,
    summary_section,
    tutor_requirement,
    type_badges,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    escape_markdown,
    pokemon_record_link,
)


def render_move_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{record['slug']}.md"
                for record in public_records
                if only_pages is None or record["slug"] in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    name_source = dataset.get("name_sources", {}).get("move_names")
    for index, record in enumerate(public_records):
        change = record_comparison(comparison, record["move_id"])
        filename = f"{record['slug']}.md"
        previous = public_records[index - 1] if index else None
        following = public_records[index + 1] if index + 1 < len(public_records) else None
        if only_pages is None or record["slug"] in only_pages:
            write_text(
                output_root / filename,
                _render_record(
                    record,
                    previous,
                    following,
                    name_source,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "move",
                    record["move_id"],
                    record["name"],
                    record["slug"],
                ),
                "moves/index.md",
            )
        )
        machines = [machine["name"] for machine in record.get("machines", [])]
        replaced_name = (
            record["replaces"]["name"] if record.get("replaces") else None
        )
        access_methods = [
            method
            for method, available in (
                ("machine", bool(machines)),
                ("move tutor", bool(record.get("tutors"))),
                ("egg move", bool(record.get("egg_move_pokemon"))),
            )
            if available
        ]
        catalog_records.append(
            add_change_status({
                "id": record["move_id"],
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "type": record["type"]["name"],
                "damage_class": record["damage_class"]["name"],
                "power": record["power"],
                "accuracy": record["accuracy"],
                "pp": record["pp"],
                "machines": machines,
                "access_methods": access_methods,
                "search_text": " ".join(
                    (
                        record["name"],
                        *machines,
                        *access_methods,
                        *((replaced_name,) if replaced_name else ()),
                    )
                ).lower(),
            }, change)
        )
    write_catalog(output_root, "moves", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Moves",
            "Move mechanics extracted directly from the game image.",
            "moves",
            fallback_links,
        ),
    )
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    name_source: dict[str, Any] | None = None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
) -> str:
    source_file = f"moves/{record['slug']}.md"
    source_url = source_file.removesuffix(".md") + "/"
    additional_properties = []
    if record.get("machines"):
        additional_properties.append(
            (
                "Machine",
                ", ".join(
                    machine_link(machine, source_url, references, as_html=True)
                    for machine in record["machines"]
                ),
            )
        )
    if record.get("tutors"):
        additional_properties.append(
            (
                "Move tutor",
                ", ".join(
                    _tutor_location_link_html(tutor["location"], source_url)
                    for tutor in record["tutors"]
                ),
            )
        )
    if record.get("replaces") and change is None:
        additional_properties.append(("Replaces", record["replaces"]["name"]))
    if record["priority"]:
        additional_properties.append(("Priority", f"{record['priority']:+d}"))
    if record["effect_chance"]:
        additional_properties.append(("Effect chance", f"{record['effect_chance']}%"))
    lines = [
        f"# {record['name']}",
        "",
        *_move_summary(record),
        *reference_description(
            record, "No PokéDB reference data is available for this move."
        ),
        *_reference_effects_section(record),
    ]
    if additional_properties:
        lines.extend(
            [
                "## Additional battle properties",
                "",
                *fact_grid(
                    tuple(
                        (
                            label,
                            value
                            if label in ("Machine", "Move tutor")
                            else escape(value),
                        )
                        for label, value in additional_properties
                    ),
                    escape_values=False,
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Tutor compatibility",
            "",
            *(
                _tutor_compatibility(record, source_file, references)
                if record.get("tutors")
                else empty_state("No compatible move tutors.")
            ),
        ]
    )
    lines.extend(
        [
            "## Egg move learners",
            "",
            *_egg_move_learners(record, source_file, references),
        ]
    )
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Effect ID", f"`{record['effect_id']}`"),
                        ("Target ID", f"`0x{record['target_id']:04X}`"),
                        ("Flags", f"`0x{record['flags']:02X}`"),
                        ("Contest effect ID", f"`{record['contest_effect_id']}`"),
                        ("Contest type ID", f"`{record['contest_type_id']}`"),
                    )
                ),
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "Effect, target, and flag IDs are shown in their native engine "
                "representation.",
                "The move record stores only an opaque effect ID rather than a "
                "description; the Effect section above (including its "
                "supplementary battle-mechanic facts and Pokédex quote) comes from "
                "PokéDB / PokéAPI reference data and describes the base game — a "
                "hack that changes this move's effect ID may behave differently.",
                *(
                    [
                        name_table_source(
                            "Move", name_source["archive"], name_source["member"]
                        )
                    ]
                    if name_source is not None
                    else []
                ),
                *reference_source_link(record),
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _move_summary(record: dict[str, Any]) -> list[str]:
    return summary_section(
        "rw-move-summary",
        [
            f"<div><dt>Move ID</dt><dd>{record['move_id']}</dd></div>",
            f"<div><dt>Type</dt><dd>{type_badges([record['type']])}</dd></div>",
            f"<div><dt>Class</dt><dd>{class_badge(record['damage_class'])}</dd></div>",
            f"<div><dt>Power</dt><dd>{_optional_value(record['power'])}</dd></div>",
            f"<div><dt>Accuracy</dt><dd>{_accuracy(record['accuracy'])}</dd></div>",
            f"<div><dt>PP</dt><dd>{record['pp']}</dd></div>",
        ],
    )


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "move",
            f"moves/{record['slug']}/",
            previous,
            following,
            aria_label="Move navigation",
            identity=lambda value: value["move_id"],
            route_key=lambda value: value["slug"],
            label=lambda value: value["name"],
        )
    )


def _reference_effects_section(record: dict[str, Any]) -> list[str]:
    """Fold PokéDB's supplementary battle-mechanic facts into the Effect section.

    These are just as PokéDB-sourced as the Effect prose above them, so they
    nest under its heading (mirroring how pokemon.py nests "### Level-up
    moves" etc. under "## Learnset") rather than getting a section of their
    own — keeping only two top-level data buckets on the page (PokéDB-sourced
    "Effect", ROM-sourced "Additional battle properties"), matching every
    other kind's page. Rendered as the same plain property/value table as
    "Additional battle properties" (not the boxed `fact_grid()` component used
    for full top-level sections like Mechanics/Training) since the two are
    sibling lists of move facts and should carry the same visual weight.
    """
    properties = _reference_battle_properties(record)
    if not properties:
        return []
    reference = record.get("reference") or {}
    heading_level = (
        "###"
        if any(
            reference.get(field)
            for field in ("short_effect", "effect", "flavor_text")
        )
        else "##"
    )
    return [
        f"{heading_level} Additional effects",
        "",
        *fact_grid(tuple(properties)),
        "",
    ]


def _reference_battle_properties(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Supplementary battle mechanics PokéDB resolves but the ROM never stores.

    Move records only carry an opaque `effect_id` the engine's native code
    interprets; things like crit-rate boosts, drain/heal percentages, and
    secondary-effect chances aren't ROM data at all, so PokéDB is the only
    source for them.
    """
    reference = record.get("reference") or {}
    metadata = reference.get("metadata") or {}
    properties: list[tuple[str, str]] = []
    stat_changes = [
        f"{display_name(change['stat'])} {change['change']:+d}"
        for change in reference.get("stat_changes") or []
        if change.get("change")
    ]
    if stat_changes:
        properties.append(("Stat changes", ", ".join(stat_changes)))
    if metadata.get("crit_rate"):
        properties.append(("Critical-hit rate", f"+{metadata['crit_rate']} stage"))
    drain = metadata.get("drain")
    if drain:
        label = "HP drain" if drain > 0 else "Recoil"
        properties.append((label, f"{abs(drain)}% of damage dealt"))
    if metadata.get("healing"):
        properties.append(("Healing", f"{metadata['healing']}% of max HP"))
    if metadata.get("flinch_chance"):
        properties.append(("Flinch chance", f"{metadata['flinch_chance']}%"))
    ailment = metadata.get("ailment")
    if ailment and ailment != "none":
        properties.append(("Secondary effect", display_name(ailment)))
    if metadata.get("min_hits") is not None:
        properties.append(("Hits", _hit_range(metadata["min_hits"], metadata["max_hits"])))
    if metadata.get("min_turns") is not None:
        properties.append(("Duration", _turn_range(metadata["min_turns"], metadata["max_turns"])))
    return properties


def _hit_range(minimum: int, maximum: int) -> str:
    return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"


def _turn_range(minimum: int, maximum: int) -> str:
    if minimum == maximum:
        return f"{minimum} turn" if minimum == 1 else f"{minimum} turns"
    return f"{minimum}-{maximum} turns"


def _optional_value(value: int) -> str:
    return str(value) if value else "—"


def _accuracy(value: int) -> str:
    return f"{value}%" if value else "Always hits"


def _tutor_compatibility(
    record: dict[str, Any], source_file: str, references: ReferenceIndex | None
) -> list[str]:
    lines = []
    for tutor in record["tutors"]:
        costs = tutor_requirement(tutor)
        location = _tutor_location_link(tutor["location"], source_file)
        lines.extend([f"**{location} — {costs}:**", ""])
        lines.extend(
            _pokemon_sprite_table(
                tutor["compatible_pokemon"],
                source_file,
                references,
                "No compatible Pokémon.",
            )
        )
    return lines


def _tutor_location_link(location: dict[str, Any], source_file: str) -> str:
    if location.get("id") is None:
        return escape_markdown(location["name"])
    return ROUTES.markdown_link(
        entity_reference("location", location["id"], location["name"], location["id"]),
        source_file,
    )


def _tutor_location_link_html(location: dict[str, Any], source_url: str) -> str:
    if location.get("id") is None:
        return escape(location["name"])
    return ROUTES.html_link(
        entity_reference("location", location["id"], location["name"], location["id"]),
        source_url,
    )


def _egg_move_learners(
    record: dict[str, Any], source_file: str, references: ReferenceIndex | None
) -> list[str]:
    return _pokemon_sprite_table(
        record["egg_move_pokemon"], source_file, references, "No egg move learners."
    )


def _pokemon_sprite_table(
    pokemon: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
    empty_message: str,
) -> list[str]:
    if not pokemon:
        return empty_state(empty_message)
    return pokemon_table(
        ["| Pokémon | Type |", "| ------- | ---- |"],
        [
            (
                f"| {_pokemon_table_link(value, source_file, references, True)} | "
                f"{reference_type_cell('pokemon', value.get('member'), references)} |"
            )
            for value in pokemon
        ],
    )


def _pokemon_table_link(
    value: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
    show_sprite: bool,
) -> str:
    link = pokemon_record_link(value, source_file)
    if not show_sprite:
        return link
    return sprite_with_link(
        reference_sprite_cell("pokemon", value.get("member"), references),
        link,
    )


