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
    badge_requirement,
    display_name,
    fact_grid,
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
    shop_price,
    sprite_with_link,
    summary_section_link,
    type_badges,
    yes_no,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_markdown_link,
    entity_reference,
    pokemon_record_link,
    unique_references,
)


def render_item_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = dataset["records"]
    name_source = dataset.get("source", {}).get("item_names")
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
        change = record_comparison(comparison, record["item_id"])
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
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "item",
                    record["item_id"],
                    f"#{record['item_id']:03} {record['name']}",
                    record["slug"],
                ),
                "items/index.md",
            )
        )
        features = _features(record)
        category = (record.get("reference") or {}).get("category")
        locations = list(
            dict.fromkeys(
                reference["name"]
                for field in ("locations", "shops", "gifts", "trades")
                for reference in record[field]
            )
        )
        location_refs = unique_references(
            [
                entity_reference(
                    "location",
                    reference["header_id"],
                    reference["name"],
                    reference.get("header_id"),
                )
                for field in ("locations", "shops", "gifts", "trades")
                for reference in record[field]
            ]
        )
        catalog_records.append(
            add_change_status({
                "id": record["item_id"],
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "pocket": record["pocket"]["name"],
                "field_use": record["field_use"]["name"],
                "category": category,
                "price": record["price"],
                "fling_power": record["fling_power"],
                "features": features,
                "locations": locations,
                "location_refs": [
                    ROUTES.catalog_reference(reference, "items/")
                    for reference in location_refs
                ],
                "search_text": " ".join(
                    (
                        record["name"],
                        *((category,) if category else ()),
                        *features,
                        *locations,
                    )
                ).lower(),
            }, change)
        )
    write_catalog(output_root, "items", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Items",
            "Item properties and references extracted from the ROM.",
            "items",
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
) -> str:
    source_file = f"items/{record['slug']}.md"
    mechanics = [
        ("Field use", escape(display_name(record["field_use"]["name"]))),
        ("Field pocket ID", str(record["field_pocket_id"])),
        ("Field use function ID", str(record["field_use_function_id"])),
        ("Held effect ID", str(record["hold_effect_id"])),
        ("Held effect parameter", str(record["hold_effect_parameter"])),
        ("Battle use function ID", str(record["battle_use_function_id"])),
        ("Battle pocket mask", f"{record['battle_pocket_mask']:#04x}"),
        ("Usable on party", yes_no(record["party_use"])),
    ]
    if record["pluck_effect_id"]:
        mechanics.append(("Pluck effect ID", str(record["pluck_effect_id"])))
    if record["fling_power"]:
        mechanics.append(("Fling effect ID", str(record["fling_effect_id"])))
    if record["natural_gift_power"]:
        gift_type = record["natural_gift_type"]
        mechanics.append(
            (
                "Natural Gift",
                f"{record['natural_gift_power']} power, {type_badges([gift_type])}",
            )
        )
    party_effects = _party_effects(record)
    if party_effects:
        mechanics.append(
            ("Party-use effects", escape(", ".join(party_effects)))
        )
    lines = [
        f"# {record['name']}",
        "",
        *_item_summary(record),
        *reference_description(
            record, "No PokéDB reference data is available for this item."
        ),
        "## Mechanics",
        "",
        *fact_grid(tuple(mechanics), escape_values=False),
        "",
    ]

    _append_berry_mechanics(lines, record.get("berry"))
    _append_locations(lines, record, source_file)
    _append_shops(lines, record["shops"], source_file)
    _append_pokemon(lines, record, source_file, references)
    _append_trainers(lines, record, source_file)
    _append_gifts_and_trades(lines, record, source_file, references)
    _append_evolutions(lines, record["evolutions"], source_file, references)
    _append_fossil_revival(lines, record["revives_into"], source_file, references)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        (
                            "Data archive member",
                            f"`{record['data_archive_member']}`",
                        ),
                    )
                ),
                rom_record_source(
                    record["provenance"]["archive"], record["provenance"]["member"]
                ),
                "The name, item-data member mapping, mechanics, and references are exact "
                "ROM facts. Numeric effect IDs are retained when their behavior is "
                "implemented by game code rather than the item record. Effect "
                "description, flavor text, and icon come from PokéDB / PokéAPI "
                "reference data.",
                *(
                    [
                        name_table_source(
                            "Item", name_source["archive"], name_source["member"]
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


def _item_summary(record: dict[str, Any]) -> list[str]:
    reference = record.get("reference") or {}
    sprite_url = reference.get("sprite_url")
    if sprite_url:
        media = (
            f'<img src="{escape(sprite_url, quote=True)}" '
            f'alt="{escape(record["name"], quote=True)} icon" loading="lazy" '
            'referrerpolicy="no-referrer">'
        )
    else:
        media = '<span class="rw-summary__placeholder">Icon unavailable</span>'
    price = f"₽{record['price']:,}"
    facts = [
        ("Item ID", escape(str(record["item_id"]))),
        ("Pocket", escape(display_name(record["pocket"]["name"]))),
        ("Base price", escape(price)),
        ("Selectable", escape(yes_no(record["selectable"]))),
        ("Can be discarded", escape(yes_no(not record["prevent_toss"]))),
    ]
    if record["fling_power"]:
        facts.append(
            (
                "Fling power",
                summary_section_link(record["fling_power"], "mechanics"),
            )
        )
    return [
        '<section class="rw-summary">',
        f'<div class="rw-summary__media">{media}</div>',
        '<div class="rw-summary__body">',
        '<dl class="rw-summary__facts">',
        *(
            f"<div><dt>{escape(label)}</dt><dd>{value}</dd></div>"
            for label, value in facts
        ),
        "</dl>",
        "</div>",
        "</section>",
        "",
    ]


def _append_locations(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    if not record["locations"]:
        return
    lines.extend(["## Overworld locations", ""])
    lines.extend(
        [
            "| Location | Kind | Coordinates |",
            "| -------- | ---- | ----------- |",
            *[
                (
                    f"| {_location_link(value, source_file)} "
                    f"| {value['kind'].title()} | ({value['x']}, {value['z']}) |"
                )
                for value in record["locations"]
            ],
            "",
        ]
    )


def _append_shops(
    lines: list[str], shops: list[dict[str, Any]], source_file: str
) -> None:
    if not shops:
        return
    lines.extend(["## Shops", ""])
    lines.extend(
        [
            "| Location | Shop | Price | Availability |",
            "| -------- | ---- | ----: | ------------ |",
            *[
                (
                    f"| {_location_link(shop, source_file)} "
                    f"| {shop['kind'].title()} | "
                    f"{shop_price(shop['price'], shop.get('currency', 'money'))} | "
                    f"{badge_requirement(shop['required_badges'])} |"
                )
                for shop in shops
            ],
            "",
        ]
    )


def _append_pokemon(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not record["wild_held_by"]:
        return
    lines.extend(["## Wild held by", ""])
    lines.extend(
        pokemon_table(
            ["| Pokémon | Type | Rarity |", "| ------- | ---- | ------ |"],
            [
                (
                    f"| {sprite_with_link(_pokemon_sprite_cell(value, references), pokemon_record_link(value, source_file))} "
                    f"| {reference_type_cell('pokemon', value.get('member', value.get('id')), references)} "
                    f"| {value['rarity'].title()} |"
                )
                for value in record["wild_held_by"]
            ],
        )
    )


def _pokemon_sprite_cell(
    pokemon: dict[str, Any], references: ReferenceIndex | None
) -> str:
    return reference_sprite_cell(
        "pokemon", pokemon.get("member", pokemon.get("id")), references
    )


def _append_trainers(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    values = [
        (value, f"Held by {value['pokemon']['name']}")
        for value in record["trainer_held_by"]
    ] + [
        (value, "AI battle item")
        for value in record["trainer_battle_items"]
    ]
    if not values:
        return
    lines.extend(["## Trainer references", ""])
    lines.extend(
        [
            "| Trainer | Reference |",
            "| ------- | --------- |",
            *[
                (
                    f"| {_trainer_link(value, source_file)} | {kind} |"
                )
                for value, kind in values
            ],
            "",
        ]
    )


def _append_gifts_and_trades(
    lines: list[str],
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    values = [
        (value, "Gift", value["pokemon"]) for value in record["gifts"]
    ] + [(value, "Trade", value["pokemon"]) for value in record["trades"]]
    if not values:
        return
    lines.extend(["## Gifts and trades", ""])
    lines.extend(
        [
            "| Location | Kind | Pokémon | Type |",
            "| -------- | ---- | ------- | ---- |",
            *[
                (
                    f"| {_location_link(value, source_file)} "
                    f"| {kind} | {sprite_with_link(_pokemon_sprite_cell(pokemon, references), pokemon_record_link(pokemon, source_file))} "
                    f"| {reference_type_cell('pokemon', pokemon.get('member', pokemon.get('id')), references)} |"
                )
                for value, kind, pokemon in values
            ],
            "",
        ]
    )


def _append_evolutions(
    lines: list[str],
    evolutions: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not evolutions:
        return
    lines.extend(["## Evolutions", ""])
    lines.extend(
        [
            "| From | To | Method |",
            "| ---- | -- | ------ |",
            *[
                (
                    f"| {sprite_with_link(_pokemon_sprite_cell(value['source'], references), pokemon_record_link(value['source'], source_file))} "
                    f"| {sprite_with_link(_pokemon_sprite_cell(value['target'], references), pokemon_record_link(value['target'], source_file))} | "
                    f"{display_name(value['method'])} |"
                )
                for value in evolutions
            ],
            "",
        ]
    )


def _append_berry_mechanics(
    lines: list[str], berry: dict[str, Any] | None
) -> None:
    if not berry:
        return
    lines.extend(
        [
            "## Berry mechanics",
            "",
            *fact_grid(
                (
                    ("Firmness", berry["firmness_name"]),
                    ("Size", f"{berry['size']} mm"),
                    ("Base yield", str(berry["base_yield"])),
                    ("Growth stage duration", f"{berry['stage_duration']} hours"),
                    ("Moisture drain rate", str(berry["moisture_drain_rate"])),
                )
            ),
            "",
            "**Contest flavor:**",
            "",
            *fact_grid(
                (
                    ("Spicy", str(berry["spiciness"])),
                    ("Dry", str(berry["dryness"])),
                    ("Sweet", str(berry["sweetness"])),
                    ("Bitter", str(berry["bitterness"])),
                    ("Sour", str(berry["sourness"])),
                    ("Smoothness", str(berry["smoothness"])),
                )
            ),
            "",
        ]
    )


def _append_fossil_revival(
    lines: list[str],
    revives_into: dict[str, Any] | None,
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not revives_into:
        return
    lines.extend(
        [
            "## Fossil revival",
            "",
            "Reviving this fossil produces:",
            "",
            f"{sprite_with_link(_pokemon_sprite_cell(revives_into, references), pokemon_record_link(revives_into, source_file))}",
            "",
        ]
    )


def _party_effects(record: dict[str, Any]) -> list[str]:
    if not record["party_use"]:
        return []
    effects = record["party_effects"]
    labels = {
        "heal_sleep": "cures sleep",
        "heal_poison": "cures poison",
        "heal_burn": "cures burn",
        "heal_freeze": "cures freeze",
        "heal_paralysis": "cures paralysis",
        "heal_confusion": "cures confusion",
        "heal_attract": "cures infatuation",
        "guard_spec": "prevents stat reduction",
        "revive": "revives",
        "revive_all": "revives party",
        "level_up": "raises level",
        "evolve": "triggers evolution",
        "pp_up": "raises PP",
        "pp_max": "maximizes PP",
        "pp_restore": "restores PP",
        "pp_restore_all": "restores all PP",
        "hp_restore": "restores HP",
    }
    result = [label for key, label in labels.items() if effects[key]]
    if effects["hp_restore"]:
        result.append(f"HP amount {effects['hp_restored']}")
    if effects["pp_restore"] or effects["pp_restore_all"]:
        result.append(f"PP amount {effects['pp_restored']}")
    for label, key in (
        ("Attack", "attack_stages"),
        ("Defense", "defense_stages"),
        ("Sp. Atk", "special_attack_stages"),
        ("Sp. Def", "special_defense_stages"),
        ("Speed", "speed_stages"),
        ("Accuracy", "accuracy_stages"),
        ("Critical-hit rate", "critical_hit_stages"),
    ):
        stages = effects[key]
        if stages:
            suffix = "stage" if abs(stages) == 1 else "stages"
            result.append(f"{label} {stages:+d} {suffix}")
    for label, key in (
        ("HP", "hp"),
        ("Attack", "attack"),
        ("Defense", "defense"),
        ("Speed", "speed"),
        ("Sp. Atk", "special_attack"),
        ("Sp. Def", "special_defense"),
    ):
        if effects[f"{key}_ev"]:
            result.append(f"{label} EVs {effects[f'{key}_ev_amount']:+d}")
    friendship = [
        f"{tier} {effects[f'friendship_{tier}_amount']:+d}"
        for tier in ("low", "medium", "high")
        if effects[f"friendship_{tier}"]
    ]
    if friendship:
        result.append(f"friendship ({', '.join(friendship)})")
    return result


def _location_link(value: dict[str, Any], source_file: str) -> str:
    return entity_markdown_link(
        "location",
        value["header_id"],
        value["name"],
        source_file,
        route_key=value.get("header_id"),
    )


def _trainer_link(value: dict[str, Any], source_file: str) -> str:
    label = " ".join(
        part for part in (value.get("class_name"), value.get("name")) if part
    )
    return entity_markdown_link(
        "trainer",
        value["trainer_id"],
        label,
        source_file,
        route_key=value.get("trainer_id"),
    )


def _features(record: dict[str, Any]) -> list[str]:
    values = []
    for field, label in (
        ("locations", "overworld"),
        ("shops", "shop"),
        ("wild_held_by", "wild-held"),
        ("trainer_held_by", "trainer-held"),
        ("trainer_battle_items", "trainer-ai-item"),
        ("gifts", "gift"),
        ("trades", "trade"),
        ("evolutions", "evolution"),
    ):
        if record[field]:
            values.append(label)
    return values


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "item",
            f"items/{record['slug']}/",
            previous,
            following,
            aria_label="Item navigation",
            identity=lambda value: value["item_id"],
            route_key=lambda value: value["slug"],
            label=lambda value: value["name"],
            sprite_url=lambda value: (value.get("reference") or {}).get(
                "sprite_url"
            ),
        )
    )
