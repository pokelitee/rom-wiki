from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from romwiki.pipeline.semantics.location_sections import location_reference_label
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

LOCATION_CATALOG_DESCRIPTION = (
    "Map headers, items, shops, trades, connections, encounters, and trainers "
    "extracted from the ROM."
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
            (
                "These rows are item-event records present in the ROM. A record can "
                "still be unreachable or intentionally disabled by a hack's map or "
                "scripts; suspicious raw coordinates are called out below."
            ),
            (
                "This section covers item balls and hidden field items, not NPC "
                "gifts, bundled rewards, or other script-awarded items."
            ),
            "",
            "| Kind | Item | ID | Position |",
            "| ---- | ---- | -: | -------- |",
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
    suspicious = [item for item in items if _is_suspicious_item_event(item)]
    if suspicious:
        labels = ", ".join(
            f"{item['name']} (event {item['event_index']})" for item in suspicious
        )
        lines.extend(
            [
                '!!! warning "Suspicious ROM item records"',
                "    The following item-event records use an origin coordinate or "
                "an unnamed item slot and may be stale, disabled, or otherwise "
                f"unreachable: {labels}.",
                "",
            ]
        )


def item_event_coverage_notice(records: list[dict[str, Any]]) -> str:
    suspicious_count = sum(
        1
        for record in records
        for item in record.get("items", [])
        if _is_suspicious_item_event(item)
    )
    if not suspicious_count:
        return ""
    noun = "record" if suspicious_count == 1 else "records"
    return (
        "\n\n"
        '!!! warning "Unresolved item events"\n'
        f"    {suspicious_count} ROM item-event {noun} use an origin coordinate "
        "or unnamed item slot. They remain visible on the affected location "
        "pages, but are not asserted to be reachable pickups."
    )


def _is_suspicious_item_event(item: Mapping[str, Any]) -> bool:
    return (item.get("x"), item.get("z")) == (0, 0) or item.get("name") in {
        "???",
        "—",
    }


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
                "| Item | ID | Price | Availability |",
                "| ---- | -: | ----: | ------------ |",
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
    rows = []
    for trainer in trainers:
        label = " ".join(
            value for value in (trainer["class_name"], trainer["name"]) if value
        )
        source = display_name(trainer["source"])
        link = ROUTES.markdown_link(
            entity_reference(
                "trainer",
                trainer["trainer_id"],
                label,
                trainer.get("trainer_id"),
            ),
            source_file,
        )
        rows.append(f"| {link} | `trainer-{trainer['trainer_id']:04}` | {source} |")
    lines.extend(
        markdown_section(
            "Trainers",
            markdown_table(
                [
                    "| Trainer | ID | Trigger |",
                    "| ------- | -- | ------- |",
                ],
                rows,
            ),
        )
    )


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
                "| Warp | Position | To | Section | Map ID | Arrival |",
                "| ---: | -------- | -- | ------- | ------ | ------- |",
            ],
        )
    )
    for warp in warps:
        if warp["dynamic"]:
            destination = "Dynamic destination"
            destination_section = "—"
            destination_id = "—"
            destination_warp = "—"
        else:
            destination_id = f"`header-{warp['destination_header_id']:03}`"
            destination_section = warp.get("destination_section_name") or "—"
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
            f"{destination} | {destination_section} | {destination_id} | "
            f"{destination_warp} |"
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
    rows = []
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
        rows.append(
            f"| {directions.title()} | {destination} | "
            f"`{connection['destination_internal_name']}` |"
        )
    lines.extend(
        markdown_section(
            "Outdoor connections",
            markdown_table(
                [
                    "| Direction | To | Map ID |",
                    "| --------- | -- | ------ |",
                ],
                rows,
            ),
        )
    )


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
