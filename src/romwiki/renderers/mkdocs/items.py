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
from romwiki.renderers.mkdocs.components import (
    display_name,
    fact_grid,
    record_nav_link,
    record_navigation,
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
    pokemon_markdown_link,
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
                "price": record["price"],
                "fling_power": record["fling_power"],
                "features": features,
                "locations": locations,
                "location_refs": [
                    ROUTES.catalog_reference(reference, "items/")
                    for reference in location_refs
                ],
                "search_text": " ".join((record["name"], *features, *locations)).lower(),
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
) -> str:
    source_file = f"items/{record['slug']}.md"
    mechanics = [
        ("Field use", display_name(record["field_use"]["name"])),
        ("Held effect ID", str(record["hold_effect_id"])),
        ("Held effect parameter", str(record["hold_effect_parameter"])),
        ("Battle use function ID", str(record["battle_use_function_id"])),
        ("Battle pocket mask", f"{record['battle_pocket_mask']:#04x}"),
    ]
    if record["fling_power"]:
        mechanics.extend(
            [
                ("Fling power", str(record["fling_power"])),
                ("Fling effect ID", str(record["fling_effect_id"])),
            ]
        )
    if record["natural_gift_power"]:
        gift_type = record["natural_gift_type"]
        mechanics.append(
            (
                "Natural Gift",
                f"{record['natural_gift_power']} power, {gift_type['name']} type",
            )
        )
    party_effects = _party_effects(record)
    if party_effects:
        mechanics.append(("Party-use effects", ", ".join(party_effects)))
    lines = [
        f"# {record['name']}",
        "",
        *_item_summary(record),
        *_item_description(record),
        *comparison_section(change, baseline_name, source_file, references),
        "## Mechanics",
        "",
        *fact_grid(tuple(mechanics)),
        "",
    ]

    _append_locations(lines, record, source_file)
    _append_shops(lines, record["shops"], source_file)
    _append_pokemon(lines, record, source_file)
    _append_trainers(lines, record, source_file)
    _append_gifts_and_trades(lines, record, source_file)
    _append_evolutions(lines, record["evolutions"], source_file)
    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Data provenance</summary>",
            "",
            "The name, item-data member mapping, mechanics, and references are exact "
            "ROM facts. Numeric effect IDs are retained when their behavior is "
            "implemented by game code rather than the item record. Effect "
            "description, flavor text, and icon come from PokéDB / PokéAPI "
            "reference data.",
            "",
            "</details>",
            "",
        ]
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
    price = f"₽{record['price']:,}" if record["price"] else "Not sold"
    facts = [
        ("Item ID", str(record["item_id"])),
        ("Pocket", display_name(record["pocket"]["name"])),
        ("Price", price),
        ("Selectable", _yes_no(record["selectable"])),
        ("Can be discarded", _yes_no(not record["prevent_toss"])),
    ]
    if record["fling_power"]:
        facts.append(("Fling power", str(record["fling_power"])))
    return [
        '<section class="rw-summary">',
        f'<div class="rw-summary__media">{media}</div>',
        '<div class="rw-summary__body">',
        '<dl class="rw-summary__facts">',
        *(
            f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
            for label, value in facts
        ),
        "</dl>",
        "</div>",
        "</section>",
        "",
    ]


def _item_description(record: dict[str, Any]) -> list[str]:
    reference = record.get("reference") or {}
    short_effect = reference.get("short_effect")
    effect = reference.get("effect")
    flavor_text = reference.get("flavor_text")
    lines: list[str] = []
    if short_effect or effect:
        lines.extend(["## Effect", ""])
        if short_effect:
            lines.append(f'<p><strong>{escape(" ".join(short_effect.split()))}</strong></p>')
        if effect and effect != short_effect:
            lines.append(f'<p>{escape(" ".join(effect.split()))}</p>')
        lines.append("")
    if flavor_text:
        version_label = (
            f"{display_name(reference['version'])} Pokédex"
            if reference.get("version")
            else "Pokédex"
        )
        lines.extend(
            [
                '<figure class="rw-pokedex-entry">',
                f"<blockquote>{escape(' '.join(flavor_text.split()))}</blockquote>",
                f"<figcaption>{escape(version_label)}</figcaption>",
                "</figure>",
                "",
            ]
        )
    if not lines:
        lines = ["No PokéDB reference data is available for this item.", ""]
    return lines


def _append_locations(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    lines.extend(["## Overworld locations", ""])
    if not record["locations"]:
        lines.extend(["None found.", ""])
        return
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
    lines.extend(["## Shops", ""])
    if not shops:
        lines.extend(["Not sold by an extracted shop.", ""])
        return
    lines.extend(
        [
            "| Location | Shop | Price | Availability |",
            "| -------- | ---- | ----: | ------------ |",
            *[
                (
                    f"| {_location_link(shop, source_file)} "
                    f"| {shop['kind'].title()} | {_shop_price(shop)} | "
                    f"{_availability(shop['required_badges'])} |"
                )
                for shop in shops
            ],
            "",
        ]
    )


def _append_pokemon(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    lines.extend(["## Wild held by", ""])
    if not record["wild_held_by"]:
        lines.extend(["No wild held-item assignments.", ""])
        return
    lines.extend(
        [
            "| Pokémon | Slot |",
            "| ------- | ---- |",
            *[
                f"| {_pokemon_link(value, source_file)} | {value['rarity'].title()} |"
                for value in record["wild_held_by"]
            ],
            "",
        ]
    )


def _append_trainers(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    lines.extend(["## Trainer references", ""])
    values = [
        (value, f"Held by {value['pokemon']['name']}")
        for value in record["trainer_held_by"]
    ] + [
        (value, "AI battle item")
        for value in record["trainer_battle_items"]
    ]
    if not values:
        lines.extend(["No trainer references.", ""])
        return
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
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    lines.extend(["## Gifts and trades", ""])
    values = [
        (value, "Gift", value["pokemon"]) for value in record["gifts"]
    ] + [(value, "Trade", value["pokemon"]) for value in record["trades"]]
    if not values:
        lines.extend(["No gift or trade references.", ""])
        return
    lines.extend(
        [
            "| Location | Kind | Pokémon |",
            "| -------- | ---- | ------- |",
            *[
                (
                    f"| {_location_link(value, source_file)} "
                    f"| {kind} | {_pokemon_link(pokemon, source_file)} |"
                )
                for value, kind, pokemon in values
            ],
            "",
        ]
    )


def _append_evolutions(
    lines: list[str], evolutions: list[dict[str, Any]], source_file: str
) -> None:
    lines.extend(["## Evolutions", ""])
    if not evolutions:
        lines.extend(["No extracted evolutions use this item.", ""])
        return
    lines.extend(
        [
            "| From | To | Method |",
            "| ---- | -- | ------ |",
            *[
                (
                    f"| {_pokemon_link(value['source'], source_file)} | "
                    f"{_pokemon_link(value['target'], source_file)} | "
                    f"{display_name(value['method'])} |"
                )
                for value in evolutions
            ],
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
    return result


def _location_link(value: dict[str, Any], source_file: str) -> str:
    return ROUTES.markdown_link(
        entity_reference(
            "location",
            value["header_id"],
            value["name"],
            value.get("header_id"),
        ),
        source_file,
    )


def _pokemon_link(value: dict[str, Any], source_file: str) -> str:
    return pokemon_markdown_link(
        value.get("id", value.get("slug", value["name"])),
        value["name"],
        value.get("slug"),
        source_file,
    )


def _trainer_link(value: dict[str, Any], source_file: str) -> str:
    label = " ".join(
        part for part in (value.get("class_name"), value.get("name")) if part
    )
    return ROUTES.markdown_link(
        entity_reference(
            "trainer",
            value["trainer_id"],
            label,
            value.get("trainer_id"),
        ),
        source_file,
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


def _shop_price(shop: dict[str, Any]) -> str:
    if shop["price"] is None:
        return "—"
    if shop["currency"] == "money":
        return f"₽{shop['price']:,}"
    return f"{shop['price']:,} {shop['currency'].upper()}"


def _availability(badges: int | None) -> str:
    if badges is None:
        return "Always"
    if badges == 0:
        return "Start"
    return f"{badges} badge" if badges == 1 else f"{badges} badges"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"items/{record['slug']}/"
    previous_link = None
    if previous is not None:
        label = f"← {previous['name']}"
        href = ROUTES.published_href(
            entity_reference("item", previous["item_id"], label, previous["slug"]),
            source_url,
        )
        previous_link = record_nav_link(
            href, label, "prev", (previous.get("reference") or {}).get("sprite_url")
        )
    following_link = None
    if following is not None:
        label = f"{following['name']} →"
        href = ROUTES.published_href(
            entity_reference("item", following["item_id"], label, following["slug"]),
            source_url,
        )
        following_link = record_nav_link(
            href, label, "next", (following.get("reference") or {}).get("sprite_url")
        )
    lines.extend(record_navigation(previous_link, following_link, "Item navigation"))
