from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.components import display_name


def render_item_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    filenames = {"index.md", *(f"{record['slug']}.md" for record in records)}
    prune_catalog_pages(output_root, filenames)
    fallback_links = []
    catalog_records = []
    for index, record in enumerate(records):
        filename = f"{record['slug']}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        write_text(output_root / filename, _render_record(record, previous, following))
        fallback_links.append(f"- [#{record['item_id']:03} {record['name']}]({filename})")
        features = _features(record)
        locations = list(
            dict.fromkeys(
                reference["name"]
                for field in ("locations", "shops", "gifts", "trades")
                for reference in record[field]
            )
        )
        catalog_records.append(
            {
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
                "search_text": " ".join((record["name"], *features, *locations)).lower(),
            }
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
    return len(records)


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> str:
    price = f"₽{record['price']:,}" if record["price"] else "Not sold"
    lines = [
        f"# {record['name']}",
        "",
        "| Item ID | Pocket | Price | Selectable | Can be discarded |",
        "| ------: | ------ | -----: | ---------- | ---------------- |",
        (
            f"| {record['item_id']} | {display_name(record['pocket']['name'])} | "
            f"{price} | {_yes_no(record['selectable'])} | "
            f"{_yes_no(not record['prevent_toss'])} |"
        ),
        "",
        "## Mechanics",
        "",
        f"- Field use: {display_name(record['field_use']['name'])}",
        f"- Held effect ID: {record['hold_effect_id']}",
        f"- Held effect parameter: {record['hold_effect_parameter']}",
        f"- Battle use function ID: {record['battle_use_function_id']}",
        f"- Battle pocket mask: `{record['battle_pocket_mask']:#04x}`",
    ]
    if record["fling_power"]:
        lines.extend(
            [
                f"- Fling power: {record['fling_power']}",
                f"- Fling effect ID: {record['fling_effect_id']}",
            ]
        )
    if record["natural_gift_power"]:
        gift_type = record["natural_gift_type"]
        lines.append(
            f"- Natural Gift: {record['natural_gift_power']} power, "
            f"{gift_type['name']} type"
        )
    party_effects = _party_effects(record)
    if party_effects:
        lines.extend(["- Party-use effects: " + ", ".join(party_effects)])
    lines.append("")

    _append_locations(lines, record)
    _append_shops(lines, record["shops"])
    _append_pokemon(lines, record)
    _append_trainers(lines, record)
    _append_gifts_and_trades(lines, record)
    _append_evolutions(lines, record["evolutions"])
    lines.extend(
        [
            "## Source",
            "",
            (
                "The name, item-data member mapping, mechanics, and references are "
                "extracted from the ROM. Numeric effect IDs are retained when their "
                "behavior is implemented by game code rather than the item record."
            ),
            "",
            _page_navigation(previous, following),
            "",
        ]
    )
    return "\n".join(lines)


def _append_locations(lines: list[str], record: dict[str, Any]) -> None:
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
                    f"| [{value['name']}](../locations/header-{value['header_id']:03}.md) "
                    f"| {value['kind'].title()} | ({value['x']}, {value['z']}) |"
                )
                for value in record["locations"]
            ],
            "",
        ]
    )


def _append_shops(lines: list[str], shops: list[dict[str, Any]]) -> None:
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
                    f"| [{shop['name']}](../locations/header-{shop['header_id']:03}.md) "
                    f"| {shop['kind'].title()} | {_shop_price(shop)} | "
                    f"{_availability(shop['required_badges'])} |"
                )
                for shop in shops
            ],
            "",
        ]
    )


def _append_pokemon(lines: list[str], record: dict[str, Any]) -> None:
    lines.extend(["## Wild held by", ""])
    if not record["wild_held_by"]:
        lines.extend(["No wild held-item assignments.", ""])
        return
    lines.extend(
        [
            "| Pokémon | Slot |",
            "| ------- | ---- |",
            *[
                f"| [{value['name']}](../pokemon/{value['slug']}.md) | {value['rarity'].title()} |"
                for value in record["wild_held_by"]
            ],
            "",
        ]
    )


def _append_trainers(lines: list[str], record: dict[str, Any]) -> None:
    lines.extend(["## Trainer references", ""])
    values = [
        (value, f"Held by {value['pokemon']['name']}")
        for value in record["trainer_held_by"]
    ] + [(value, "Battle reward") for value in record["trainer_rewards"]]
    if not values:
        lines.extend(["No trainer references.", ""])
        return
    lines.extend(
        [
            "| Trainer | Reference |",
            "| ------- | --------- |",
            *[
                (
                    f"| [{value['class_name']} {value['name']}]"
                    f"(../trainers/trainer-{value['trainer_id']:04}.md) | {kind} |"
                )
                for value, kind in values
            ],
            "",
        ]
    )


def _append_gifts_and_trades(lines: list[str], record: dict[str, Any]) -> None:
    lines.extend(["## Gifts and trades", ""])
    values = [
        (value, "Gift", value["pokemon"]["name"]) for value in record["gifts"]
    ] + [(value, "Trade", value["pokemon"]["name"]) for value in record["trades"]]
    if not values:
        lines.extend(["No gift or trade references.", ""])
        return
    lines.extend(
        [
            "| Location | Kind | Pokémon |",
            "| -------- | ---- | ------- |",
            *[
                (
                    f"| [{value['name']}](../locations/header-{value['header_id']:03}.md) "
                    f"| {kind} | {pokemon} |"
                )
                for value, kind, pokemon in values
            ],
            "",
        ]
    )


def _append_evolutions(lines: list[str], evolutions: list[dict[str, Any]]) -> None:
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
                    f"| [{value['source']['name']}]"
                    f"(../pokemon/{value['source']['slug']}.md) | "
                    f"[{value['target']['name']}]"
                    f"(../pokemon/{value['target']['slug']}.md) | "
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


def _features(record: dict[str, Any]) -> list[str]:
    values = []
    for field, label in (
        ("locations", "overworld"),
        ("shops", "shop"),
        ("wild_held_by", "wild-held"),
        ("trainer_held_by", "trainer-held"),
        ("trainer_rewards", "trainer-reward"),
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


def _page_navigation(
    previous: dict[str, Any] | None, following: dict[str, Any] | None
) -> str:
    links = []
    if previous is not None:
        links.append(f"[← {previous['name']}]({previous['slug']}.md)")
    links.append("[All items](index.md)")
    if following is not None:
        links.append(f"[{following['name']} →]({following['slug']}.md)")
    return " · ".join(links)
