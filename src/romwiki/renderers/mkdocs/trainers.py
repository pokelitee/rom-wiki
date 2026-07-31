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
    ability_link,
    class_badge,
    display_name,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    sprite_with_link,
    summary_section,
    summary_section_link,
    table_sprite_cell,
    type_badges,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    unique_references,
)

_SAME_NAME_COLLAPSE_THRESHOLD = 5


def render_trainer_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = [record for record in dataset["records"] if record["party"]]
    same_name_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (record["class_name"], record["name"])
        same_name_groups.setdefault(key, []).append(record)
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"trainer-{record['trainer_id']:04}.md"
                for record in records
                if only_pages is None
                or f"trainer-{record['trainer_id']:04}" in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    linked = [
        record
        for record in records
        if record["locations"] or record.get("script_references", [])
    ]
    unlinked = [
        record
        for record in records
        if not record["locations"] and not record.get("script_references", [])
    ]
    sorted_linked = sorted(
        linked,
        key=lambda item: (
            (item["locations"] or item.get("script_references", []))[0]["name"],
            _trainer_label(item),
            item["trainer_id"],
        ),
    )
    for index, record in enumerate(sorted_linked):
        change = record_comparison(comparison, record["trainer_id"])
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        previous = sorted_linked[index - 1] if index else None
        following = sorted_linked[index + 1] if index + 1 < len(sorted_linked) else None
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_trainer(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    previous,
                    following,
                    same_name_groups[(record["class_name"], record["name"])],
                ),
            )
            page_count += 1
        location_names = " / ".join(_location_names(record))
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "trainer",
                    record["trainer_id"],
                    f"{location_names} — {label} ({_trainer_disambiguator(record)})",
                    record["trainer_id"],
                ),
                "trainers/index.md",
            )
        )
        catalog_records.append(
            _catalog_record(
                record,
                filename.removesuffix(".md") + "/",
                location_names,
                True,
                change,
            )
        )
    for index, record in enumerate(unlinked):
        change = record_comparison(comparison, record["trainer_id"])
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        previous = unlinked[index - 1] if index else None
        following = unlinked[index + 1] if index + 1 < len(unlinked) else None
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            write_text(
                output_root / filename,
                _render_trainer(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    None,
                    previous,
                    following,
                    same_name_groups[(record["class_name"], record["name"])],
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "trainer",
                    record["trainer_id"],
                    f"{label} ({_trainer_disambiguator(record)})",
                    record["trainer_id"],
                ),
                "trainers/index.md",
            )
        )
        catalog_records.append(
            _catalog_record(
                record,
                filename.removesuffix(".md") + "/",
                "",
                False,
                change,
            )
        )
    write_catalog(output_root, "trainers", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Trainers",
            "Trainer parties and battle settings extracted directly from the ROM.",
            "trainers",
            fallback_links,
        ),
    )
    return page_count


def _catalog_record(
    record: dict[str, Any],
    filename: str,
    location_label: str,
    linked: bool,
    change: dict[str, Any] | None = None,
) -> dict[str, Any]:
    levels = [member["level"] for member in record["party"]]
    location_names = _location_names(record)
    party = [
        {
            "name": member["pokemon"]["name"],
            "level": member["level"],
            "pokemon_ref": ROUTES.catalog_reference(
                entity_reference(
                    "pokemon",
                    member["pokemon"].get("id", member["pokemon"]["slug"]),
                    member["pokemon"]["name"],
                    member["pokemon"].get("slug"),
                ),
                "trainers/",
            ),
        }
        for member in record["party"]
    ]
    location_refs = unique_references(
        [
            entity_reference(
                "location",
                location["header_id"],
                location["name"],
                location.get("header_id"),
            )
            for location in _combined_locations(record)
        ]
    )
    species = [member["name"] for member in party]
    label = _trainer_label(record)
    route_id = filename.removesuffix("/")
    return add_change_status(
        {
            "id": record["trainer_id"],
            "route_id": route_id,
            "label": label,
            "url": filename,
            "class_name": record["class_name"],
            "name": record["name"],
            "locations": location_names,
            "location_label": location_label,
            "location_refs": [
                ROUTES.catalog_reference(reference, "trainers/")
                for reference in location_refs
            ],
            "linked": linked,
            "double_battle": record["double_battle"],
            "party_size": len(record["party"]),
            "min_level": min(levels),
            "max_level": max(levels),
            "pokemon": species,
            "party": party,
            "search_text": " ".join(
                (label, route_id, *location_names, *species)
            ).lower(),
        },
        change,
    )


def _render_trainer(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    same_name_records: list[dict[str, Any]] | None = None,
) -> str:
    label = _trainer_label(record)
    source_file = f"trainers/trainer-{record['trainer_id']:04}.md"
    source_url = f"trainers/trainer-{record['trainer_id']:04}/"
    grouped_ai_items = _group_ai_battle_items(record)
    lines = [
        f"# {label}",
        "",
        *_trainer_summary(record, grouped_ai_items, source_url),
        "## Party",
        "",
        *_party_cards(record["party"], source_url),
    ]
    _append_ai_battle_items(lines, grouped_ai_items, source_file)
    _append_locations(lines, record["locations"], source_file)
    _append_script_references(lines, record.get("script_references", []), source_file)
    _append_same_name_trainers(lines, record, same_name_records or [], source_file)
    lines.extend(comparison_section(change, baseline_name, source_file, references))
    lines.extend(provenance_section(_trainer_provenance(record)))
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _group_ai_battle_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    grouped_items: dict[int | str, dict[str, Any]] = {}
    for item in record.get("ai_battle_items", []):
        if not item.get("name"):
            continue
        identity = item.get("id", item.get("slug", item["name"]))
        grouped = grouped_items.setdefault(identity, {"item": item, "quantity": 0})
        grouped["quantity"] += 1
    return list(grouped_items.values())


def _ai_item_identity(item: dict[str, Any]) -> int | str:
    return item.get("id", item.get("slug", item["name"]))


def _ai_item_link(grouped: dict[str, Any], source_url: str) -> str:
    item = grouped["item"]
    link = ROUTES.html_link(
        entity_reference(
            "item", _ai_item_identity(item), item["name"], item.get("slug")
        ),
        source_url,
    )
    quantity = f" ×{grouped['quantity']}" if grouped["quantity"] > 1 else ""
    return f"{link}{quantity}"


def _append_ai_battle_items(
    lines: list[str], grouped_items: list[dict[str, Any]], source_file: str
) -> None:
    if not grouped_items:
        return
    lines.extend(
        [
            "## AI battle items",
            "",
            "Items the trainer AI may use during battle. These are not prize items.",
            "",
            "| Item | Quantity |",
            "| ---- | -------: |",
        ]
    )
    for grouped in grouped_items:
        item = grouped["item"]
        item_link = ROUTES.markdown_link(
            entity_reference(
                "item",
                _ai_item_identity(item),
                item["name"],
                item.get("slug"),
            ),
            source_file,
        )
        lines.append(
            f"| {sprite_with_link(table_sprite_cell(item.get('sprite_url')), item_link)} | "
            f"{grouped['quantity']} |"
        )
    lines.append("")


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    lines.extend(
        record_navigation_for(
            "trainer",
            f"trainers/trainer-{record['trainer_id']:04}/",
            previous,
            following,
            aria_label="Trainer navigation",
            identity=lambda value: value["trainer_id"],
            route_key=lambda value: value["trainer_id"],
            label=_trainer_label,
        )
    )


def _trainer_provenance(record: dict[str, Any]) -> list[str]:
    facts = [("Class ID", f"`{record['class_id']}`")]
    if "class_gender" in record:
        facts.append(("Class gender", record["class_gender"].capitalize()))
    facts.append(("AI flags", f"`0x{record['ai_flags']:08X}`"))
    if "battle_type" in record:
        facts.append(("Battle type", f"`{record['battle_type']}`"))
    else:
        facts.append(("Battle mode", f"`{record['battle_mode']}`"))
    if "unknown_byte" in record:
        facts.append(("Unknown byte", f"`0x{record['unknown_byte']:02X}`"))
    if "victory_money_multiplier" in record:
        facts.append(
            ("Victory money multiplier", f"`{record['victory_money_multiplier']}`")
        )
    base_prize_money = record.get("base_prize_money")
    if base_prize_money:
        facts.extend(
            [
                (
                    "Prize-money final party level",
                    f"`{base_prize_money['final_party_level']}`",
                ),
                ("Prize-money base factor", f"`{base_prize_money['base_factor']}`"),
                (
                    "Prize-money battle-format factor",
                    f"`{base_prize_money['battle_format_multiplier']}`",
                ),
            ]
        )
    entries = [
        *provenance_fact_table(facts),
        (
            "Source: exact ROM trainer record from "
            f"`{record['provenance']['archive']}` member "
            f"`{record['provenance']['member']}` and party record from "
            f"`{record['party_provenance']['archive']}` member "
            f"`{record['party_provenance']['member']}`."
        ),
    ]
    if base_prize_money:
        multiplier_source = base_prize_money.get("multiplier_provenance") or {}
        if "overlay_id" in multiplier_source:
            entries.append(
                "Prize-money multiplier source: ARM9 overlay "
                f"`{multiplier_source['overlay_id']}` at byte offset "
                f"`0x{multiplier_source['offset']:X}` for trainer class "
                f"`{multiplier_source['class_id']}`."
            )
        elif multiplier_source.get("archive"):
            entries.append(
                "Prize-money multiplier source: trainer record byte "
                f"`0x{multiplier_source['offset']:X}` in "
                f"`{multiplier_source['archive']}` member "
                f"`{multiplier_source['member']}`."
            )
    if record.get("locations"):
        entries.append(
            "Overworld locations: trainer event objects whose script IDs "
            "resolve directly to this trainer record."
        )
    if record.get("script_references"):
        entries.append(
            "Scripted battle locations: literal `StartTrainerBattle` commands "
            "followed by `CheckWonBattle`; only literal trainer IDs are linked."
        )
    return entries


# Trainer Data record comment, Gen5RomHandler.java: "Battle Mode; 1 byte;
# 0=single, 1=double, 2=triple, 3=rotation" -- unlike Generation IV, which
# only ever has single/double battles, so `double_battle` alone would
# misrepresent a triple or rotation battle as merely "double".
_GEN5_BATTLE_MODE_LABELS = {
    0: "Single battle",
    1: "Double battle",
    2: "Triple battle",
    3: "Rotation battle",
}


def _battle_format_label(record: dict[str, Any]) -> str:
    if "battle_mode" in record:
        return _GEN5_BATTLE_MODE_LABELS.get(
            record["battle_mode"], f"Battle mode {record['battle_mode']}"
        )
    return "Double battle" if record["double_battle"] else "Single battle"


def _trainer_level_range(record: dict[str, Any]) -> str:
    levels = [member["level"] for member in record["party"]]
    return (
        f"{min(levels)}"
        if min(levels) == max(levels)
        else f"{min(levels)}–{max(levels)}"
    )


def _party_preview(record: dict[str, Any], limit: int = 3) -> str:
    species = [member["pokemon"]["name"] for member in record["party"]]
    preview = ", ".join(species[:limit])
    remaining = len(species) - limit
    return f"{preview}, +{remaining} more" if remaining > 0 else preview


def _trainer_disambiguator(record: dict[str, Any]) -> str:
    """A compact "which one is this" hint for trainers sharing a display name.

    Many trainers share a class + name — some legitimately are the same
    story character rematched later with a stronger team (Gym Leaders, the
    Sinnoh trio, Cyrus), but most are simply distinct NPCs the game never
    gave individual names (dozens of unrelated "Galactic Grunt" trainers).
    The ROM has no field distinguishing the two, so rather than guess, every
    entry gets its level range and party species — usually enough to tell
    apart trainers that share both a name and a location.
    """
    return f"Lv. {_trainer_level_range(record)}: {_party_preview(record)}"


def _location_summary_value(record: dict[str, Any], location_names: list[str]) -> str:
    if not location_names:
        return "Unlinked"
    anchor = "locations" if record["locations"] else "scripted-battle-locations"
    return summary_section_link(" / ".join(location_names), anchor)


def _trainer_summary(
    record: dict[str, Any],
    grouped_ai_items: list[dict[str, Any]],
    source_url: str,
) -> list[str]:
    location_names = _location_names(record)
    level_range = _trainer_level_range(record)
    ai_items = (
        ", ".join(_ai_item_link(grouped, source_url) for grouped in grouped_ai_items)
        or '<span class="rw-summary__empty">None</span>'
    )
    victory_item = record.get("victory_item")
    victory_item_link = (
        ROUTES.html_link(
            entity_reference(
                "item",
                victory_item["id"],
                victory_item["name"],
                victory_item.get("slug"),
            ),
            source_url,
        )
        if victory_item
        else None
    )
    base_prize_money = record.get("base_prize_money")
    return summary_section(
        "rw-trainer-summary",
        [
            f"<div><dt>Trainer ID</dt><dd>{record['trainer_id']}</dd></div>",
            f"<div><dt>Class</dt><dd>{display_name(record['class_name'])}</dd></div>",
            (
                "<div><dt>Location</dt><dd>"
                f"{_location_summary_value(record, location_names)}</dd></div>"
            ),
            (
                "<div><dt>Battle format</dt><dd>"
                f"{_battle_format_label(record)}</dd></div>"
            ),
            "<div><dt>Party size</dt><dd>"
            f"{summary_section_link(len(record['party']), 'party')}</dd></div>",
            "<div><dt>Level range</dt><dd>"
            f"{summary_section_link(level_range, 'party')}</dd></div>",
            *(
                [
                    "<div><dt>Base prize money</dt><dd>"
                    f"&#8381;{base_prize_money['amount']:,}</dd></div>"
                ]
                if base_prize_money
                else []
            ),
            f"<div><dt>AI items</dt><dd>{ai_items}</dd></div>",
            *(
                ["<div><dt>After victory</dt><dd>Heals the player's party</dd></div>"]
                if record.get("healer")
                else []
            ),
            *(
                [f"<div><dt>Victory item</dt><dd>{victory_item_link}</dd></div>"]
                if victory_item_link
                else []
            ),
        ],
    )


def _party_cards(party: list[dict[str, Any]], source_url: str) -> list[str]:
    lines = ['<div class="rw-party-grid">']
    for index, member in enumerate(party, start=1):
        pokemon = member["pokemon"]
        held_item = member["held_item"]
        if held_item and held_item["name"]:
            item_link = ROUTES.html_link(
                entity_reference(
                    "item",
                    held_item.get("id", held_item.get("slug", held_item["name"])),
                    held_item["name"],
                    held_item.get("slug"),
                ),
                source_url,
            )
            item_sprite = held_item.get("sprite_url")
            item_icon = (
                f'<img class="rw-party-card__item-icon" src="{escape(item_sprite, quote=True)}" '
                'alt="" width="21" height="21" loading="lazy">'
                if item_sprite
                else ""
            )
            item_name = (
                f'<span class="rw-party-card__item">{item_icon}{item_link}</span>'
            )
        else:
            item_name = "—"
        pokemon_link = ROUTES.html_link(
            entity_reference(
                "pokemon",
                pokemon.get("id", pokemon["slug"]),
                pokemon["name"],
                pokemon.get("slug"),
            ),
            source_url,
        )
        pokemon_sprite = pokemon.get("sprite")
        sprite_icon = (
            f'<img class="rw-party-card__sprite" src="{escape(pokemon_sprite["url"], quote=True)}" '
            f'alt="" width="48" height="48" loading="lazy">'
            if pokemon_sprite and pokemon_sprite.get("url")
            else ""
        )
        ability = member.get("ability")
        ability_link_html = (
            ability_link(ability, source_url)
            if ability and ability.get("name")
            else None
        )
        details = []
        pokemon_types = pokemon.get("types", [])
        nature = member.get("nature")
        if nature:
            nature_name = nature.get("name", nature.get("value"))
            if nature_name is not None:
                details.append(("Nature", escape(str(nature_name))))
        if ability_link_html is not None:
            details.append(("Ability", ability_link_html))
        details.append(("Held item", item_name))
        gender_html = _party_gender(member.get("gender"))
        types_html = (
            f'<div class="rw-party-card__types">{type_badges(pokemon_types)}</div>'
            if pokemon_types
            else ""
        )
        lines.extend(
            [
                '<article class="rw-party-card">',
                f'<span class="rw-party-card__slot">Slot {index}</span>',
                '<div class="rw-party-card__header">',
                sprite_icon,
                '<div class="rw-party-card__identity">',
                '<div class="rw-party-card__heading">',
                f'<span class="rw-party-card__level">Lv. {member["level"]}</span>',
                f"<h3>{pokemon_link}</h3>",
                gender_html,
                "</div>",
                types_html,
                "</div>",
                "</div>",
                '<dl class="rw-party-card__details rw-party-card__section">',
                *[
                    f"<div><dt>{label}</dt><dd>{value}</dd></div>"
                    for label, value in details
                ],
                "</dl>",
            ]
        )
        stat_table = _party_stat_table(member)
        if stat_table:
            lines.append('<section class="rw-party-card__section">')
            lines.append('<h4 class="rw-party-card__section-title">Stats</h4>')
            lines.extend(stat_table)
            lines.append("</section>")
        lines.extend(
            [
                '<section class="rw-party-card__section">',
                '<h4 class="rw-party-card__section-title">Moves</h4>',
            ]
        )
        if member["moves_source"] == "explicit":
            move_label = escape(f"{pokemon['name']} moves", quote=True)
            lines.append(f'<ol class="rw-party-card__moves" aria-label="{move_label}">')
            for move_index, move in enumerate(member["moves"], start=1):
                slug = move["name"]
                move_link = ROUTES.html_link(
                    entity_reference(
                        "move",
                        move.get("id", slug),
                        display_name(slug),
                        slug,
                    ),
                    source_url,
                )
                move_metadata = []
                if move.get("type"):
                    move_metadata.append(type_badges([move["type"]]))
                if move.get("damage_class"):
                    move_metadata.append(class_badge(move["damage_class"]))
                metadata_html = (
                    '<span class="rw-party-card__move-meta">'
                    + "".join(move_metadata)
                    + "</span>"
                    if move_metadata
                    else ""
                )
                lines.append(
                    '<li><span class="rw-party-card__move-name">'
                    f'<span aria-hidden="true">{move_index}. </span>{move_link}'
                    f"</span>{metadata_html}</li>"
                )
            if not member["moves"]:
                lines.append('<li class="rw-party-card__moves-empty">No moves</li>')
            lines.append("</ol>")
        elif member["moves_source"] == "level-up":
            lines.append(
                '<p class="rw-party-card__default-moves">Uses default level-up moves.</p>'
            )
        else:
            lines.append(
                '<p class="rw-party-card__default-moves">Moves unavailable.</p>'
            )
        lines.append("</section>")
        lines.append("</article>")
    lines.extend(["</div>", ""])
    return lines


def _party_gender(gender: dict[str, Any] | None) -> str:
    if not gender:
        return ""
    name = gender.get("name", gender.get("value"))
    if name is None:
        return ""
    label = str(name)
    symbol, modifier = {
        "male": ("♂", "male"),
        "female": ("♀", "female"),
        "genderless": ("⚲", "genderless"),
    }.get(label.lower(), ("•", "unknown"))
    return (
        f'<span class="rw-party-card__gender rw-party-card__gender--{modifier}" '
        f'aria-label="{escape(label, quote=True)}" title="{escape(label, quote=True)}">'
        f"{symbol}</span>"
    )


def _party_stat_table(member: dict[str, Any]) -> list[str]:
    ordered = (
        ("HP", "hp"),
        ("Atk", "attack"),
        ("Def", "defense"),
        ("SpA", "special_attack"),
        ("SpD", "special_defense"),
        ("Spe", "speed"),
    )
    rows = []
    for label, field in (
        ("Value", "calculated_stats"),
        ("IV", "ivs"),
        ("EV", "evs"),
    ):
        attribute = member.get(field)
        values = attribute.get("values") if attribute else None
        if isinstance(values, dict) and all(key in values for _, key in ordered):
            rows.append((label, values))
    if not rows:
        return []
    return [
        '<table class="rw-party-card__stats">',
        "<caption>Stats, IVs, and EVs</caption>",
        "<thead><tr><th></th>"
        + "".join(f'<th scope="col">{label}</th>' for label, _ in ordered)
        + "</tr></thead>",
        "<tbody>",
        *[
            f'<tr><th scope="row">{label}</th>'
            + "".join(f"<td>{_stat_value(values[key])}</td>" for _, key in ordered)
            + "</tr>"
            for label, values in rows
        ],
        "</tbody>",
        "</table>",
    ]


def _stat_value(value: Any) -> str:
    if isinstance(value, dict) and {
        "minimum",
        "maximum",
    }.issubset(value):
        return f"{value['minimum']}-{value['maximum']}"
    return str(value)


def _append_locations(
    lines: list[str], locations: list[dict[str, Any]], source_file: str
) -> None:
    if not locations:
        return
    lines.extend(
        [
            "## Locations",
            "",
            "| Location | Header | Internal map | Position | Event object |",
            "| -------- | -----: | ------------ | -------- | ------------ |",
        ]
    )
    for location in locations:
        link = ROUTES.markdown_link(
            entity_reference(
                "location",
                location["header_id"],
                location["name"],
                location.get("header_id"),
            ),
            source_file,
        )
        lines.append(
            f"| {link} "
            f"| {location['header_id']} | "
            f"`{location['internal_name']}` | ({location['x']}, {location['z']}) | "
            f"`{location['event_file_id']}:{location['object_index']}` |"
        )
    lines.append("")


def _append_script_references(
    lines: list[str], references: list[dict[str, Any]], source_file: str
) -> None:
    if not references:
        return
    lines.extend(
        [
            "## Scripted battle locations",
            "",
            "| Location | Header | Internal map | Script command | Opponent slot |",
            "| -------- | -----: | ------------ | -------------- | ------------: |",
        ]
    )
    for reference in references:
        link = ROUTES.markdown_link(
            entity_reference(
                "location",
                reference["header_id"],
                reference["name"],
                reference.get("header_id"),
            ),
            source_file,
        )
        lines.append(
            f"| {link} "
            f"| {reference['header_id']} | "
            f"`{reference['internal_name']}` | "
            f"`{reference['script_file_id']}@0x{reference['command_offset']:X}` | "
            f"{reference['opponent_slot']} |"
        )
    lines.append("")


def _append_same_name_trainers(
    lines: list[str],
    record: dict[str, Any],
    same_name_records: list[dict[str, Any]],
    source_file: str,
) -> None:
    related = sorted(
        (
            candidate
            for candidate in same_name_records
            if candidate["trainer_id"] != record["trainer_id"]
        ),
        key=lambda candidate: candidate["trainer_id"],
    )
    if not related:
        return
    count = len(related)
    lines.extend(
        [
            "## Same-name trainers",
            "",
            (
                "These records share the exact trainer class and name. The ROM does "
                "not establish that they represent the same character."
            ),
            "",
        ]
    )
    collapsed = count > _SAME_NAME_COLLAPSE_THRESHOLD
    if collapsed:
        lines.extend(
            [
                '<details markdown="1">',
                f"<summary>{count} other parties</summary>",
                "",
            ]
        )
    lines.extend(
        [
            "| Trainer | Location | Levels | Party |",
            "| ------- | -------- | ------ | ----- |",
        ]
    )
    for candidate in related:
        trainer_id = candidate["trainer_id"]
        trainer_link = ROUTES.markdown_link(
            entity_reference("trainer", trainer_id, f"ID {trainer_id}", trainer_id),
            source_file,
        )
        locations = _location_names(candidate)
        lines.append(
            f"| {trainer_link} | {' / '.join(locations) or 'Unlinked'} | "
            f"{_trainer_level_range(candidate)} | {_party_preview(candidate)} |"
        )
    lines.append("")
    if collapsed:
        lines.extend(["</details>", ""])


def _trainer_label(record: dict[str, Any]) -> str:
    return " ".join(value for value in (record["class_name"], record["name"]) if value)


def _combined_locations(record: dict[str, Any]) -> list[dict[str, Any]]:
    return record["locations"] + record.get("script_references", [])


def _location_names(record: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(location["name"] for location in _combined_locations(record))
    )
