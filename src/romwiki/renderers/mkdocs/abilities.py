from __future__ import annotations

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
    HIDDEN_ABILITY_MARKER,
    MarkdownColumn,
    description_table_source,
    empty_state,
    markdown_table,
    markdown_table_from_cells,
    name_table_source,
    provenance_section,
    record_navigation_for,
    reference_description,
    reference_source_link,
    reference_sprite_cell,
    reference_type_cell,
    sprite_with_link,
    summary_section,
    summary_section_link,
    table_sprite_cell,
    version_availability_note,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_markdown_link,
    entity_reference,
    pokemon_markdown_link,
)
from romwiki.schema.rendering import AbilityRenderRecord, RenderDataset

_ITEM_COLUMNS = (
    MarkdownColumn("Item"),
    MarkdownColumn("ID", "right"),
)


def render_ability_pages(
    dataset: RenderDataset[AbilityRenderRecord],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = dataset["records"]
    name_source = dataset.get("name_source")
    description_source = dataset.get("description_source")
    output_root.mkdir(parents=True, exist_ok=True)
    filenames = {
        "index.md",
        *(
            f"{record['slug']}.md"
            for record in records
            if only_pages is None or record["slug"] in only_pages
        ),
    }
    prune_catalog_pages(output_root, filenames)

    fallback_links = []
    catalog_records = []
    page_count = 0
    for index, record in enumerate(records):
        change = record_comparison(comparison, record["ability_id"])
        filename = f"{record['slug']}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        if only_pages is None or record["slug"] in only_pages:
            write_text(
                output_root / filename,
                _render_record(
                    record,
                    previous,
                    following,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    name_source,
                    description_source,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "ability",
                    record["ability_id"],
                    f"#{record['ability_id']:03} {record['name']}",
                    record["slug"],
                ),
                "abilities/index.md",
            )
        )
        pokemon_names = [pokemon["name"] for pokemon in record["pokemon"]]
        pokemon_refs = [
            ROUTES.catalog_reference(
                entity_reference(
                    "pokemon",
                    pokemon.get("member", pokemon["national_dex_id"]),
                    pokemon["name"],
                    pokemon.get("slug"),
                ),
                "abilities/",
            )
            for pokemon in record["pokemon"]
        ]
        catalog_records.append(
            add_change_status(
                {
                    "id": record["ability_id"],
                    "label": record["name"],
                    "slug": record["slug"],
                    "url": f"{record['slug']}/",
                    "pokemon": pokemon_names,
                    "pokemon_refs": pokemon_refs,
                    "pokemon_count": len(pokemon_names),
                    "status": "assigned" if pokemon_names else "unassigned",
                    "search_text": " ".join((record["name"], *pokemon_names)).lower(),
                },
                change,
            )
        )

    write_catalog(output_root, "abilities", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Abilities",
            "Abilities extracted from the ROM, with every Pokémon and form that "
            "can have them.",
            "abilities",
            fallback_links,
        ),
    )
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    name_source: dict[str, Any] | None = None,
    description_source: dict[str, Any] | None = None,
) -> str:
    source_file = f"abilities/{record['slug']}.md"
    lines = [
        f"# {record['name']}",
        "",
        *version_availability_note(record),
        *_ability_summary(record),
        *reference_description(
            record, "No PokéDB reference data is available for this ability."
        ),
        *_pickup_section(record.get("pickup"), source_file, references),
        "## Pokémon",
        "",
    ]
    if record["pokemon"]:
        lines.extend(
            markdown_table(
                [
                    "| Pokémon | Type | Ability slot |",
                    "| ------- | ---- | ------------ |",
                ],
                [
                    (
                        f"| {sprite_with_link(table_sprite_cell(pokemon.get('sprite')), _pokemon_link(pokemon, source_file))} | "
                        f"{reference_type_cell('pokemon', pokemon.get('member'), references)} | "
                        f"{', '.join(str(slot) for slot in pokemon['slots'])}"
                        f"{HIDDEN_ABILITY_MARKER if pokemon.get('is_hidden') else ''} |"
                    )
                    for pokemon in record["pokemon"]
                ],
            )
        )
    else:
        lines.extend(empty_state("No Pokémon are assigned this ability."))

    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                "The ability name and Pokémon assignments are exact ROM facts. Ability "
                "behavior is never inferred from the name; structured effect text "
                "comes from PokéDB / PokéAPI reference data."
                + (
                    " The displayed description comes from the ROM message table."
                    if (record.get("reference") or {}).get("flavor_text_source")
                    == "rom"
                    else " Flavor text also comes from that reference data."
                ),
                *(
                    [
                        name_table_source(
                            "Ability", name_source["archive"], name_source["member"]
                        )
                    ]
                    if name_source is not None
                    else []
                ),
                *(
                    [
                        description_table_source(
                            "Ability",
                            description_source["archive"],
                            description_source["member"],
                        )
                    ]
                    if description_source is not None
                    else []
                ),
                *reference_source_link(record),
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _pickup_pool_rows(
    items: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> list[str]:
    return markdown_table_from_cells(
        _ITEM_COLUMNS,
        (
            (
                sprite_with_link(
                    reference_sprite_cell("item", item["item_id"], references),
                    _item_link(item, source_file, references),
                ),
                str(item["item_id"]),
            )
            for item in items
        ),
    )


def _pickup_section(
    pickup: dict[str, Any] | None,
    source_file: str,
    references: ReferenceIndex | None,
) -> list[str]:
    if not pickup:
        return []
    if "level_ranges" in pickup:
        return _sliding_pickup_section(pickup["level_ranges"], source_file, references)
    if "honey_gather_rate" in pickup:
        rates = pickup["honey_gather_rate"]
        lines = [
            "## Honey generation chance",
            "",
            "At the end of a battle, each Pokémon with Honey Gather has a "
            "chance to generate Honey, scaling with its level.",
            "",
            "| Level | Chance |",
            "| ----: | -----: |",
        ]
        lines.extend(
            f"| {tier * 10 + 1}–{tier * 10 + 10} | {rate}% |"
            for tier, rate in enumerate(rates)
        )
        lines.append("")
        return lines

    lines = [
        "## Held items",
        "",
        "At the end of a battle, a Pokémon with Pickup has a 10% chance to "
        "check for an item if it isn't already holding one. Both pools slide "
        "with the Pokémon's level (floor(level − 1) / 10, capped at the "
        "table's last tier): higher-level Pokémon skip toward later, more "
        "valuable entries in each list rather than always drawing from the "
        "start.",
        "",
        "| Level | Common chance |",
        "| ----: | -------------: |",
    ]
    lines.extend(
        f"| {tier * 10 + 1}–{tier * 10 + 10} | {rate}% |"
        for tier, rate in enumerate(pickup["common_rate"])
    )
    lines.extend(["", "**Common pool:**", ""])
    lines.extend(_pickup_pool_rows(pickup["common_items"], source_file, references))
    lines.extend(["**Rare pool** (the remaining chance):", ""])
    lines.extend(_pickup_pool_rows(pickup["rare_items"], source_file, references))
    return lines


def _sliding_pickup_section(
    level_ranges: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> list[str]:
    lines = [
        "## Held items",
        "",
        "At the end of a battle, a Pokémon with Pickup has a 10% chance to "
        "check for an item if it isn't already holding one. Which item "
        "depends on the Pokémon's level -- each 10-level range draws from "
        "its own weighted list of 11 possible items.",
        "",
    ]
    for level_range in level_ranges:
        lines.extend(
            [
                f"### Level {level_range['minimum_level']}"
                f"–{level_range['maximum_level']}",
                "",
            ]
        )
        lines.extend(
            markdown_table(
                ["| Item | ID | Chance |", "| ---- | -: | -----: |"],
                [
                    f"| {sprite_with_link(reference_sprite_cell('item', slot['item_id'], references), _item_link(slot, source_file, references))} | "
                    f"{slot['item_id']} | {slot['chance']}% |"
                    for slot in level_range["slots"]
                ],
            )
        )
    return lines


def _item_link(
    item: dict[str, Any], source_file: str, references: ReferenceIndex | None
) -> str:
    return entity_markdown_link(
        "item", item["item_id"], item["name"], source_file, index=references
    )


def _ability_summary(record: dict[str, Any]) -> list[str]:
    return summary_section(
        "rw-ability-summary",
        [
            f"<div><dt>Ability ID</dt><dd>{record['ability_id']}</dd></div>",
            f"<div><dt>Pokémon with this ability</dt>"
            f"<dd>{summary_section_link(len(record['pokemon']), 'pokemon')}</dd></div>",
        ],
    )


def _pokemon_link(pokemon: dict[str, Any], source_file: str) -> str:
    return pokemon_markdown_link(
        pokemon.get("member", pokemon["national_dex_id"]),
        pokemon["name"],
        pokemon.get("slug"),
        source_file,
    )


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "ability",
            f"abilities/{record['slug']}/",
            previous,
            following,
            aria_label="Ability navigation",
            identity=lambda value: value["ability_id"],
            route_key=lambda value: value["slug"],
            label=lambda value: value["name"],
        )
    )
