from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

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
    resolved_reference,
)


_SEAL_MART_DAYS = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)


def render_location_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
) -> int:
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
        change = record_comparison(comparison, record["header_id"])
        filename = _filename(record["header_id"])
        _write_text(
            output_root / filename,
            _render_location(
                record,
                change,
                comparison.get("baseline") if comparison else None,
                references,
            ),
        )
        label = record["name"]
        if name_counts[label] > 1:
            label = (
                f"{label} — {record['internal_name']} "
                f"(header {record['header_id']})"
            )
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "location", record["header_id"], label, record["header_id"]
                ),
                "locations/index.md",
            )
        )
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
            add_change_status({
                "id": record["header_id"],
                "label": label,
                "url": filename.removesuffix(".md") + "/",
                "internal_name": record["internal_name"],
                "features": features,
                "search_text": f"{record['name']} {record['internal_name']}".lower(),
            }, change)
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


def _render_location(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
) -> str:
    source_file = f"locations/{_filename(record['header_id'])}"
    lines = [
        f"# {record['name']}",
        "",
        *_location_summary(record),
        *comparison_section(change, baseline_name, source_file, references),
    ]
    if record["encounter_id"] is not None:
        lines.extend(
            [
                "## Wild encounters",
                "",
                ROUTES.markdown_link(
                    entity_reference(
                        "encounter",
                        record["encounter_id"],
                        "View encounter table",
                        record["encounter_id"],
                    ),
                    source_file,
                ),
                "",
            ]
        )
    _append_items(lines, record.get("items", []), source_file, references)
    _append_shops(lines, record.get("shops", []), source_file, references)
    _append_pokemon_gifts(
        lines, record.get("pokemon_gifts", []), source_file, references
    )
    _append_npc_trades(
        lines, record.get("npc_trades", []), source_file, references
    )
    _append_static_encounters(
        lines, record.get("static_encounters", []), source_file, references
    )
    _append_trainers(lines, record["trainers"], source_file)
    _append_warps(lines, record["warps"], source_file)
    _append_connections(lines, record["connections"], source_file)
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


def _append_items(
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
        item_link = _entity_link(
            "item", item["item_id"], item["name"], source_file, references
        )
        lines.append(
            f"| {item['kind'].title()} | {item_link} | {item['item_id']} | "
            f"({item['x']}, {item['z']}) |"
        )
    lines.append("")


def _append_shops(
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
            item_link = _entity_link(
                "item", item["item_id"], item["name"], source_file, references
            )
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
                f"| {item_link} | {item['item_id']} | {price} | "
                f"{availability} |"
            )
        lines.append("")


def _append_trainers(
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
        lines.append(
            f"- {link} ({source})"
        )
        lines.append("")


def _append_pokemon_gifts(
    lines: list[str],
    gifts: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
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
        pokemon = _entity_link(
            "pokemon", gift["species_id"], gift["name"], source_file, references
        )
        held_item = (
            _entity_link(
                "item",
                gift["held_item_id"],
                gift["held_item_name"],
                source_file,
                references,
            )
            if gift["held_item_id"] is not None and gift["held_item_name"]
            else "—"
        )
        kind = "Pokémon" if gift["kind"] == "pokemon" else gift["kind"].title()
        lines.append(
            f"| {pokemon} | {kind} | {gift['level']} | "
            f"{held_item} |"
        )
    lines.append("")


def _append_static_encounters(
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
        pokemon = _entity_link(
            "pokemon",
            encounter["species_id"],
            encounter["name"],
            source_file,
            references,
        )
        lines.append(f"| {pokemon} | {encounter['level']} |")
    lines.append("")


def _append_npc_trades(
    lines: list[str],
    trades: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
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
        requested = _entity_link(
            "pokemon",
            trade["requested_species_id"],
            trade["requested_species_name"],
            source_file,
            references,
        )
        offered = _entity_link(
            "pokemon",
            trade["offered_species_id"],
            trade["offered_species_name"],
            source_file,
            references,
        )
        held_item = (
            _entity_link(
                "item",
                trade["held_item_id"],
                trade["held_item_name"],
                source_file,
                references,
            )
            if trade["held_item_id"] is not None and trade["held_item_name"]
            else "—"
        )
        lines.append(
            f"| {requested} | {offered} | {trade['nickname']} | "
            f"{trade['nature']} | {held_item} | {ivs} |"
        )
        lines.append("")
        lines.append(
            f"OT: {trade['ot_name']} (ID {trade['ot_id']:05}), "
            f"{trade['ot_gender'].lower()}, {trade['language']}."
        )
    lines.append("")


def _append_warps(
    lines: list[str], warps: list[dict[str, Any]], source_file: str
) -> None:
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
            destination = ROUTES.markdown_link(
                entity_reference(
                    "location",
                    warp["destination_header_id"],
                    warp["destination_name"],
                    warp.get("destination_header_id"),
                ),
                source_file,
            )
            destination += f" (`{warp['destination_internal_name']}`)"
            destination_warp = str(warp["destination_warp_id"])
            if not warp["destination_warp_exists"]:
                destination_warp += " (missing target record)"
        lines.append(
            f"| {warp['index']} | ({warp['x']}, {warp['z']}) | "
            f"{destination} | {destination_warp} |"
        )
    lines.append("")


def _append_connections(
    lines: list[str], connections: list[dict[str, Any]], source_file: str
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
                connection["destination_name"],
                connection.get("destination_header_id"),
            ),
            source_file,
        )
        lines.append(
            f"- {directions}: {destination} "
            f"(`{connection['destination_internal_name']}`)"
        )
    lines.append("")


def _entity_link(
    kind: str,
    identifier: int | str,
    label: str,
    source_file: str,
    references: ReferenceIndex | None,
) -> str:
    reference = resolved_reference(
        kind, identifier, label, index=references
    )
    return ROUTES.markdown_link(reference, source_file)


def _filename(header_id: int) -> str:
    return f"header-{header_id:03}.md"


