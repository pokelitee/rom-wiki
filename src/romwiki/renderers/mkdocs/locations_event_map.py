from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from romwiki.pipeline.location_sections import location_reference_label
from romwiki.pipeline.relationships import RelationshipIndex
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
    escape_table_cell,
    pokemon_table,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    reference_sprite_cell,
    reference_type_cell,
    resolved_location_label,
    shop_price,
    sprite_with_link,
    summary_section,
    summary_section_link,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_markdown_link,
    entity_reference,
    escape_markdown,
)


def render_event_map_location_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                _filename(record["header_id"])
                for record in records
                if only_pages is None
                or _filename(record["header_id"]).removesuffix(".md") in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    sorted_records = sorted(
        records,
        key=lambda item: (
            item["name"],
            item.get("section_name") or "",
            item["internal_name"],
            item["header_id"],
        ),
    )
    for index, record in enumerate(sorted_records):
        change = record_comparison(comparison, record["header_id"])
        filename = _filename(record["header_id"])
        previous = sorted_records[index - 1] if index else None
        following = (
            sorted_records[index + 1] if index + 1 < len(sorted_records) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_location(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    previous,
                    following,
                    relationships.location_labels if relationships else None,
                ),
            )
            page_count += 1
        route_id = filename.removesuffix(".md")
        fallback_label = f"{_location_label(record)} — {route_id}"
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "location",
                    record["header_id"],
                    fallback_label,
                    record["header_id"],
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
                ("roaming", bool(record.get("roaming_activations"))),
                ("honey tree", bool(record.get("honey_tree"))),
                ("daily rotation", bool(record.get("daily_encounter_pool"))),
                ("game corner", bool(record.get("game_corner_prizes"))),
                ("trainers", bool(record.get("trainers"))),
                ("warps", bool(record.get("warps"))),
                ("connections", bool(record.get("connections"))),
            )
            if active
        ]
        catalog_records.append(
            add_change_status(
                {
                    "id": record["header_id"],
                    "route_id": route_id,
                    "label": record["name"],
                    "location_name": record["name"],
                    "section_name": record.get("section_name"),
                    "url": route_id + "/",
                    "internal_name": record["internal_name"],
                    "features": features,
                    "search_text": (
                        f"{record['name']} {record.get('section_name') or ''} "
                        f"{record['internal_name']} {route_id}".lower()
                    ),
                },
                change,
            )
        )
    write_catalog(output_root, "locations", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Locations",
            "Map headers, items, shops, trades, connections, encounters, and trainers extracted from the ROM.",
            "locations",
            fallback_links,
        ),
    )
    return page_count


def _render_location(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    location_labels: Mapping[int, str] | None = None,
) -> str:
    source_file = f"locations/{_filename(record['header_id'])}"
    lines = [
        f"# {_location_label(record)}",
        "",
        *_location_summary(record),
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
    _append_npc_trades(lines, record.get("npc_trades", []), source_file, references)
    _append_static_encounters(
        lines, record.get("static_encounters", []), source_file, references
    )
    _append_roaming_activations(
        lines, record.get("roaming_activations", []), source_file, references
    )
    _append_honey_tree(lines, record.get("honey_tree"), source_file, references)
    _append_daily_encounter_pool(
        lines, record.get("daily_encounter_pool"), source_file, references
    )
    _append_game_corner_prizes(
        lines, record.get("game_corner_prizes", []), source_file, references
    )
    _append_trainers(lines, record["trainers"], source_file)
    _append_warps(lines, record["warps"], source_file, location_labels)
    _append_connections(lines, record["connections"], source_file, location_labels)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(
        provenance_section(
            [
                *provenance_fact_table(
                    (
                        ("Internal map", f"`{record['internal_name']}`"),
                        *(_section_name_provenance_facts(record)),
                        ("Map header", f"`header-{record['header_id']:03}`"),
                        ("Location-name index", f"`{record['location_name_id']}`"),
                        ("Matrix ID", f"`{record['matrix_id']}`"),
                        (
                            "Event file ID",
                            f"`{record['event_file_id']}`"
                            if record["event_file_id"] is not None
                            else "—",
                        ),
                        ("Area data ID", f"`{record['area_data_id']}`"),
                        ("Level script ID", f"`{record['level_script_id']}`"),
                        ("Text archive ID", f"`{record['text_archive_id']}`"),
                        (
                            "Music ID",
                            f"day `{record['day_music_id']}`, "
                            f"night `{record['night_music_id']}`",
                        ),
                        ("Weather ID", f"`{record['weather_id']}`"),
                        ("Camera ID", f"`{record['camera_id']}`"),
                        ("Map flags", f"`0x{record['map_flags']:04X}`"),
                    )
                ),
                "Source: exact map header, event, script, item-data, and map-matrix "
                "records from the ROM.",
                *(
                    (
                        f"Trade `{trade['trade_id']}` "
                        f"({escape_markdown(trade['nickname'])}) "
                        f"personality value: `0x{trade['personality']:08X}`, "
                        f"undecoded record values: `{trade['unknown_values']}`."
                    )
                    for trade in record.get("npc_trades", [])
                ),
                *(
                    (
                        "Undecoded trade record values are raw ROM data at "
                        "offsets whose purpose isn't fully understood; kept "
                        "here so hack edits to those bytes stay auditable.",
                    )
                    if record.get("npc_trades")
                    else ()
                ),
            ]
        )
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "location",
            f"locations/{_filename(record['header_id']).removesuffix('.md')}/",
            previous,
            following,
            aria_label="Location navigation",
            identity=lambda value: value["header_id"],
            route_key=lambda value: value["header_id"],
            label=_location_label,
        )
    )


def _location_summary(record: dict[str, Any]) -> list[str]:
    has_encounters = record["encounter_id"] is not None
    has_honey_tree = bool(record.get("honey_tree"))
    daily_pool = record.get("daily_encounter_pool")
    daily_pool_anchor = (
        "great-marsh-daily-rotation"
        if daily_pool and daily_pool["kind"] == "great_marsh"
        else "trophy-garden-daily-rotation"
    )
    facts: list[tuple[str, int | str, str, bool]] = [
        ("Wild encounters", "Yes", "wild-encounters", has_encounters),
        ("Honey tree", "Yes", "honey-tree", has_honey_tree),
        ("Daily rotation", "Yes", daily_pool_anchor, bool(daily_pool)),
    ]
    for label, key, anchor in (
        ("Item pickups", "items", "item-pickups"),
        ("Shops", "shops", "shops"),
        ("Gift Pokémon", "pokemon_gifts", "gift-pokemon"),
        ("In-game trades", "npc_trades", "in-game-trades"),
        ("Static encounters", "static_encounters", "static-encounters"),
        ("Roaming activations", "roaming_activations", "roaming-activations"),
        ("Game Corner prizes", "game_corner_prizes", "game-corner-prizes"),
        ("Trainers", "trainers", "trainers"),
        ("Warps", "warps", "warps"),
        ("Outdoor connections", "connections", "outdoor-connections"),
    ):
        count = len(record.get(key, []))
        facts.append((label, count, anchor, count > 0))
    fact_lines = [
        f"<div><dt>{label}</dt><dd>{summary_section_link(value, anchor)}</dd></div>"
        for label, value, anchor, populated in facts
        if populated
    ]
    fact_lines.insert(
        0, f"<div><dt>Map header</dt><dd>header-{record['header_id']:03}</dd></div>"
    )
    if record.get("section_name"):
        fact_lines[0:0] = [
            f"<div><dt>Location</dt><dd>{escape_table_cell(record['name'])}</dd></div>",
            f"<div><dt>Section</dt><dd>{escape_table_cell(record['section_name'])}</dd></div>",
        ]
    if not fact_lines:
        fact_lines.append(
            "<div><dt>Notable features</dt>"
            '<dd><span class="rw-summary__empty">None</span></dd></div>'
        )
    return summary_section("rw-location-summary", fact_lines)


def _location_label(record: dict[str, Any]) -> str:
    return location_reference_label(record)


def _section_name_provenance_facts(
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
            f"| {item['kind'].title()} | "
            f"{sprite_with_link(_entity_sprite('item', item['item_id'], references), item_link)} "
            f"| {item['item_id']} | ({item['x']}, {item['z']}) |"
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
        lines.extend(
            [
                f"### {label}",
                "",
            ]
        )
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
            item_link = _entity_link(
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
                f"| {sprite_with_link(_entity_sprite('item', item['item_id'], references), item_link)} "
                f"| {item['item_id']} | {price} | "
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
        lines.append(f"- {link} ({source})")
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
        ]
    )
    rows = []
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
        pokemon_sprite = _entity_sprite("pokemon", gift["species_id"], references)
        held_item_sprite = (
            _entity_sprite("item", gift["held_item_id"], references)
            if gift["held_item_id"] is not None and gift["held_item_name"]
            else "—"
        )
        held_item_cell = (
            sprite_with_link(held_item_sprite, held_item)
            if gift["held_item_id"] is not None and gift["held_item_name"]
            else "—"
        )
        rows.append(
            f"| {sprite_with_link(pokemon_sprite, pokemon)} | "
            f"{reference_type_cell('pokemon', gift['species_id'], references)} | "
            f"{kind} | {gift['level']} | {held_item_cell} |"
        )
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Kind | Level | Held item |",
                "| ------- | ---- | ---- | ----: | --------- |",
            ],
            rows,
        )
    )


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
        ]
    )
    rendered_outcomes = set()
    rows = []
    for encounter in encounters:
        outcome = (encounter["name"], encounter["level"], encounter["command"])
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
        sprite = _entity_sprite("pokemon", encounter["species_id"], references)
        rows.append(
            f"| {sprite_with_link(sprite, pokemon)} | "
            f"{reference_type_cell('pokemon', encounter['species_id'], references)} | "
            f"{encounter['level']} | `{encounter['command']}` |"
        )
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Level | Command |",
                "| ------- | ---- | ----: | ------- |",
            ],
            rows,
        )
    )


def _append_roaming_activations(
    lines: list[str],
    activations: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not activations:
        return
    lines.extend(
        [
            "## Roaming activations",
            "",
            "Literal roaming-slot activation commands in this map's scripts. "
            "Each slot's species is a fixed engine assignment, not ROM table "
            "data; its level is a compiled constant we haven't verified "
            "per-ROM, so it isn't shown.",
            "",
        ]
    )
    rows = [
        (
            f"| {sprite_with_link(_entity_sprite('pokemon', activation['species_id'], references), _entity_link('pokemon', activation['species_id'], activation['species_name'], source_file, references))} | "
            f"{reference_type_cell('pokemon', activation['species_id'], references)} | "
            f"{activation['slot']} | `{activation['script_file_id']}"
            f"@0x{activation['command_offset']:X}` |"
        )
        for activation in activations
    ]
    lines.extend(
        pokemon_table(
            [
                "| Pokémon | Type | Roaming slot | Script command |",
                "| ------- | ---- | -----------: | -------------- |",
            ],
            rows,
        )
    )


def _merge_bonus_species(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate species in a flat, equal-weight ROM species list.

    Honey tree and daily-rotation pools store one entry per slot with no
    explicit chance value; a species listed twice is twice as likely to be
    picked as one listed once, the same relationship wild-encounter slots
    express with a stored chance. Each slot is given equal weight here so
    duplicates can be collapsed into a single row with a derived chance.
    """
    if not entries:
        return []
    slot_chance = 100 / len(entries)
    merged: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for entry in entries:
        species_id = entry["species_id"]
        if species_id not in merged:
            merged[species_id] = {**entry, "chance": slot_chance}
            order.append(species_id)
        else:
            merged[species_id]["chance"] += slot_chance
    return [merged[species_id] for species_id in order]


def _format_chance(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _append_honey_tree(
    lines: list[str],
    honey_tree: dict[str, Any] | None,
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not honey_tree:
        return
    lines.extend(
        [
            "## Honey tree",
            "",
            "Slathering this tree has a 70% chance of a Common encounter, 20% "
            "Uncommon, and 10% no encounter; four specific trees per save file "
            "(chosen from the trainer ID) instead use 20% Common, 70% Uncommon, "
            "1% Rare, and 9% no encounter. Which trees are a save file's Rare "
            "trees is not ROM data.",
            "",
        ]
    )
    for label, key in (
        ("Common", "common"),
        ("Uncommon", "uncommon"),
        ("Rare", "rare"),
    ):
        rows = [
            (
                f"| {sprite_with_link(_entity_sprite('pokemon', entry['species_id'], references), _entity_link('pokemon', entry['species_id'], entry['name'], source_file, references))} | "
                f"{reference_type_cell('pokemon', entry['species_id'], references)} | "
                f"{_format_chance(entry['chance'])} |"
            )
            for entry in _merge_bonus_species(honey_tree[key])
        ]
        lines.extend([f"**{label}:**", ""])
        lines.extend(
            pokemon_table(
                ["| Pokémon | Type | Chance |", "| ------- | ---- | -----: |"], rows
            )
        )


def _append_daily_encounter_pool(
    lines: list[str],
    pool: dict[str, Any] | None,
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not pool:
        return
    label = "Great Marsh" if pool["kind"] == "great_marsh" else "Trophy Garden"
    lines.extend([f"## {label} daily rotation", ""])
    if pool["pre_national_dex_species"] is not None:
        lines.extend(
            [
                "This location shares one daily pool across all six Great Marsh "
                "areas, gated on whether the player has the National Pokédex. "
                "Which entry is active on a given day comes from save-file "
                "state, not ROM data, so the full pool is listed instead of "
                "today's pick.",
                "",
            ]
        )
        groups = (
            ("After National Dex", pool["species"]),
            ("Before National Dex", pool["pre_national_dex_species"]),
        )
    else:
        lines.extend(
            [
                "Two of these Pokémon are available at a time and rotate on a "
                "cooldown; which two are active comes from save-file state, "
                "not ROM data, so the full pool is listed instead of today's "
                "pick.",
                "",
            ]
        )
        groups = ((None, pool["species"]),)
    for group_label, entries in groups:
        rows = [
            (
                f"| {sprite_with_link(_entity_sprite('pokemon', entry['species_id'], references), _entity_link('pokemon', entry['species_id'], entry['name'], source_file, references))} | "
                f"{reference_type_cell('pokemon', entry['species_id'], references)} | "
                f"{_format_chance(entry['chance'])} |"
            )
            for entry in _merge_bonus_species(entries)
        ]
        if group_label:
            lines.extend([f"**{group_label}:**", ""])
        lines.extend(
            pokemon_table(
                ["| Pokémon | Type | Chance |", "| ------- | ---- | -----: |"], rows
            )
        )


def _append_game_corner_prizes(
    lines: list[str],
    prizes: list[dict[str, Any]],
    source_file: str,
    references: ReferenceIndex | None,
) -> None:
    if not prizes:
        return
    lines.extend(
        [
            "## Game Corner prizes",
            "",
            "Coin prices from the Prize Exchange counter's fixed prize table.",
            "",
            "| Item | Item ID | Price |",
            "| ---- | ------: | ----: |",
        ]
    )
    for prize in prizes:
        item_link = _entity_link(
            "item", prize["item_id"], prize["name"], source_file, references
        )
        lines.append(
            f"| {sprite_with_link(_entity_sprite('item', prize['item_id'], references), item_link)} "
            f"| {prize['item_id']} | {prize['price']:,} coins |"
        )
    lines.append("")


def _append_npc_trades(
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
        ot_details = [f"ID {trade['ot_id']:05}"]
        if trade.get("ot_gender"):
            ot_details.append(trade["ot_gender"].lower())
        if trade.get("language"):
            ot_details.append(trade["language"])
        ot = f"{escape_table_cell(trade['ot_name'])} ({', '.join(ot_details)})"
        requested_sprite = _entity_sprite(
            "pokemon",
            trade["requested_species_id"],
            references,
        )
        offered_sprite = _entity_sprite(
            "pokemon",
            trade["offered_species_id"],
            references,
        )
        held_item_sprite = (
            _entity_sprite("item", trade["held_item_id"], references)
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


def _entity_sprite(
    kind: str,
    identifier: int | str | None,
    references: ReferenceIndex | None,
) -> str:
    return reference_sprite_cell(kind, identifier, references)


def _append_warps(
    lines: list[str],
    warps: list[dict[str, Any]],
    source_file: str,
    location_labels: Mapping[int, str] | None = None,
) -> None:
    if not warps:
        return
    lines.extend(
        [
            "## Warps",
            "",
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
        ]
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


def _append_connections(
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


def _entity_link(
    kind: str,
    identifier: int | str,
    label: str,
    source_file: str,
    references: ReferenceIndex | None,
) -> str:
    return entity_markdown_link(kind, identifier, label, source_file, index=references)


def _filename(header_id: int) -> str:
    return f"header-{header_id:03}.md"
