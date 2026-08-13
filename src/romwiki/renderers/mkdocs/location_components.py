from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from romwiki.pipeline.location_sections import location_reference_label
from romwiki.renderers.mkdocs.components import (
    badge_requirement,
    display_name,
    escape_table_cell,
    markdown_section,
    markdown_table,
    reference_sprite_cell,
    reference_type_cell,
    resolved_location_label,
    shop_price,
    sprite_with_link,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_markdown_link,
    entity_reference,
)


def location_filename(header_id: int) -> str:
    return f"header-{header_id:03}.md"


def location_label(record: dict[str, Any]) -> str:
    return location_reference_label(record)


def section_name_provenance_facts(
    record: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    section_name = record.get("section_name")
    source = record.get("section_name_source")
    if not section_name or not source:
        return ()
    if source.get("source") == "rom":
        source_label = f"ROM `{source['field']}` field"
    else:
        source_label = f"profile `{source['profile']}`, key `{source['key']}`"
    return (
        ("Section name", escape_table_cell(section_name)),
        ("Section name source", source_label),
    )


def append_items(
    lines: list[str],
    items: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not items:
        return
    lines.extend(
        [
            "## Item pickups",
            "",
            "| Kind | Item | Item ID | Position |",
            "| ---- | ---- | ------: | -------- |",
        ]
    )
    for item in items:
        item_link = entity_link(
            "item", item["item_id"], item["name"], source_file, references
        )
        lines.append(
            f"| {item['kind'].title()} | "
            f"{sprite_with_link(entity_sprite('item', item['item_id'], references), item_link)} "
            f"| {item['item_id']} | ({item['x']}, {item['z']}) |"
        )
    lines.append("")


def append_shops(
    lines: list[str],
    shops: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not shops:
        return
    lines.extend(["## Shops", ""])
    kind_counts = Counter(shop["kind"] for shop in shops)
    kind_indices: Counter[str] = Counter()
    for shop in shops:
        kind_indices[shop["kind"]] += 1
        label = shop.get("name") or {
            "common": "Common Poké Mart",
            "specialty": "Specialty shop",
            "tm": "TM shop",
            "decoration": "Decoration shop",
            "seal": "Seal shop",
            "frontier": "Battle Frontier shop",
        }.get(shop["kind"], f"{shop['kind'].title()} shop")
        if shop.get("dynamic"):
            lines.extend(
                [
                    f"### {label}",
                    "",
                    shop.get("availability")
                    or "Stock changes with badge progression and is selected "
                    "dynamically by the game.",
                    "",
                ]
            )
            continue
        if shop.get("schedule"):
            label += f" — {shop['schedule']}"
        elif not shop.get("name") and kind_counts[shop["kind"]] > 1:
            label += f" {kind_indices[shop['kind']]}"
        lines.extend([f"### {label}", ""])
        if shop.get("availability"):
            lines.extend([f"Availability: {shop['availability']}", ""])
        lines.extend(
            [
                "| Item | Item ID | Price | Availability |",
                "| ---- | ------: | ----: | ------------ |",
            ]
        )
        currency = shop.get("currency", "money")
        for item in shop["items"]:
            item_link = entity_link(
                "item", item["item_id"], item["name"], source_file, references
            )
            price = shop_price(item["price"], currency)
            if item.get("availability"):
                availability = item["availability"]
            elif shop.get("is_main_game") is not None:
                availability = "Main game" if shop["is_main_game"] else "Post-game"
            else:
                availability = badge_requirement(item["required_badges"])
            lines.append(
                f"| {sprite_with_link(entity_sprite('item', item['item_id'], references), item_link)} "
                f"| {item['item_id']} | {price} | {availability} |"
            )
        lines.append("")


def append_trainers(
    lines: list[str], trainers: list[dict[str, Any]], source_file: str
) -> None:
    if not trainers:
        return
    lines.extend(["## Trainers", ""])
    for trainer in trainers:
        label = " ".join(
            value for value in (trainer["class_name"], trainer["name"]) if value
        )
        source = (
            "overworld object"
            if trainer["source"] == "overworld-object"
            else "map script"
        )
        link = ROUTES.markdown_link(
            entity_reference(
                "trainer",
                trainer["trainer_id"],
                label,
                trainer.get("trainer_id"),
            ),
            source_file,
        )
        lines.append(f"- {link} ({source})")
    lines.append("")


def append_static_encounters(
    lines: list[str],
    encounters: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not encounters:
        return
    lines.extend(
        [
            "## Static encounters",
            "",
            "These are literal wild-battle commands in this map's scripts; "
            "conditional branches may make encounters unavailable.",
            "",
        ]
    )
    rendered_outcomes = set()
    rows = []
    for encounter in encounters:
        outcome = (encounter["name"], encounter["level"], encounter["command"])
        if outcome in rendered_outcomes:
            continue
        rendered_outcomes.add(outcome)
        pokemon = entity_link(
            "pokemon",
            encounter["species_id"],
            encounter["name"],
            source_file,
            references,
        )
        sprite = entity_sprite("pokemon", encounter["species_id"], references)
        rows.append(
            f"| {sprite_with_link(sprite, pokemon)} | "
            f"{reference_type_cell('pokemon', encounter['species_id'], references)} | "
            f"{encounter['level']} | `{encounter['command']}` |"
        )
    lines.extend(
        markdown_table(
            [
                "| Pokémon | Type | Level | Command |",
                "| ------- | ---- | ----: | ------- |",
            ],
            rows,
        )
    )


def append_npc_trades(
    lines: list[str],
    trades: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not trades:
        return
    show_nature = any(trade.get("nature") for trade in trades)
    show_versions = any(trade.get("versions") for trade in trades)
    headers = ["Give", "Receive", "Nickname"]
    if show_versions:
        headers.append("Versions")
    if show_nature:
        headers.append("Nature")
    headers.extend(["Held item", "IVs", "OT"])
    lines.extend(
        [
            "## In-game trades",
            "",
            "The received Pokémon keeps the level of the Pokémon you trade away.",
            "",
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("----" for _ in headers) + " |",
        ]
    )
    stat_names = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")
    for trade in trades:
        ivs = " / ".join(
            f"{name} {value}"
            for name, value in zip(stat_names, trade["ivs"], strict=True)
        )
        requested = entity_link(
            "pokemon",
            trade["requested_species_id"],
            trade["requested_species_name"],
            source_file,
            references,
        )
        offered = entity_link(
            "pokemon",
            trade["offered_species_id"],
            trade["offered_species_name"],
            source_file,
            references,
        )
        held_item = (
            entity_link(
                "item",
                trade["held_item_id"],
                trade["held_item_name"],
                source_file,
                references,
            )
            if trade["held_item_id"] is not None and trade["held_item_name"]
            else "—"
        )
        ot_details = [f"ID {trade['ot_id']:05}"]
        if trade.get("ot_gender"):
            ot_details.append(trade["ot_gender"].lower())
        if trade.get("language"):
            ot_details.append(trade["language"])
        ot = f"{escape_table_cell(trade['ot_name'])} ({', '.join(ot_details)})"
        requested_sprite = entity_sprite(
            "pokemon", trade["requested_species_id"], references
        )
        offered_sprite = entity_sprite(
            "pokemon", trade["offered_species_id"], references
        )
        held_item_sprite = (
            entity_sprite("item", trade["held_item_id"], references)
            if trade["held_item_id"] is not None and trade["held_item_name"]
            else "—"
        )
        held_item_cell = (
            sprite_with_link(held_item_sprite, held_item)
            if trade["held_item_id"] is not None and trade["held_item_name"]
            else "—"
        )
        cells = [
            sprite_with_link(requested_sprite, requested),
            sprite_with_link(offered_sprite, offered),
            escape_table_cell(trade["nickname"]),
        ]
        if show_versions:
            cells.append(
                " / ".join(display_name(version) for version in trade["versions"])
            )
        if show_nature:
            cells.append(trade.get("nature") or "—")
        cells.extend([held_item_cell, ivs, ot])
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")


def append_warps(
    lines: list[str],
    warps: list[dict[str, Any]],
    source_file: str,
    location_labels: Mapping[int, str] | None = None,
) -> None:
    if not warps:
        return
    lines.extend(
        markdown_section(
            "Warps",
            [
                *(
                    [
                        "Dynamic destination means the ROM does not store one fixed "
                        "destination header or destination warp for that row. The em "
                        "dashes are explicit unavailable values, not missing cells.",
                        "",
                    ]
                    if any(warp["dynamic"] for warp in warps)
                    else []
                ),
                "| Warp | Position | Destination | Destination map header | Destination warp |",
                "| ---: | -------- | ----------- | ---------------------- | ---------------: |",
            ],
        )
    )
    for warp in warps:
        if warp["dynamic"]:
            destination = "Dynamic destination"
            destination_id = "—"
            destination_warp = "—"
        else:
            destination_id = f"`header-{warp['destination_header_id']:03}`"
            destination = ROUTES.markdown_link(
                entity_reference(
                    "location",
                    warp["destination_header_id"],
                    resolved_location_label(
                        warp["destination_header_id"],
                        warp["destination_name"],
                        location_labels,
                    ),
                    warp.get("destination_header_id"),
                ),
                source_file,
            )
            destination_warp = (
                "Coordinate-based"
                if warp["destination_warp_id"] is None
                else str(warp["destination_warp_id"])
            )
            if warp["destination_warp_exists"] is False:
                destination_warp += " (one-way or special landing)"
        lines.append(
            f"| {warp['index']} | ({warp['x']}, {warp['z']}) | "
            f"{destination} | {destination_id} | {destination_warp} |"
        )
    lines.append("")


def append_connections(
    lines: list[str],
    connections: list[dict[str, Any]],
    source_file: str,
    location_labels: Mapping[int, str] | None = None,
) -> None:
    if not connections:
        return
    lines.extend(["## Outdoor connections", ""])
    for connection in connections:
        directions = ", ".join(connection["directions"])
        destination = ROUTES.markdown_link(
            entity_reference(
                "location",
                connection["destination_header_id"],
                resolved_location_label(
                    connection["destination_header_id"],
                    connection["destination_name"],
                    location_labels,
                ),
                connection.get("destination_header_id"),
            ),
            source_file,
        )
        lines.append(
            f"- {directions}: {destination} "
            f"(`{connection['destination_internal_name']}`)"
        )
    lines.append("")


def entity_link(
    kind: str,
    identifier: int | str,
    label: str,
    source_file: str,
    references: ReferenceIndex | None,
) -> str:
    return entity_markdown_link(kind, identifier, label, source_file, index=references)


def entity_sprite(
    kind: str,
    identifier: int | str | None,
    references: ReferenceIndex | None,
) -> str:
    return reference_sprite_cell(kind, identifier, references)
