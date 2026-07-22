from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text as _write_text,
)
from romwiki.renderers.mkdocs.components import (
    empty_state,
    display_name,
    record_nav_link,
    record_navigation,
    table_sprite_cell,
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
    unique_references,
)


def render_trainer_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = [record for record in dataset["records"] if record["party"]]
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
        following = (
            sorted_linked[index + 1] if index + 1 < len(sorted_linked) else None
        )
        if only_pages is None or filename.removesuffix(".md") in only_pages:
            _write_text(
                output_root / filename,
                _render_trainer(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                    previous,
                    following,
                ),
            )
            page_count += 1
        location_names = " / ".join(
            dict.fromkeys(
                location["name"]
                for location in record["locations"]
                + record.get("script_references", [])
            )
        )
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
            _write_text(
                output_root / filename,
                _render_trainer(
                    record,
                    change,
                    comparison.get("baseline") if comparison else None,
                    None,
                    previous,
                    following,
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
    _write_text(
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
    location_names = list(
        dict.fromkeys(
            location["name"]
            for location in record["locations"] + record.get("script_references", [])
        )
    )
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
            for location in record["locations"] + record.get("script_references", [])
        ]
    )
    species = [member["name"] for member in party]
    label = _trainer_label(record)
    return add_change_status({
        "id": record["trainer_id"],
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
        "search_text": " ".join((label, *location_names, *species)).lower(),
    }, change)


def _render_trainer(
    record: dict[str, Any],
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> str:
    label = _trainer_label(record)
    source_file = f"trainers/trainer-{record['trainer_id']:04}.md"
    source_url = f"trainers/trainer-{record['trainer_id']:04}/"
    lines = [
        f"# {label}",
        "",
        *_trainer_summary(record),
        *comparison_section(change, baseline_name, source_file, references),
    ]
    _append_locations(lines, record["locations"], source_file)
    _append_script_references(
        lines, record.get("script_references", []), source_file
    )
    lines.extend(["## Party", "", *_party_cards(record["party"], source_url)])
    _append_ai_battle_items(lines, record, source_file)
    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Data provenance</summary>",
            "",
            (
                f"Source: exact ROM trainer record from `{record['provenance']['archive']}` "
                f"member `{record['provenance']['member']}` and party record from "
                f"`{record['party_provenance']['archive']}` member "
                f"`{record['party_provenance']['member']}`."
            ),
            "",
            "</details>",
            "",
        ]
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _append_ai_battle_items(
    lines: list[str], record: dict[str, Any], source_file: str
) -> None:
    lines.extend(
        [
            "## AI battle items",
            "",
            "Items the trainer AI may use during battle. These are not prize items.",
            "",
        ]
    )
    items = [item for item in record.get("ai_battle_items", []) if item.get("name")]
    if not items:
        lines.extend(empty_state("No AI battle items."))
        return
    grouped_items: dict[int | str, dict[str, Any]] = {}
    for item in items:
        identity = item.get("id", item.get("slug", item["name"]))
        grouped = grouped_items.setdefault(identity, {"item": item, "quantity": 0})
        grouped["quantity"] += 1

    lines.extend(
        [
            "| Icon | Item | Quantity |",
            "| ---- | ---- | -------: |",
        ]
    )
    for identity, grouped in grouped_items.items():
        item = grouped["item"]
        item_link = ROUTES.markdown_link(
            entity_reference(
                "item",
                identity,
                item["name"],
                item.get("slug"),
            ),
            source_file,
        )
        lines.append(
            f"| {table_sprite_cell(item.get('sprite_url'))} | {item_link} | "
            f"{grouped['quantity']} |"
        )
    lines.append("")


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"trainers/trainer-{record['trainer_id']:04}/"
    previous_link = None
    if previous is not None:
        label = f"← {_trainer_label(previous)}"
        href = ROUTES.published_href(
            entity_reference(
                "trainer", previous["trainer_id"], label, previous["trainer_id"]
            ),
            source_url,
        )
        previous_link = record_nav_link(href, label, "prev")
    following_link = None
    if following is not None:
        label = f"{_trainer_label(following)} →"
        href = ROUTES.published_href(
            entity_reference(
                "trainer", following["trainer_id"], label, following["trainer_id"]
            ),
            source_url,
        )
        following_link = record_nav_link(href, label, "next")
    lines.extend(
        record_navigation(previous_link, following_link, "Trainer navigation")
    )


def _trainer_level_range(record: dict[str, Any]) -> str:
    levels = [member["level"] for member in record["party"]]
    return (
        f"{min(levels)}" if min(levels) == max(levels) else f"{min(levels)}–{max(levels)}"
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


def _trainer_summary(record: dict[str, Any]) -> list[str]:
    location_names = list(
        dict.fromkeys(
            location["name"]
            for location in record["locations"] + record.get("script_references", [])
        )
    )
    level_range = _trainer_level_range(record)
    return [
        '<section class="rw-trainer-summary">',
        '<dl class="rw-summary__facts">',
        f"<div><dt>Trainer ID</dt><dd>{record['trainer_id']}</dd></div>",
        f"<div><dt>Class</dt><dd>{display_name(record['class_name'])}</dd></div>",
        (
            "<div><dt>Location</dt><dd>"
            f"{' / '.join(location_names) if location_names else 'Unlinked'}</dd></div>"
        ),
        (
            "<div><dt>Battle format</dt><dd>"
            f"{'Double battle' if record['double_battle'] else 'Single battle'}</dd></div>"
        ),
        f"<div><dt>Party size</dt><dd>{len(record['party'])}</dd></div>",
        f"<div><dt>Level range</dt><dd>{level_range}</dd></div>",
        "</dl>",
        "</section>",
        "",
    ]


def _party_cards(party: list[dict[str, Any]], source_url: str) -> list[str]:
    lines = ['<div class="rw-party-grid">']
    for index, member in enumerate(party, start=1):
        pokemon = member["pokemon"]
        held_item = member["held_item"]
        if held_item and held_item["name"]:
            item_link = ROUTES.html_link(
                entity_reference(
                    "item",
                    held_item.get("id", held_item["name"]),
                    held_item["name"],
                    held_item.get("slug"),
                ),
                source_url,
            )
            item_sprite = held_item.get("sprite_url")
            item_icon = (
                f'<img class="rw-party-card__item-icon" src="{escape(item_sprite, quote=True)}" '
                'alt="" loading="lazy">'
                if item_sprite
                else ""
            )
            item_name = f'<span class="rw-party-card__item">{item_icon}{item_link}</span>'
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
            f'alt="" loading="lazy">'
            if pokemon_sprite and pokemon_sprite.get("url")
            else ""
        )
        lines.extend(
            [
                '<article class="rw-party-card">',
                f'<span class="rw-party-card__slot">Slot {index}</span>',
                '<div class="rw-party-card__header">',
                sprite_icon,
                f"<h3>{pokemon_link}</h3>",
                "</div>",
                '<dl class="rw-summary__facts">',
                f"<div><dt>Level</dt><dd>{member['level']}</dd></div>",
                f"<div><dt>Held item</dt><dd>{item_name}</dd></div>",
                "</dl>",
            ]
        )
        if member["moves_source"] == "explicit":
            lines.append('<ol class="rw-party-card__moves" aria-label="Moves">')
            for move in member["moves"]:
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
                lines.append(f"<li>{move_link}</li>")
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
        lines.append("</article>")
    lines.extend(["</div>", ""])
    return lines


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
    lines.extend(
        [
            "",
            "Source: literal `StartTrainerBattle` command followed by "
            "`CheckWonBattle` in the map's script archive member.",
            "",
        ]
    )


def _trainer_label(record: dict[str, Any]) -> str:
    return " ".join(value for value in (record["class_name"], record["name"]) if value)


