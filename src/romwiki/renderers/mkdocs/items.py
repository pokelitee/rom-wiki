from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.pipeline.transforms.relationships import RelationshipIndex
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
    content_tabs,
    description_table_source,
    display_name,
    fact_grid,
    markdown_table,
    name_table_source,
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
    summary_hero,
    summary_section_link,
    type_badges,
    version_availability_note,
    version_variant_records,
    with_resolved_location_labels,
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
from romwiki.schema.rendering import ItemRenderRecord, RenderDataset


def render_item_pages(
    dataset: RenderDataset[ItemRenderRecord],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    location_labels = relationships.location_labels if relationships else None
    records = [
        with_resolved_location_labels(record, location_labels)
        for record in dataset["records"]
    ]
    name_source = dataset.get("source", {}).get("item_names")
    description_source = dataset.get("description_sources", {}).get("item_descriptions")
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
                    description_source,
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
        source_records = [value for _, value in version_variant_records(record)]
        features = list(
            dict.fromkeys(
                feature
                for source_record in source_records
                for feature in _features(source_record)
            )
        )
        category = (record.get("reference") or {}).get("category")
        locations = list(
            dict.fromkeys(
                # Detached catalog shops use "shop_name" instead of "name";
                # location-linked shops provide both.
                reference.get("name", reference.get("shop_name"))
                for source_record in source_records
                for field in ("locations", "shops", "gifts", "trades")
                for reference in source_record[field]
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
                for source_record in source_records
                for field in ("locations", "shops", "gifts", "trades")
                for reference in source_record[field]
                # Some trades genuinely have no single map, so only resolved
                # references become location links.
                if reference.get("header_id") is not None
            ]
        )
        catalog_records.append(
            add_change_status(
                {
                    "id": record["item_id"],
                    "label": record["name"],
                    "slug": record["slug"],
                    "url": f"{record['slug']}/",
                    "pocket": record.get("pocket", {}).get("name"),
                    "field_use": record.get("field_use", {}).get("name"),
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
                },
                change,
            )
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
    description_source: dict[str, Any] | None = None,
) -> str:
    source_file = f"items/{record['slug']}.md"
    mechanics = []
    if "field_use" in record:
        mechanics.append(
            ("Field use", escape(display_name(record["field_use"]["name"])))
        )
    if "field_pocket_id" in record:
        mechanics.append(("Field pocket ID", str(record["field_pocket_id"])))
    if "field_use_function_id" in record:
        mechanics.append(
            ("Field use function ID", str(record["field_use_function_id"]))
        )
    if "hold_effect_id" in record:
        mechanics.append(("Held effect ID", str(record["hold_effect_id"])))
    if "hold_effect_parameter" in record:
        mechanics.append(
            ("Held effect parameter", str(record["hold_effect_parameter"]))
        )
    if "battle_use_function_id" in record:
        mechanics.append(
            ("Battle use function ID", str(record["battle_use_function_id"]))
        )
    if "battle_pocket_mask" in record:
        mechanics.append(("Battle pocket mask", f"{record['battle_pocket_mask']:#04x}"))
    if "party_use" in record:
        mechanics.append(("Usable on party", yes_no(record["party_use"])))
    if record.get("pluck_effect_id"):
        mechanics.append(("Pluck effect ID", str(record["pluck_effect_id"])))
    if record["fling_power"]:
        mechanics.append(("Fling effect ID", str(record["fling_effect_id"])))
    if record.get("natural_gift_power"):
        gift_type = record["natural_gift_type"]
        mechanics.append(
            (
                "Natural Gift",
                f"{record['natural_gift_power']} power, {type_badges([gift_type])}",
            )
        )
    party_effects = _party_effects(record)
    if party_effects:
        mechanics.append(("Party-use effects", escape(", ".join(party_effects))))
    lines = [
        f"# {record['name']}",
        "",
        *version_availability_note(record),
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
    _append_shops(lines, record, source_file)
    _append_pokemon(lines, record, source_file, references)
    _append_trainers(lines, record, source_file)
    _append_gifts_and_trades(lines, record, source_file, references)
    _append_evolutions(lines, record["evolutions"], source_file, references)
    _append_fossil_revival(
        lines,
        record["revives_into"],
        record.get("revives_at", []),
        source_file,
        references,
    )
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
                "The name, item-data member mapping, mechanics, and relationships are "
                "exact ROM facts. Numeric effect IDs are retained when their behavior "
                "is implemented by game code rather than the item record. Structured "
                "effect text and the icon come from PokéDB / PokéAPI reference data."
                + (
                    " The displayed description comes from the ROM message table."
                    if (record.get("reference") or {}).get("flavor_text_source")
                    == "rom"
                    else " Flavor text also comes from that reference data."
                ),
                *(
                    [
                        name_table_source(
                            "Item", name_source["archive"], name_source["member"]
                        )
                    ]
                    if name_source is not None
                    else []
                ),
                *(
                    [
                        description_table_source(
                            "Item",
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
    category = reference.get("category")
    pocket = record.get("pocket")
    facts = [
        ("Item ID", escape(str(record["item_id"]))),
        *(
            [("Pocket", escape(display_name(pocket["name"])))]
            if pocket is not None
            else []
        ),
        *([("Category", escape(display_name(category)))] if category else []),
        ("Base price", escape(price)),
        *(
            [("Selectable", escape(yes_no(record["selectable"])))]
            if "selectable" in record
            else []
        ),
        *(
            [("Can be discarded", escape(yes_no(not record["prevent_toss"])))]
            if "prevent_toss" in record
            else []
        ),
    ]
    if record["fling_power"]:
        facts.append(
            (
                "Fling power",
                summary_section_link(record["fling_power"], "mechanics"),
            )
        )
    fact_lines = [
        f"<div><dt>{escape(label)}</dt><dd>{value}</dd></div>" for label, value in facts
    ]
    return summary_hero(media, fact_lines)


def _append_locations(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    if not record["locations"]:
        return
    lines.extend(["## Overworld locations", ""])
    lines.extend(
        [
            "| Location | Section | Map ID | Kind | Position |",
            "| -------- | ------- | ------ | ---- | -------- |",
            *[
                (
                    f"| {_location_link(value, source_file)} "
                    f"| {_location_section(value)} | {_map_header(value)} "
                    f"| {display_name(value['kind'])} | "
                    f"{_item_position(value)} |"
                )
                for value in record["locations"]
            ],
            "",
        ]
    )


def _item_position(value: dict[str, Any]) -> str:
    x = value.get("x")
    z = value.get("z")
    return f"({x}, {z})" if isinstance(x, int) and isinstance(z, int) else "—"


def _append_shops(lines: list[str], record: dict[str, Any], source_file: str) -> None:
    shops = record["shops"]
    if not shops:
        return
    lines.extend(["## Shops", ""])
    linked_shops = [shop for shop in shops if "header_id" in shop]
    standalone_shops = [shop for shop in shops if "header_id" not in shop]
    if linked_shops:
        lines.extend(
            [
                "| Location | Section | Map ID | Shop | Price | Availability |",
                "| -------- | ------- | ------ | ---- | ----: | ------------ |",
                *[
                    (
                        f"| {_location_link(shop, source_file)} "
                        f"| {_location_section(shop)} | {_map_header(shop)} "
                        f"| {escape(shop.get('shop_name') or shop['kind'].title())} "
                        "| "
                        f"{shop_price(shop['price'], shop.get('currency', 'money'))} | "
                        f"{_shop_availability(shop)} |"
                    )
                    for shop in linked_shops
                ],
                "",
            ]
        )
    # Standalone fallback for inventories without a verified location link.
    if not standalone_shops:
        return
    lines.extend(
        [
            "| Shop | Price | Availability |",
            "| ---- | ----: | ------------ |",
            *[
                (
                    f"| {escape(shop['shop_name'])} "
                    f"| {shop_price(record['price'], 'money')} | "
                    f"{'Main game' if shop['is_main_game'] else 'Post-game'} |"
                )
                for shop in standalone_shops
            ],
            "",
        ]
    )


def _shop_availability(shop: dict[str, Any]) -> str:
    if shop.get("availability"):
        return shop["availability"]
    if shop.get("is_main_game") is not None:
        return "Main game" if shop["is_main_game"] else "Post-game"
    return badge_requirement(shop["required_badges"])


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
        markdown_table(
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
    values = (
        [
            (value, f"Held by {value['pokemon']['name']}")
            for value in record["trainer_held_by"]
        ]
        + [(value, "AI battle item") for value in record["trainer_battle_items"]]
        + [(value, "Victory reward") for value in record.get("trainer_rewards", [])]
    )
    if not values:
        return
    lines.extend(["## Trainer references", ""])
    lines.extend(
        [
            "| Trainer | Reference |",
            "| ------- | --------- |",
            *[
                (f"| {_trainer_link(value, source_file)} | {kind} |")
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
    version_records = version_variant_records(record)
    variant_records = [value for _, value in version_records]
    gifts_and_trades_differ = version_records[0][0] is not None and any(
        (value["gifts"], value["trades"])
        != (variant_records[0]["gifts"], variant_records[0]["trades"])
        for value in variant_records[1:]
    )
    if gifts_and_trades_differ:
        lines.extend(["## Gifts and trades", ""])
        tabs: list[tuple[str, list[str]]] = []
        for version, version_record in version_records:
            assert version is not None
            content: list[str] = []
            values = _gift_trade_values(version_record)
            if values:
                _append_gift_trade_table(content, values, source_file, references)
            else:
                content.extend(["No gift or trade references.", ""])
            tabs.append((display_name(version), content))
        lines.extend(content_tabs(tabs))
        return

    values = _gift_trade_values(record)
    if not values:
        return
    lines.extend(["## Gifts and trades", ""])
    _append_gift_trade_table(lines, values, source_file, references)


def _gift_trade_values(
    record: dict[str, Any],
) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
    return [(value, "Gift", value["pokemon"]) for value in record["gifts"]] + [
        (value, "Trade", value["pokemon"]) for value in record["trades"]
    ]


def _append_gift_trade_table(
    lines: list[str],
    values: list[tuple[dict[str, Any], str, dict[str, Any]]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    lines.extend(
        [
            "| Location | Section | Map ID | Kind | Pokémon | Type |",
            "| -------- | ------- | ------ | ---- | ------- | ---- |",
            *[
                (
                    f"| {_location_or_trade_cell(value, source_file)} "
                    f"| {_location_section(value)} | {_map_header(value)} "
                    f"| {kind} | {sprite_with_link(_pokemon_sprite_cell(pokemon, references), pokemon_record_link(pokemon, source_file))} "
                    f"| {reference_type_cell('pokemon', pokemon.get('member', pokemon.get('id')), references)} |"
                )
                for value, kind, pokemon in values
            ],
            "",
        ]
    )


def _location_or_trade_cell(value: dict[str, Any], source_file: str) -> str:
    # Locationless trades show the NPC identity instead of an invented link.
    if "header_id" in value:
        return _location_link(value, source_file)
    trade = f"{value['ot_name']} (nicknamed {value['nickname']})"
    if value.get("interaction") == "xtransceiver":
        return f"Xtransceiver — {trade}"
    return trade


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


def _append_berry_mechanics(lines: list[str], berry: dict[str, Any] | None) -> None:
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
    locations: list[dict[str, Any]],
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
    if locations:
        lines.extend(
            [
                "Revival location: "
                + ", ".join(
                    _location_link(location, source_file) for location in locations
                ),
                "",
            ]
        )


def _party_effects(record: dict[str, Any]) -> list[str]:
    if not record.get("party_use"):
        return []
    effects = record["party_effects"]
    # Gen5's party effects have no `evolve` concept at all (that Gen4 key is
    # absent from ItemPartyUseEffects entirely, not just always-false), so
    # its presence distinguishes which shape this record carries.
    if "evolve" not in effects:
        return _party_use_effects(effects)
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


def _party_use_effects(effects: dict[str, Any]) -> list[str]:
    labels = {
        "heal_sleep": "cures sleep",
        "heal_poison": "cures poison",
        "heal_burn": "cures burn",
        "heal_freeze": "cures freeze",
        "heal_paralysis": "cures paralysis",
        "heal_confusion": "cures confusion",
        "revive": "revives",
        "revive_all": "revives party",
        "level_up": "raises level",
    }
    result = [label for key, label in labels.items() if effects[key]]
    if effects["hp_restored"]:
        result.append(f"HP amount {effects['hp_restored']}")
    if effects["pp_restored"]:
        result.append(f"PP amount {effects['pp_restored']}")
    for label, key in (
        ("HP", "hp_ev_amount"),
        ("Attack", "attack_ev_amount"),
        ("Defense", "defense_ev_amount"),
        ("Speed", "speed_ev_amount"),
        ("Sp. Atk", "special_attack_ev_amount"),
        ("Sp. Def", "special_defense_ev_amount"),
    ):
        amount = effects[key]
        if amount:
            result.append(f"{label} EVs {amount:+d}")
    friendship = [
        f"{tier} {effects[f'friendship_{tier}_amount']:+d}"
        for tier in ("low", "medium", "high")
        if effects[f"friendship_{tier}_amount"]
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


def _location_section(value: dict[str, Any]) -> str:
    return escape(value.get("section_name") or "—")


def _map_header(value: dict[str, Any]) -> str:
    header_id = value.get("header_id")
    return f"`header-{header_id:03}`" if isinstance(header_id, int) else "—"


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
        ("trainer_rewards", "trainer-reward"),
        ("gifts", "gift"),
        ("trades", "trade"),
        ("evolutions", "evolution"),
    ):
        if record.get(field):
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
            sprite_url=lambda value: (value.get("reference") or {}).get("sprite_url"),
        )
    )
