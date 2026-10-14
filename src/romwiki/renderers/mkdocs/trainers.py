from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any, cast

from romwiki.pipeline.enrichment.features import POST_BATTLE_HEALING, VICTORY_ITEMS
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
    ability_link,
    class_badge,
    content_tabs,
    display_name,
    escape_heading,
    escape_table_cell,
    provenance_fact_table,
    provenance_section,
    record_navigation_for,
    sprite_with_link,
    summary_section,
    summary_section_link,
    table_sprite_cell,
    type_badges,
    with_resolved_location_labels,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    EntityReference,
    ReferenceIndex,
    entity_reference,
    unique_references,
)
from romwiki.schema.rendering import RenderDataset, TrainerRenderRecord
from romwiki.schema.trainers import is_unused_trainer_slot

_SAME_NAME_COLLAPSE_THRESHOLD = 5
_DEFAULT_TRAINER_FEATURES = frozenset({POST_BATTLE_HEALING, VICTORY_ITEMS})


def render_trainer_pages(
    dataset: RenderDataset[TrainerRenderRecord],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    relationships: RelationshipIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    dataset_dict = cast(dict[str, Any], dataset)
    location_labels = relationships.location_labels if relationships else None
    source_records = cast(list[dict[str, Any]], dataset["records"])
    records = [
        with_resolved_location_labels(record, location_labels)
        for record in source_records
        if record["party"] and not is_unused_trainer_slot(record)
    ]
    records_by_id = {record["trainer_id"]: record for record in records}
    family_memberships: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for family in dataset_dict.get("battle_families", []):
        for variant in family["variants"]:
            if variant["trainer_id"] in records_by_id:
                family_memberships.setdefault(variant["trainer_id"], []).append(
                    (family, variant)
                )
    dataset_features = frozenset(
        dataset_dict.get("features", _DEFAULT_TRAINER_FEATURES)
    )
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
                    dataset_features,
                    family_memberships.get(record["trainer_id"], []),
                    records_by_id,
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
                family_memberships.get(record["trainer_id"], []),
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
                    references,
                    previous,
                    following,
                    same_name_groups[(record["class_name"], record["name"])],
                    dataset_features,
                    family_memberships.get(record["trainer_id"], []),
                    records_by_id,
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
                family_memberships.get(record["trainer_id"], []),
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
    family_memberships: list[tuple[dict[str, Any], dict[str, Any]]] | None = None,
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
                    member["pokemon"].get("page_slug", member["pokemon"].get("slug")),
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
    pokemon_refs = unique_references(
        entity_reference(
            "pokemon",
            member["pokemon"].get("id", member["pokemon"]["slug"]),
            member["pokemon"]["name"],
            member["pokemon"].get("page_slug", member["pokemon"].get("slug")),
        )
        for member in record["party"]
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
            "battle_format": _battle_format_value(record),
            "double_battle": record["double_battle"],
            "party_size": len(record["party"]),
            "min_level": min(levels),
            "max_level": max(levels),
            "pokemon": species,
            "pokemon_refs": [
                ROUTES.catalog_reference(reference, "trainers/")
                for reference in pokemon_refs
            ],
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
    features: frozenset[str] = _DEFAULT_TRAINER_FEATURES,
    family_memberships: list[tuple[dict[str, Any], dict[str, Any]]] | None = None,
    records_by_id: dict[int, dict[str, Any]] | None = None,
) -> str:
    label = _trainer_label(record)
    source_file = f"trainers/trainer-{record['trainer_id']:04}.md"
    source_url = f"trainers/trainer-{record['trainer_id']:04}/"
    grouped_ai_items = _group_ai_battle_items(record)
    lines = [
        f"# {escape_heading(label)}",
        "",
        *_trainer_summary(record, grouped_ai_items, source_url, features=features),
    ]
    memberships = family_memberships or []
    _append_party(
        lines,
        record,
        memberships,
        records_by_id or {},
        source_file,
        source_url,
        features=features,
        references=references,
    )
    _append_ai_battle_items(lines, grouped_ai_items, source_file)
    _append_locations(lines, record["locations"], source_file)
    _append_script_references(lines, record.get("script_references", []), source_file)
    _append_same_name_trainers(
        lines, record, same_name_records or [], source_file, references
    )
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


def _ai_item_reference(item: dict[str, Any]) -> EntityReference:
    return entity_reference(
        "item", _ai_item_identity(item), item["name"], item.get("slug")
    )


def _ai_item_link(grouped: dict[str, Any], source_url: str) -> str:
    link = ROUTES.html_link(_ai_item_reference(grouped["item"]), source_url)
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
        item_link = ROUTES.markdown_link(_ai_item_reference(item), source_file)
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


# Labels for the optional multi-format battle-mode field in the shared contract.
_BATTLE_MODE_LABELS = {
    0: "Single battle",
    1: "Double battle",
    2: "Triple battle",
    3: "Rotation battle",
}
_BATTLE_MODE_VALUES = {
    0: "single",
    1: "double",
    2: "triple",
    3: "rotation",
}


def _battle_format_value(record: dict[str, Any]) -> str:
    if "battle_mode" in record:
        mode = record["battle_mode"]
        return _BATTLE_MODE_VALUES.get(mode, f"mode-{mode}")
    return "double" if record["double_battle"] else "single"


def _battle_format_label(record: dict[str, Any]) -> str:
    if "battle_mode" in record:
        return _BATTLE_MODE_LABELS.get(
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


def _linked_party(
    record: dict[str, Any],
    source_file: str,
    references: ReferenceIndex | None = None,
) -> str:
    links = []
    for member in record["party"]:
        pokemon = member["pokemon"]
        identifier = pokemon.get("id", pokemon.get("slug", pokemon["name"]))
        name = pokemon["name"]
        reference = (
            references.resolve_matching("pokemon", identifier, name)
            if references is not None
            else entity_reference(
                "pokemon",
                identifier,
                name,
                pokemon.get("page_slug", pokemon.get("slug")),
            )
        )
        links.append(ROUTES.markdown_link(reference, source_file))
    return ", ".join(links)


def _trainer_disambiguator(record: dict[str, Any]) -> str:
    """A compact "which one is this" hint for trainers sharing a display name.

    The source has no universal field distinguishing rematches or story
    variants from unrelated NPCs with the same name. Every entry therefore
    gets its level range and party species, which usually disambiguates it
    without inferring an unsupported relationship.
    """
    return f"Lv. {_trainer_level_range(record)}: {_party_preview(record)}"


def _location_summary_value(record: dict[str, Any], location_names: list[str]) -> str:
    if not location_names:
        return '<span class="rw-summary__empty">—</span>'
    anchor = "locations" if record["locations"] else "scripted-battle-locations"
    return summary_section_link(" / ".join(location_names), anchor)


def _trainer_summary(
    record: dict[str, Any],
    grouped_ai_items: list[dict[str, Any]],
    source_url: str,
    *,
    features: frozenset[str] = _DEFAULT_TRAINER_FEATURES,
) -> list[str]:
    location_names = _location_names(record)
    level_range = _trainer_level_range(record)
    ai_items = (
        ", ".join(_ai_item_link(grouped, source_url) for grouped in grouped_ai_items)
        or '<span class="rw-summary__empty">None</span>'
    )
    victory_item = record.get("victory_item") if VICTORY_ITEMS in features else None
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
    post_battle_result = (
        "Heals the player's party"
        if record.get("healer")
        else '<span class="rw-summary__empty">No healing</span>'
    )
    victory_item_result = (
        victory_item_link or '<span class="rw-summary__empty">None</span>'
    )
    base_prize_money = record.get("base_prize_money")
    return summary_section(
        "rw-trainer-summary",
        [
            f"<div><dt>Trainer ID</dt><dd>trainer-{record['trainer_id']:04}</dd></div>",
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
                [f"<div><dt>After victory</dt><dd>{post_battle_result}</dd></div>"]
                if POST_BATTLE_HEALING in features
                else []
            ),
            *(
                [f"<div><dt>Victory item</dt><dd>{victory_item_result}</dd></div>"]
                if VICTORY_ITEMS in features
                else []
            ),
        ],
    )


def _party_cards(
    party: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None = None,
) -> list[str]:
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
        pokemon_identifier = pokemon.get("id", pokemon["slug"])
        pokemon_reference = (
            references.resolve_matching("pokemon", pokemon_identifier, pokemon["name"])
            if references is not None
            else entity_reference(
                "pokemon",
                pokemon_identifier,
                pokemon["name"],
                pokemon.get("page_slug", pokemon.get("slug")),
            )
        )
        pokemon_link = ROUTES.html_link(pokemon_reference, source_url)
        pokemon_sprite = pokemon.get("sprite")
        sprite_icon = (
            f'<img class="rw-party-card__sprite" src="{escape(pokemon_sprite["url"], quote=True)}" '
            f'alt="" width="48" height="48" loading="lazy">'
            if pokemon_sprite and pokemon_sprite.get("url")
            else ""
        )
        ability_link_html = _party_ability(member.get("ability"), source_url)
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
        moves_heading = "Moves"
        if member["moves_source"] == "level-up" and member["moves"]:
            moves_heading += (
                '<abbr class="rw-inline-note" title="Derived from the Pokémon\'s '
                'level-up learnset at this level.">*</abbr>'
            )
        lines.extend(
            [
                '<section class="rw-party-card__section">',
                f'<h4 class="rw-party-card__section-title">{moves_heading}</h4>',
            ]
        )
        if member["moves_source"] == "explicit" or member["moves"]:
            move_label = escape(f"{pokemon['name']} moves", quote=True)
            lines.append(f'<ol class="rw-party-card__moves" aria-label="{move_label}">')
            for move_index, move in enumerate(member["moves"], start=1):
                display_slug = move["name"]
                # `slug` (when present) is the move's real, ROM-derived page
                # slug -- see `pipeline/enrichment/trainers.py`'s own
                # comment -- distinct from `name`/`display_slug`, which is
                # PokeDB's canonical slug used only for display formatting.
                route_slug = move.get("slug", display_slug)
                move_link = ROUTES.html_link(
                    entity_reference(
                        "move",
                        move.get("id", route_slug),
                        display_name(display_slug),
                        route_slug,
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


def _party_ability(ability: dict[str, Any] | None, source_url: str) -> str | None:
    if not ability:
        return None
    if ability.get("name"):
        return ability_link(ability, source_url)
    possibilities = ability.get("possibilities")
    if not isinstance(possibilities, list) or not possibilities:
        return None
    links = [
        ability_link(possibility, source_url)
        for possibility in possibilities
        if isinstance(possibility, dict) and possibility.get("name")
    ]
    if not links:
        return None
    return " / ".join(links)


def _append_party(
    lines: list[str],
    record: dict[str, Any],
    memberships: list[tuple[dict[str, Any], dict[str, Any]]],
    records_by_id: dict[int, dict[str, Any]],
    source_file: str,
    source_url: str,
    *,
    features: frozenset[str] = _DEFAULT_TRAINER_FEATURES,
    references: ReferenceIndex | None = None,
) -> None:
    lines.extend(["## Party", ""])
    families = {family["id"]: family for family, _variant in memberships}
    if not families:
        lines.extend(_party_cards(record["party"], source_url, references))
        return

    tabs: list[tuple[str, dict[str, Any], bool]] = []
    for family in sorted(families.values(), key=lambda value: value["order"]):
        variants = sorted(
            family["variants"],
            key=lambda value: (
                value["trainer_id"] != record["trainer_id"],
                value["order"],
            ),
        )
        for variant in variants:
            candidate = records_by_id.get(variant["trainer_id"])
            if candidate is None or not candidate.get("party"):
                continue
            is_difficulty = any(
                condition["kind"] == "difficulty-mode"
                for condition in variant["conditions"]
            )
            tabs.append(
                (
                    _variant_tab_label(variant, len(tabs) + 1),
                    candidate,
                    is_difficulty,
                )
            )

    prepared_tabs: list[tuple[str, dict[str, Any], list[str]]] = []
    seen_labels: dict[str, int] = {}
    for label, candidate, is_difficulty in tabs:
        seen_labels[label] = seen_labels.get(label, 0) + 1
        tab_label = (
            label if seen_labels[label] == 1 else f"{label} ({seen_labels[label]})"
        )
        presentation = [
            *_variant_battle_details(
                candidate,
                source_url,
                is_difficulty=is_difficulty,
                features=features,
            ),
            *_party_cards(candidate["party"], source_url, references),
        ]
        prepared_tabs.append((tab_label, candidate, presentation))

    if prepared_tabs and all(
        presentation == prepared_tabs[0][2] for _, _, presentation in prepared_tabs
    ):
        selection_links = []
        for tab_label, candidate, _presentation in prepared_tabs:
            route_id = f"trainer-{candidate['trainer_id']:04}"
            selection_links.append(
                ROUTES.markdown_link(
                    entity_reference(
                        "trainer",
                        candidate["trainer_id"],
                        f"{tab_label} ({route_id})",
                        candidate["trainer_id"],
                    ),
                    source_file,
                )
            )
        lines.extend(["Selections: " + " · ".join(selection_links), ""])
        lines.extend(prepared_tabs[0][2])
        return

    content_pairs: list[tuple[str, list[str]]] = []
    for tab_label, candidate, presentation in prepared_tabs:
        route_id = f"trainer-{candidate['trainer_id']:04}"
        record_link = ROUTES.markdown_link(
            entity_reference(
                "trainer",
                candidate["trainer_id"],
                route_id,
                candidate["trainer_id"],
            ),
            source_file,
        )
        content_pairs.append(
            (tab_label, [f"Exact record: {record_link}", "", *presentation])
        )
    lines.extend(content_tabs(content_pairs))


def _variant_battle_details(
    record: dict[str, Any],
    source_url: str,
    *,
    is_difficulty: bool,
    features: frozenset[str],
) -> list[str]:
    facts = []
    if "battle_mode" in record or "double_battle" in record:
        facts.append(
            f"<div><dt>Battle format</dt><dd>{_battle_format_label(record)}</dd></div>"
        )
    facts.extend(
        [
            f"<div><dt>Party size</dt><dd>{len(record['party'])}</dd></div>",
            f"<div><dt>Level range</dt><dd>{_trainer_level_range(record)}</dd></div>",
        ]
    )
    ai_flags = record.get("ai_flags")
    if isinstance(ai_flags, int):
        facts.append(
            f"<div><dt>AI flags</dt><dd><code>0x{ai_flags:08X}</code></dd></div>"
        )
    grouped_items = _group_ai_battle_items(record)
    ai_items = (
        ", ".join(_ai_item_link(grouped, source_url) for grouped in grouped_items)
        or '<span class="rw-summary__empty">None</span>'
    )
    facts.append(f"<div><dt>AI items</dt><dd>{ai_items}</dd></div>")
    base_prize_money = record.get("base_prize_money")
    if base_prize_money:
        facts.append(
            "<div><dt>Base prize money</dt><dd>"
            f"&#8381;{base_prize_money['amount']:,}</dd></div>"
        )
    if POST_BATTLE_HEALING in features:
        result = (
            "Heals the player's party"
            if record.get("healer")
            else '<span class="rw-summary__empty">No healing</span>'
        )
        facts.append(f"<div><dt>After victory</dt><dd>{result}</dd></div>")
    if VICTORY_ITEMS in features:
        victory_item = record.get("victory_item")
        if victory_item:
            result = ROUTES.html_link(
                entity_reference(
                    "item",
                    victory_item["id"],
                    victory_item["name"],
                    victory_item.get("slug"),
                ),
                source_url,
            )
        else:
            result = '<span class="rw-summary__empty">None</span>'
        facts.append(f"<div><dt>Victory item</dt><dd>{result}</dd></div>")
    if is_difficulty:
        facts.append(
            "<div><dt>Level basis</dt><dd>Stored ROM levels"
            '<abbr class="rw-inline-note" title="B2W2 may adjust the displayed '
            "level by difficulty after loading the party; stats still use the "
            'stored level.">*</abbr></dd></div>'
        )
    return summary_section("rw-trainer-variant-summary", facts)


def _variant_tab_label(variant: dict[str, Any], generic_number: int) -> str:
    named_kinds = {
        "starter-choice",
        "difficulty-mode",
        "season",
        "rematch-stage",
        "sibling-version",
    }
    labels = [
        display_name(condition["value"])
        for condition in variant["conditions"]
        if condition["kind"] in named_kinds
    ]
    return " · ".join(labels) if labels else f"Variant {generic_number}"


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


# A nature's raised/lowered stat pair, keyed by name. This is a fixed game
# mechanic identical across every Generation III+ title, not ROM data, so it
# is safe to hardcode rather than decode per-ROM.
_NATURE_STAT_MODIFIERS: dict[str, tuple[str, str] | None] = {
    "Hardy": None,
    "Lonely": ("attack", "defense"),
    "Brave": ("attack", "speed"),
    "Adamant": ("attack", "special_attack"),
    "Naughty": ("attack", "special_defense"),
    "Bold": ("defense", "attack"),
    "Docile": None,
    "Relaxed": ("defense", "speed"),
    "Impish": ("defense", "special_attack"),
    "Lax": ("defense", "special_defense"),
    "Timid": ("speed", "attack"),
    "Hasty": ("speed", "defense"),
    "Serious": None,
    "Jolly": ("speed", "special_attack"),
    "Naive": ("speed", "special_defense"),
    "Modest": ("special_attack", "attack"),
    "Mild": ("special_attack", "defense"),
    "Quiet": ("special_attack", "speed"),
    "Bashful": None,
    "Rash": ("special_attack", "special_defense"),
    "Calm": ("special_defense", "attack"),
    "Gentle": ("special_defense", "defense"),
    "Sassy": ("special_defense", "speed"),
    "Careful": ("special_defense", "special_attack"),
    "Quirky": None,
}

# Row labels that reflect a nature-affected final stat, as opposed to raw
# IVs/EVs, which a nature does not modify.
_CALCULATED_STAT_LABELS = {"Value", "Min", "Max"}


def _nature_stat_modifiers(nature: dict[str, Any] | None) -> tuple[str, str] | None:
    name = (nature or {}).get("name")
    return _NATURE_STAT_MODIFIERS.get(name) if isinstance(name, str) else None


def _stat_cell(key: str, value: Any, modifiers: tuple[str, str] | None) -> str:
    css_class = ""
    if modifiers:
        boosted, lowered = modifiers
        if key == boosted:
            css_class = ' class="rw-party-card__stat--up"'
        elif key == lowered:
            css_class = ' class="rw-party-card__stat--down"'
    return f"<td{css_class}>{_stat_value(value)}</td>"


def _party_stat_table(member: dict[str, Any]) -> list[str]:
    ordered = (
        ("HP", "hp"),
        ("Atk", "attack"),
        ("Def", "defense"),
        ("SpA", "special_attack"),
        ("SpD", "special_defense"),
        ("Spe", "speed"),
    )
    rows: list[tuple[str, dict[str, Any]]] = []
    calculated = member.get("calculated_stats")
    calculated_values = calculated.get("values") if calculated else None
    ranged_stats: list[tuple[str, dict[str, Any]]] = []
    if isinstance(calculated_values, dict) and all(
        key in calculated_values for _, key in ordered
    ):
        if any(_is_stat_range(calculated_values[key]) for _, key in ordered):
            ranged_stats.extend(
                [
                    ("Min", _stat_bounds(calculated_values, ordered, "minimum")),
                    ("Max", _stat_bounds(calculated_values, ordered, "maximum")),
                ]
            )
        else:
            rows.append(("Value", calculated_values))
    for label, field in (("IV", "ivs"), ("EV", "evs")):
        attribute = member.get(field)
        values = attribute.get("values") if attribute else None
        if isinstance(values, dict) and all(key in values for _, key in ordered):
            rows.append((label, values))
    rows.extend(ranged_stats)
    if not rows:
        return []
    nature_modifiers = _nature_stat_modifiers(member.get("nature"))
    return [
        '<table class="rw-party-card__stats">',
        "<caption>Stats, IVs, and EVs</caption>",
        "<thead><tr><th></th>"
        + "".join(f'<th scope="col">{label}</th>' for label, _ in ordered)
        + "</tr></thead>",
        "<tbody>",
        *[
            f'<tr><th scope="row">{label}</th>'
            + "".join(
                _stat_cell(
                    key,
                    values[key],
                    nature_modifiers if label in _CALCULATED_STAT_LABELS else None,
                )
                for _, key in ordered
            )
            + "</tr>"
            for label, values in rows
        ],
        "</tbody>",
        "</table>",
    ]


def _is_stat_range(value: Any) -> bool:
    return isinstance(value, dict) and {"minimum", "maximum"}.issubset(value)


def _stat_bounds(
    values: dict[str, Any],
    ordered: tuple[tuple[str, str], ...],
    bound: str,
) -> dict[str, Any]:
    return {
        key: value[bound] if _is_stat_range(value) else value
        for _, key in ordered
        for value in (values[key],)
    }


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
            "| Location | Map ID | Internal ID | Position | Event |",
            "| -------- | ------ | ----------- | -------- | ----- |",
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
            f"| `header-{location['header_id']:03}` | "
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
            "| Location | Map ID | Internal ID | Script | Opponent |",
            "| -------- | ------ | ----------- | ------ | -------: |",
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
            f"| `header-{reference['header_id']:03}` | "
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
    references: ReferenceIndex | None = None,
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
            "| Trainer | ID | Location | Levels | Party |",
            "| ------- | -: | -------- | -----: | ----- |",
        ]
    )
    for candidate in related:
        trainer_id = candidate["trainer_id"]
        trainer_link = ROUTES.markdown_link(
            entity_reference(
                "trainer", trainer_id, _trainer_label(candidate), trainer_id
            ),
            source_file,
        )
        route_id = f"trainer-{trainer_id:04}"
        locations = _location_links(candidate, source_file)
        lines.append(
            f"| {trainer_link} | `{route_id}` | {' / '.join(locations) or '—'} | "
            f"{_trainer_level_range(candidate)} | "
            f"{_linked_party(candidate, source_file, references)} |"
        )
    lines.append("")
    if collapsed:
        lines.extend(["</details>", ""])


def _trainer_label(record: Mapping[str, Any]) -> str:
    return " ".join(value for value in (record["class_name"], record["name"]) if value)


def _combined_locations(record: dict[str, Any]) -> list[dict[str, Any]]:
    return record["locations"] + record.get("script_references", [])


def _location_names(record: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(location["name"] for location in _combined_locations(record))
    )


def _location_links(record: dict[str, Any], source_file: str) -> list[str]:
    links = []
    seen = set()
    for location in _combined_locations(record):
        header_id = location.get("header_id")
        identity = (header_id, location["name"])
        if identity in seen:
            continue
        seen.add(identity)
        if not isinstance(header_id, int):
            links.append(escape_table_cell(location["name"]))
            continue
        links.append(
            ROUTES.markdown_link(
                entity_reference("location", header_id, location["name"], header_id),
                source_file,
            )
        )
    return links
