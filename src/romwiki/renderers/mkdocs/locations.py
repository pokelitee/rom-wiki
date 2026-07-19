from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import catalog_index, write_catalog


_SEAL_MART_DAYS = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)


def render_location_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    name_counts = Counter(record["name"] for record in records)
    fallback_links = []
    catalog_records = []
    for record in sorted(
        records,
        key=lambda item: (
            item["name"],
            item["internal_name"],
            item["header_id"],
        ),
    ):
        filename = _filename(record["header_id"])
        _write_text(output_root / filename, _render_location(record))
        label = record["name"]
        if name_counts[label] > 1:
            label = (
                f"{label} — {record['internal_name']} "
                f"(header {record['header_id']})"
            )
        fallback_links.append(f"- [{label}](./{filename})")
        features = [
            feature
            for feature, active in (
                ("encounters", record["encounter_id"] is not None),
                ("items", bool(record.get("items"))),
                ("shops", bool(record.get("shops"))),
                ("gifts", bool(record.get("pokemon_gifts"))),
                ("trades", bool(record.get("npc_trades"))),
                ("static encounters", bool(record.get("static_encounters"))),
                ("trainers", bool(record.get("trainers"))),
                ("warps", bool(record.get("warps"))),
                ("connections", bool(record.get("connections"))),
            )
            if active
        ]
        catalog_records.append(
            {
                "id": record["header_id"],
                "label": record["name"],
                "url": filename.removesuffix(".md") + "/",
                "internal_name": record["internal_name"],
                "features": features,
                "search_text": f"{record['name']} {record['internal_name']}".lower(),
            }
        )
    write_catalog(output_root, "locations", catalog_records)
    _write_text(
        output_root / "index.md",
        catalog_index(
            "Locations",
            "Map headers, items, shops, trades, connections, encounters, and trainers extracted from the ROM.",
            "locations",
            fallback_links,
        ),
    )
    return len(records)


def _render_location(record: dict[str, Any]) -> str:
    lines = [
        f"# {record['name']}",
        "",
        *_location_summary(record),
    ]
    if record["encounter_id"] is not None:
        lines.extend(
            [
                "## Wild encounters",
                "",
                "[View encounter table]"
                f"(../encounters/area-{record['encounter_id']:03}.md)",
                "",
            ]
        )
    _append_items(lines, record.get("items", []))
    _append_shops(lines, record.get("shops", []))
    _append_pokemon_gifts(lines, record.get("pokemon_gifts", []))
    _append_npc_trades(lines, record.get("npc_trades", []))
    _append_static_encounters(lines, record.get("static_encounters", []))
    _append_trainers(lines, record["trainers"])
    _append_warps(lines, record["warps"])
    _append_connections(lines, record["connections"])
    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Map identifiers and provenance</summary>",
            "",
            f"- Internal map: `{record['internal_name']}`",
            f"- Header ID: `{record['header_id']}`",
            f"- Matrix ID: `{record['matrix_id']}`",
            "",
            "Source: exact map header, event, script, item-data, and map-matrix "
            "records from the ROM.",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def _location_summary(record: dict[str, Any]) -> list[str]:
    facts = (
        ("Items", len(record.get("items", []))),
        ("Shops", len(record.get("shops", []))),
        ("Trainers", len(record.get("trainers", []))),
        ("Warps", len(record.get("warps", []))),
        ("Connections", len(record.get("connections", []))),
    )
    lines = ['<section class="rw-location-summary">', '<dl class="rw-summary__facts">']
    for label, value in facts:
        lines.append(f"<div><dt>{label}</dt><dd>{value}</dd></div>")
    lines.extend(["</dl>", "</section>", ""])
    return lines


def _append_items(lines: list[str], items: list[dict[str, Any]]) -> None:
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
        lines.append(
            f"| {item['kind'].title()} | {item['name']} | {item['item_id']} | "
            f"({item['x']}, {item['z']}) |"
        )
    lines.append("")


def _append_shops(lines: list[str], shops: list[dict[str, Any]]) -> None:
    if not shops:
        return
    lines.extend(["## Shops", ""])
    kind_counts = Counter(shop["kind"] for shop in shops)
    kind_indices: Counter[str] = Counter()
    for shop in shops:
        kind_indices[shop["kind"]] += 1
        label = {
            "common": "Common Poké Mart",
            "specialty": "Specialty shop",
            "decoration": "Decoration shop",
            "seal": "Seal shop",
            "frontier": "Battle Frontier shop",
        }.get(shop["kind"], f"{shop['kind'].title()} shop")
        if shop["kind"] == "seal" and shop["inventory_id"] < len(_SEAL_MART_DAYS):
            label += f" — {_SEAL_MART_DAYS[shop['inventory_id']]}"
        elif kind_counts[shop["kind"]] > 1:
            label += f" {kind_indices[shop['kind']]}"
        lines.extend(
            [
                f"### {label}",
                "",
                "| Item | Item ID | Price | Available after |",
                "| ---- | ------: | ----: | --------------- |",
            ]
        )
        currency = shop.get("currency", "money")
        for item in shop["items"]:
            if item["price"] is None:
                price = "—"
            elif currency == "money":
                price = f"₽{item['price']:,}"
            else:
                price = f"{item['price']:,} {currency.upper()}"
            badges = item["required_badges"]
            if badges is None:
                availability = "Always"
            elif badges == 0:
                availability = "Start"
            elif badges == 1:
                availability = "1 badge"
            else:
                availability = f"{badges} badges"
            lines.append(
                f"| {item['name']} | {item['item_id']} | {price} | "
                f"{availability} |"
            )
        lines.append("")


def _append_trainers(lines: list[str], trainers: list[dict[str, Any]]) -> None:
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
        lines.append(
            f"- [{label}](../trainers/trainer-{trainer['trainer_id']:04}.md) "
            f"({source})"
        )
        lines.append("")


def _append_pokemon_gifts(
    lines: list[str], gifts: list[dict[str, Any]]
) -> None:
    if not gifts:
        return
    lines.extend(
        [
            "## Gift Pokémon",
            "",
            "These are literal gift outcomes in this map's scripts; conditional "
            "branches may be mutually exclusive.",
            "",
            "| Pokémon | Kind | Level | Held item |",
            "| ------- | ---- | ----: | --------- |",
        ]
    )
    for gift in gifts:
        held_item = gift["held_item_name"] or "—"
        kind = "Pokémon" if gift["kind"] == "pokemon" else gift["kind"].title()
        lines.append(
            f"| {gift['name']} | {kind} | {gift['level']} | "
            f"{held_item} |"
        )
    lines.append("")


def _append_static_encounters(
    lines: list[str], encounters: list[dict[str, Any]]
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
            "| Pokémon | Level |",
            "| ------- | ----: |",
        ]
    )
    rendered_outcomes = set()
    for encounter in encounters:
        outcome = (encounter["name"], encounter["level"])
        if outcome in rendered_outcomes:
            continue
        rendered_outcomes.add(outcome)
        lines.append(f"| {encounter['name']} | {encounter['level']} |")
    lines.append("")


def _append_npc_trades(
    lines: list[str], trades: list[dict[str, Any]]
) -> None:
    if not trades:
        return
    lines.extend(
        [
            "## In-game trades",
            "",
            "The received Pokémon keeps the level of the Pokémon you trade away.",
            "",
            "| Give | Receive | Nickname | Nature | Held item | IVs |",
            "| ---- | ------- | -------- | ------ | --------- | --- |",
        ]
    )
    stat_names = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")
    for trade in trades:
        ivs = " / ".join(
            f"{name} {value}" for name, value in zip(stat_names, trade["ivs"])
        )
        held_item = trade["held_item_name"] or "—"
        lines.append(
            f"| {trade['requested_species_name']} | "
            f"{trade['offered_species_name']} | {trade['nickname']} | "
            f"{trade['nature']} | {held_item} | {ivs} |"
        )
        lines.append("")
        lines.append(
            f"OT: {trade['ot_name']} (ID {trade['ot_id']:05}), "
            f"{trade['ot_gender'].lower()}, {trade['language']}."
        )
    lines.append("")


def _append_warps(lines: list[str], warps: list[dict[str, Any]]) -> None:
    if not warps:
        return
    lines.extend(
        [
            "## Warps",
            "",
            "| Warp | Position | Destination | Destination warp |",
            "| ---: | -------- | ----------- | ---------------: |",
        ]
    )
    for warp in warps:
        if warp["dynamic"]:
            destination = "Dynamic destination"
            destination_warp = "—"
        else:
            destination = (
                f"[{warp['destination_name']}]"
                f"(./{_filename(warp['destination_header_id'])}) "
                f"(`{warp['destination_internal_name']}`)"
            )
            destination_warp = str(warp["destination_warp_id"])
            if not warp["destination_warp_exists"]:
                destination_warp += " (missing target record)"
        lines.append(
            f"| {warp['index']} | ({warp['x']}, {warp['z']}) | "
            f"{destination} | {destination_warp} |"
        )
    lines.append("")


def _append_connections(
    lines: list[str], connections: list[dict[str, Any]]
) -> None:
    if not connections:
        return
    lines.extend(["## Outdoor connections", ""])
    for connection in connections:
        directions = ", ".join(connection["directions"])
        lines.append(
            f"- {directions}: "
            f"[{connection['destination_name']}]"
            f"(./{_filename(connection['destination_header_id'])}) "
            f"(`{connection['destination_internal_name']}`)"
        )
    lines.append("")


def _filename(header_id: int) -> str:
    return f"header-{header_id:03}.md"


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
