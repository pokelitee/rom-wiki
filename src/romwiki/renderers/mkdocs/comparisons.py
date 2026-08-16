from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from romwiki.pipeline.transforms.comparisons import (
    comparison_by_key,
    normalize_comparison_value,
)
from romwiki.pipeline.transforms.relationships import RelationshipIndex
from romwiki.renderers.mkdocs.catalog import write_text
from romwiki.renderers.mkdocs.components import (
    content_tabs,
    display_name,
    empty_state,
    escape_table_cell,
    evolution_condition,
)
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    encounter_route_kind,
    entity_reference,
    escape_markdown,
    resolved_reference,
)


def _diff(before: str, after: str) -> str:
    return f'{before}<span class="rw-diff-arrow">→</span>{after}'


_SECTIONS = {
    "pokemon": "Pokémon",
    "abilities": "Abilities",
    "moves": "Moves",
    "items": "Items",
    "wild_encounters": "Wild encounters",
    "trainers": "Trainers",
    "locations": "Locations",
}

_ROUTE_KINDS = {
    "pokemon": "pokemon",
    "abilities": "ability",
    "moves": "move",
    "items": "item",
    "trainers": "trainer",
    "locations": "location",
}


def record_comparison(
    comparison: dict[str, Any] | None, key: int | str
) -> dict[str, Any] | None:
    return comparison_by_key(comparison).get(key)


def comparison_section(
    entry: dict[str, Any] | None,
    baseline_name: str | None,
    source_file: str = "",
    references: ReferenceIndex | None = None,
    *,
    heading_level: int | None = 2,
) -> list[str]:
    if entry is None:
        return []
    version_comparisons = entry.get("version_comparisons")
    if version_comparisons:
        lines = (
            [f"{'#' * heading_level} Hack changes", ""]
            if heading_level is not None
            else []
        )
        lines.extend(
            content_tabs(
                [
                    (
                        display_name(version),
                        _comparison_body(
                            version_entry,
                            version_entry.get("baseline") or baseline_name,
                            source_file,
                            references,
                        ),
                    )
                    for version, version_entry in version_comparisons.items()
                ]
            )
        )
        return lines
    return [
        *(
            [f"{'#' * heading_level} Hack changes", ""]
            if heading_level is not None
            else []
        ),
        *_comparison_body(entry, baseline_name, source_file, references),
    ]


def grouped_comparison_section(
    entries: list[tuple[str, dict[str, Any] | None]],
    baseline_name: str | None,
    source_file: str = "",
    references: ReferenceIndex | None = None,
) -> list[str]:
    available = [(label, entry) for label, entry in entries if entry is not None]
    if not available:
        return []
    if len(available) == 1:
        return comparison_section(
            available[0][1], baseline_name, source_file, references
        )
    lines = ["## Hack changes", ""]
    for label, entry in available:
        lines.extend([f"### {label}", ""])
        lines.extend(
            comparison_section(
                entry,
                baseline_name,
                source_file,
                references,
                heading_level=None,
            )
        )
    return lines


def _comparison_body(
    entry: dict[str, Any],
    baseline_name: str | None,
    source_file: str,
    references: ReferenceIndex | None,
) -> list[str]:
    baseline = baseline_name or "the clean base game"
    status = entry["status"]
    if status == "unchanged":
        return [
            f"Verified unchanged from **{escape_markdown(baseline)}** for all compared fields.",
            "",
        ]
    if status == "added":
        return [
            '!!! success "Added in this hack"',
            f"    This record was added and does not exist in **{escape_markdown(baseline)}**.",
            "",
        ]
    if status == "removed":
        return [
            '!!! warning "Removed in this hack"',
            f"    This record exists in **{escape_markdown(baseline)}** but not in this hack.",
            "",
        ]
    change_count = len(entry["changes"])
    noun = "field changed" if change_count == 1 else "fields changed"
    lines = [
        f"Compared with **{escape_markdown(baseline)}**.",
        "",
        '<details markdown="1">',
        f"<summary>{change_count} {noun}</summary>",
        "",
        '<div class="rw-changes">',
    ]
    for change in entry["changes"]:
        value = _format_change(
            change,
            entry.get("kind"),
            source_file.removesuffix(".md") + ("/" if source_file else ""),
            references,
        )
        label = escape(str(change["label"]))
        lines.extend(
            [
                '<section class="rw-change">',
                f'<p class="rw-change__field">{label}</p>',
                f'<div class="rw-change__value">{value}</div>',
                "</section>",
            ]
        )
    lines.extend(["</div>", "", "</details>", ""])
    return lines


def add_change_status(
    catalog_record: dict[str, Any], entry: dict[str, Any] | None
) -> dict[str, Any]:
    if entry is not None:
        catalog_record["change_status"] = entry["status"]
    return catalog_record


def render_changes_pages(
    comparisons: dict[str, dict[str, Any]],
    output_root: Path,
    relationships: RelationshipIndex | None = None,
) -> int:
    changes_root = output_root / "changes"
    changes_root.mkdir(parents=True, exist_ok=True)
    if not comparisons:
        for path in changes_root.rglob("*.md"):
            if path.name != "index.md":
                path.unlink()
        for directory in sorted(
            (path for path in changes_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()
        write_text(
            changes_root / "index.md",
            "# Changes from base game\n\n"
            "This wiki was generated without a clean-ROM comparison.\n",
        )
        return 1
    lines = [
        "# Changes from base game",
        "",
        "Every supported ROM dataset is compared with the configured clean base ROM. "
        "Unchanged records remain visible on their detail pages.",
        "",
        "| Section | Unchanged | Changed | Added | Removed |",
        "| ------- | --------: | ------: | ----: | ------: |",
    ]
    total_pages = 1
    removed_paths = set()
    for comparison in comparisons.values():
        kind = comparison["kind"]
        counts = comparison["counts"]
        lines.append(
            f"| [{_SECTIONS[kind]}](#{kind.replace('_', '-')}) | "
            f"{counts['unchanged']} | {counts['changed']} | "
            f"{counts['added']} | {counts['removed']} |"
        )
    lines.append("")
    for comparison in comparisons.values():
        kind = comparison["kind"]
        changed = [
            record
            for record in comparison["records"]
            if record["status"] != "unchanged"
        ]
        lines.extend([f"## {_SECTIONS[kind]}", ""])
        if not changed:
            lines.extend(empty_state("All compared records are unchanged."))
            continue
        lines.extend(
            [
                "| Record | Status | Changed fields |",
                "| ------ | ------ | -------------- |",
            ]
        )
        for record in changed:
            href = _change_href(kind, record)
            label = escape_markdown(_change_record_label(kind, record, relationships))
            record_cell = f"[{label}]({href})" if href else label
            labels = ", ".join(change["label"] for change in record["changes"])
            lines.append(
                f"| {record_cell} | {record['status'].title()} | {labels or '—'} |"
            )
            if record["status"] == "removed":
                removed_paths.add(Path(kind) / f"{_removed_slug(record)}.md")
                _render_removed_page(comparison, record, changes_root)
                total_pages += 1
        lines.append("")
    for path in changes_root.rglob("*.md"):
        relative = path.relative_to(changes_root)
        if relative != Path("index.md") and relative not in removed_paths:
            path.unlink()
    write_text(changes_root / "index.md", "\n".join(lines))
    return total_pages


def _change_record_label(
    kind: str,
    record: dict[str, Any],
    relationships: RelationshipIndex | None,
) -> str:
    if kind != "wild_encounters" or relationships is None:
        return record["label"]
    route_key = record.get("slug") or record["key"]
    locations = relationships.encounter_locations.get(route_key, ())
    names = list(dict.fromkeys(location.location_name for location in locations))
    return " / ".join(names) or record["label"]


def _change_href(kind: str, record: dict[str, Any]) -> str | None:
    if record["status"] == "removed":
        return f"{kind}/{_removed_slug(record)}.md"
    if not record.get("detail_available", True):
        return None
    route_key = record.get("slug") or record["key"]
    route_kind = (
        encounter_route_kind(route_key)
        if kind == "wild_encounters"
        else _ROUTE_KINDS[kind]
    )
    reference = entity_reference(
        route_kind,
        record["key"],
        record["label"],
        route_key,
    )
    return ROUTES.markdown_href(reference, "changes/index.md") or "#"


def _render_removed_page(
    comparison: dict[str, Any], record: dict[str, Any], changes_root: Path
) -> None:
    path = changes_root / comparison["kind"] / f"{_removed_slug(record)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = record["baseline_record"]
    lines = [
        f"# {record['label']}",
        "",
        '!!! warning "Removed in this hack"',
        f"    This record exists in **{comparison['baseline']}** but not in "
        f"**{comparison['game']}**.",
        "",
        "## Base-game snapshot",
        "",
    ]
    for field, value in snapshot.items():
        lines.extend(
            [
                f"### {field.replace('_', ' ').title()}",
                "",
                _format_value(value),
                "",
            ]
        )
    write_text(path, "\n".join(lines))


def _removed_slug(record: dict[str, Any]) -> str:
    return str(record.get("slug") or f"record-{record['key']}")


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if isinstance(value, str):
        return escape_table_cell(value) or "—"
    if isinstance(value, (int, float)):
        return str(value)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    exact = escape_table_cell(encoded)
    if isinstance(value, dict):
        summary = escape_table_cell(_mapping_summary(value))
        return (
            f"{summary}<details><summary>Exact data</summary>"
            f"<code>{exact}</code></details>"
        )
    return f"<code>{exact}</code>"


def _format_change(
    change: dict[str, Any],
    kind: str | None = None,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    before = change["before"]
    after = change["after"]
    if kind == "pokemon":
        specialized = _format_pokemon_change(change, source_url, references)
        if specialized is not None:
            return specialized
    if kind == "abilities" and change.get("field") == "pokemon":
        return _format_ability_pokemon_change(before, after, source_url, references)
    if kind == "trainers" and change.get("field") == "battle_mode":
        labels = ("Single", "Double", "Triple", "Rotation")
        old_label = (
            labels[before] if isinstance(before, int) and 0 <= before < 4 else before
        )
        new_label = (
            labels[after] if isinstance(after, int) and 0 <= after < 4 else after
        )
        return _format_value_change(old_label, new_label)
    if kind == "trainers" and change.get("field") in {"locations", "script_references"}:
        return _format_trainer_location_change(before, after, source_url, references)
    return _format_value_change(
        before,
        after,
        kind=kind,
        field=change.get("field"),
        source_url=source_url,
        references=references,
    )


def _format_value_change(
    old_value: Any,
    new_value: Any,
    *,
    kind: str | None = None,
    field: str | None = None,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    """Shared recursive formatter for a single field's before/after values.

    Used both at the top level (after the kind-specific specializations in
    ``_format_change`` have had a chance to run) and recursively for nested
    fields inside ``_format_mapping_change`` — so a dict-of-dicts or
    dict-of-lists (e.g. wild encounters' "special.dual_slot") gets the same
    treatment at every level instead of falling back to a raw Python repr.
    """
    named_reference = _format_named_reference_change(old_value, new_value)
    if named_reference is not None:
        return named_reference
    if isinstance(old_value, dict) and isinstance(new_value, dict):
        return _format_mapping_change(
            old_value,
            new_value,
            kind=kind,
            source_url=source_url,
            references=references,
        )
    if isinstance(old_value, list) and isinstance(new_value, list):
        return _format_list_change(
            old_value,
            new_value,
            kind=kind,
            field=field,
            source_url=source_url,
            references=references,
        )
    return _diff(_format_value(old_value), _format_value(new_value))


def _format_named_reference_change(before: Any, after: Any) -> str | None:
    """Render a change to a simple ``{id, name}`` enum reference as one diff.

    Fields like growth_rate/body_color/damage_class/type/pocket/field_use/
    natural_gift_type are ROM-derived ``{"id": int, "name": str}`` lookups
    (see ``_named_id``/``_type_id`` in enrich.py and the equivalent item
    pipeline dict literals). Diffing them key-by-key produces a redundant
    "Id: 2 → 3" line alongside "Name: A → B" for what is really one change;
    this collapses both into a single name-to-name diff. A field can also go
    from ``None`` to populated (e.g. an item gaining a Natural Gift type), so
    both sides are optional.
    """

    def is_reference_like(value: Any) -> bool:
        return value is None or (
            isinstance(value, dict) and "name" in value and set(value) <= {"id", "name"}
        )

    if not is_reference_like(before) or not is_reference_like(after):
        return None
    if before is None and after is None:
        return None
    before_label = (
        display_name(before["name"])
        if isinstance(before, dict) and before.get("name")
        else "—"
    )
    after_label = (
        display_name(after["name"])
        if isinstance(after, dict) and after.get("name")
        else "—"
    )
    return _diff(escape(before_label), escape(after_label))


def _format_list_change(
    before: list[Any],
    after: list[Any],
    *,
    kind: str | None = None,
    field: str | None = None,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    keyed_before = _keyed_records(before)
    keyed_after = _keyed_records(after)
    if keyed_before is not None and keyed_after is not None:
        return _format_keyed_list_change(
            keyed_before,
            keyed_after,
            source_url=source_url,
            references=references,
        )
    before_values = {
        _canonical(normalize_comparison_value(item, kind=kind, field=field)): item
        for item in before
    }
    after_values = {
        _canonical(normalize_comparison_value(item, kind=kind, field=field)): item
        for item in after
    }
    removed = [before_values[key] for key in before_values.keys() - after_values.keys()]
    added = [after_values[key] for key in after_values.keys() - before_values.keys()]
    if not removed and not added:
        return f"Order changed ({len(before)} entries)"
    return _format_set_delta(
        removed, added, source_url=source_url, references=references
    )


def _format_set_delta(
    removed: list[Any],
    added: list[Any],
    *,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    groups = []
    for label, values in (("removed", removed), ("added", added)):
        if values:
            groups.append(
                (
                    f"entry {label}",
                    f"entries {label}",
                    [
                        _format_value_summary(
                            value, source_url=source_url, references=references
                        )
                        for value in sorted(values, key=_canonical)
                    ],
                )
            )
    return _format_change_groups(groups)


def _keyed_records(values: list[Any]) -> dict[Any, dict[str, Any]] | None:
    if not values or not all(isinstance(value, dict) for value in values):
        return None
    result: dict[Any, dict[str, Any]] = {}
    for value in values:
        if "command_offset" in value:
            key = (
                value.get("kind"),
                value.get("inventory_id"),
                value.get("script_file_id"),
                value["command_offset"],
            )
        elif "item_id" in value:
            key = ("item_id", value["item_id"])
        else:
            return None
        if key in result:
            return None
        result[key] = value
    return result


def _format_keyed_list_change(
    before: dict[Any, dict[str, Any]],
    after: dict[Any, dict[str, Any]],
    *,
    nested: bool = False,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    changed, removed, added = [], [], []
    for key in sorted(set(before) | set(after), key=str):
        old, new = before.get(key), after.get(key)
        if old is None:
            added.append(
                _format_value_summary(new, source_url=source_url, references=references)
            )
        elif new is None:
            removed.append(
                _format_value_summary(old, source_url=source_url, references=references)
            )
        elif old != new:
            changed.append(
                f"{_format_value_summary(new, source_url=source_url, references=references)}: "
                f"{_format_mapping_change(old, new, nested=True, source_url=source_url, references=references)}"
            )
    groups = [
        ("entry changed", "entries changed", changed),
        ("entry removed", "entries removed", removed),
        ("entry added", "entries added", added),
    ]
    if nested:
        return _format_plain_change_groups(groups)
    return _format_change_groups(groups)


def _format_value_summary(
    value: Any,
    *,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    """Render a per-item change-list value without a raw JSON dump.

    Every candidate here already has a readable label (from
    ``_mapping_summary``) and, in practice, its own detail page — the "Exact
    data" JSON dump ``_format_value`` adds for dicts is reserved for the
    standalone removed-record snapshot page, where there is no better
    alternative and no detail page to link to instead.
    """
    if isinstance(value, dict):
        pokemon = value.get("pokemon")
        if isinstance(pokemon, dict) and pokemon.get("name"):
            return _reference_html(
                pokemon, "pokemon", source_url, references
            ) + _level_suffix(value)
        move = value.get("move")
        if isinstance(move, dict) and move.get("name"):
            return _reference_html(
                move, "move", source_url, references
            ) + _level_suffix(value)
        target = value.get("target")
        if isinstance(target, dict) and target.get("name"):
            method = value.get("method")
            method_name = method.get("name") if isinstance(method, dict) else method
            suffix = f" — {escape(str(method_name))}" if method_name else ""
            return _reference_html(target, "pokemon", source_url, references) + suffix
        return escape_table_cell(_mapping_summary(value))
    return _format_value(value)


def _format_pokemon_change(
    change: dict[str, Any],
    source_url: str,
    references: ReferenceIndex | None,
) -> str | None:
    field = change["field"]
    before = change["before"]
    after = change["after"]
    if field == "abilities":
        return _format_slots(
            before, after, "Ability slot", "ability", source_url, references
        )
    if field == "types":
        return _format_slots(before, after, "Type slot")
    if field == "machines":
        return _format_machine_compatibility(before, after, source_url, references)
    if field == "egg_moves":
        return _format_compatibility(
            before, after, _record_identity, source_url, references
        )
    if field == "tutor_moves":
        return _format_compatibility(
            before, after, _tutor_identity, source_url, references
        )
    if field == "level_up_moves":
        return _format_level_up_moves(before, after, source_url, references)
    if field == "evolutions":
        return _format_evolutions(before, after, source_url, references)
    if field == "held_items":
        return _format_held_items_change(before, after, source_url, references)
    if field in {"base_stats", "ev_yields"}:
        return _format_mapping_change(before, after, kind="pokemon")
    return None


def _format_ability_pokemon_change(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {item["member"]: {**item, "id": item["member"]} for item in before}
    current = {item["member"]: {**item, "id": item["member"]} for item in after}
    changed = []
    removed = []
    added = []
    for member in sorted(set(previous) | set(current)):
        old = previous.get(member)
        new = current.get(member)
        if old is not None and new is not None:
            if old["slots"] == new["slots"]:
                continue
            display = _reference_html(old, "pokemon", source_url, references)
            changed.append(
                f"{display}: "
                f"{_diff(_ability_slot_label(old['slots']), _ability_slot_label(new['slots']))}"
            )
        elif old is not None:
            removed.append(_reference_html(old, "pokemon", source_url, references))
        else:
            added.append(_reference_html(new, "pokemon", source_url, references))
    groups = [
        ("ability slot change", "ability slot changes", changed),
        (
            "Pokémon that lost this ability",
            "Pokémon that lost this ability",
            removed,
        ),
        (
            "Pokémon that gained this ability",
            "Pokémon that gained this ability",
            added,
        ),
    ]
    return _finalize_change_groups(groups)


def _format_held_items_change(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {item["rarity"]: item for item in before}
    current = {item["rarity"]: item for item in after}
    lines = []
    for rarity in sorted(set(previous) | set(current)):
        old = previous.get(rarity)
        new = current.get(rarity)
        if _reference_id(old) == _reference_id(new):
            continue
        old_label = _reference_html(old, "item", source_url, references)
        new_label = _reference_html(new, "item", source_url, references)
        lines.append(f"{rarity.title()} held item: {_diff(old_label, new_label)}")
    return _format_lines(lines, True)


def _format_trainer_location_change(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {_trainer_location_identity(item): item for item in before}
    current = {_trainer_location_identity(item): item for item in after}
    changed = []
    removed = []
    added = []
    for key in sorted(set(previous) | set(current), key=str):
        old = previous.get(key)
        new = current.get(key)
        if old is not None and new is not None:
            old_position = (old.get("x"), old.get("z"))
            new_position = (new.get("x"), new.get("z"))
            if old_position == new_position:
                continue
            display = _reference_html(
                {**old, "id": old.get("header_id")}, "location", source_url, references
            )
            changed.append(f"{display}: {_diff(str(old_position), str(new_position))}")
        elif old is not None:
            removed.append(
                _reference_html(
                    {**old, "id": old.get("header_id")},
                    "location",
                    source_url,
                    references,
                )
            )
        else:
            added.append(
                _reference_html(
                    {**new, "id": new.get("header_id")},
                    "location",
                    source_url,
                    references,
                )
            )
    groups = [
        ("position change", "position changes", changed),
        ("location removed", "locations removed", removed),
        ("location added", "locations added", added),
    ]
    return _finalize_change_groups(groups)


def _trainer_location_identity(value: dict[str, Any]) -> Any:
    return (
        value.get("header_id"),
        value.get("object_index"),
        value.get("event_file_id"),
    )


def _ability_slot_label(slots: list[int]) -> str:
    if not slots:
        return "Not assigned"
    label = "Slot" if len(slots) == 1 else "Slots"
    return f"{label} {', '.join(str(slot) for slot in slots)}"


def _format_slots(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    label: str,
    reference_kind: str | None = None,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    lines = []
    for index in range(max(len(before), len(after))):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        if _reference_id(old) == _reference_id(new):
            continue
        old_label = _reference_html(old, reference_kind, source_url, references)
        new_label = _reference_html(new, reference_kind, source_url, references)
        lines.append(f"{label} {index + 1}: {_diff(old_label, new_label)}")
    return _format_lines(lines, True)


def _format_compatibility(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    identity: Any,
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {identity(item): item for item in before}
    current = {identity(item): item for item in after}
    lines = []
    for key in sorted(set(previous) | set(current), key=str):
        old = previous.get(key)
        new = current.get(key)
        if old is not None and new is not None:
            continue
        value = old or new
        move = value.get("move") if isinstance(value, dict) else None
        display = _reference_html(move or value, "move", source_url, references)
        old_state = "Compatible" if old else "Not compatible"
        new_state = "Compatible" if new else "Not compatible"
        lines.append(f"{display}: {_diff(old_state, new_state)}")
    return _format_lines(lines, True)


def _format_level_up_moves(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = _level_moves_by_id(before)
    current = _level_moves_by_id(after)
    changed = []
    removed = []
    added = []
    move_ids = list(
        dict.fromkeys(
            [entry["move"]["id"] for entry in before]
            + [entry["move"]["id"] for entry in after]
        )
    )
    for move_id in move_ids:
        old = previous.get(move_id)
        new = current.get(move_id)
        old_levels = tuple(old["levels"]) if old else ()
        new_levels = tuple(new["levels"]) if new else ()
        if old_levels == new_levels:
            continue
        display = _reference_html(old or new, "move", source_url, references)
        line = f"{display}: {_diff(_level_label(old_levels), _level_label(new_levels))}"
        if old and new:
            changed.append(line)
        elif old:
            removed.append(line)
        else:
            added.append(line)
    groups = [
        ("level change", "level changes", changed),
        ("move removed", "moves removed", removed),
        ("move added", "moves added", added),
    ]
    return _finalize_change_groups(groups)


def _format_evolutions(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {entry["target"]["id"]: entry for entry in before}
    current = {entry["target"]["id"]: entry for entry in after}
    changed = []
    removed = []
    added = []
    target_ids = list(dict.fromkeys(list(previous) + list(current)))
    for target_id in target_ids:
        old = previous.get(target_id)
        new = current.get(target_id)
        display = _reference_html(
            (old or new)["target"], "pokemon", source_url, references
        )
        if old is not None and new is not None:
            old_condition = evolution_condition(old, source_url, references)
            new_condition = evolution_condition(new, source_url, references)
            if old_condition == new_condition:
                continue
            changed.append(f"{display}: {_diff(old_condition, new_condition)}")
        elif old is not None:
            removed.append(
                f"{display}: {evolution_condition(old, source_url, references)}"
            )
        else:
            added.append(
                f"{display}: {evolution_condition(new, source_url, references)}"
            )
    groups = [
        ("evolution change", "evolution changes", changed),
        ("evolution removed", "evolutions removed", removed),
        ("evolution added", "evolutions added", added),
    ]
    return _finalize_change_groups(groups)


def _level_moves_by_id(moves: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for entry in moves:
        move = entry["move"]
        value = result.setdefault(
            move["id"],
            {
                "id": move["id"],
                "name": move["name"],
                "slug": move.get("slug"),
                "levels": [],
            },
        )
        value["levels"].append(entry["level"])
    return result


def _level_label(levels: tuple[int, ...]) -> str:
    if not levels:
        return "Not learned"
    return ", ".join(f"Lv. {level}" for level in levels)


def _format_mapping_change(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    kind: str | None = None,
    nested: bool = False,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> str:
    lines = []
    for key in sorted(before.keys() | after.keys()):
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value == new_value:
            continue
        label = escape(key.replace("_", " ").title())
        if isinstance(old_value, list) and isinstance(new_value, list):
            keyed_before = _keyed_records(old_value)
            keyed_after = _keyed_records(new_value)
            if keyed_before is not None and keyed_after is not None:
                value = _format_keyed_list_change(
                    keyed_before,
                    keyed_after,
                    nested=nested,
                    source_url=source_url,
                    references=references,
                )
            else:
                value = _format_value_change(
                    old_value,
                    new_value,
                    kind=kind,
                    field=key,
                    source_url=source_url,
                    references=references,
                )
        else:
            value = _format_value_change(
                old_value,
                new_value,
                kind=kind,
                field=key,
                source_url=source_url,
                references=references,
            )
        lines.append(f"{label}: {value}")
    return _format_lines(lines, True) if not nested else _format_plain_lines(lines)


def _format_lines(values: list[str], trusted: bool = False) -> str:
    if not values:
        return "No changes"
    rendered = [value if trusted else escape_table_cell(value) for value in values]
    return _format_collection(rendered, "change", "changes")


def _format_plain_lines(values: list[str]) -> str:
    if not values:
        return "No changes"
    return (
        '<ul class="rw-comparison-list">'
        + "".join(f"<li>{value}</li>" for value in values)
        + "</ul>"
    )


def _format_collection(values: list[str], singular: str, plural: str) -> str:
    if not values:
        return "No changes"
    label = singular if len(values) == 1 else plural
    entries = "".join(f"<li>{value}</li>" for value in values)
    return (
        f'<p class="rw-comparison-count">{len(values)} {label}</p>'
        f'<ul class="rw-comparison-list">{entries}</ul>'
    )


def _format_change_groups(
    groups: list[tuple[str, str, list[str]]],
) -> str:
    parts = []
    for singular, plural, values in groups:
        if not values:
            continue
        parts.append(_format_collection(values, singular, plural))
    return "".join(parts) or "No changes"


def _finalize_change_groups(groups: list[tuple[str, str, list[str]]]) -> str:
    """Render the changed/removed/added buckets a per-field diff formatter
    built, or report an unchanged-but-reordered collection when every
    bucket ended up empty (every key matched, nothing to report, but the
    two lists weren't `==` -- the only way to reach here with no changes).
    """
    groups = [group for group in groups if group[2]]
    if not groups:
        return "Order changed"
    return _format_change_groups(groups)


def _format_plain_change_groups(
    groups: list[tuple[str, str, list[str]]],
) -> str:
    parts = []
    for singular, plural, values in groups:
        if not values:
            continue
        label = singular if len(values) == 1 else plural
        entries = "".join(f"<li>{value}</li>" for value in values)
        parts.append(
            f"<strong>{escape(label[:1].upper() + label[1:])}:</strong>"
            f'<ul class="rw-comparison-list">{entries}</ul>'
        )
    return "".join(parts) or "No changes"


def _level_suffix(value: dict[str, Any]) -> str:
    if value.get("level") is not None:
        return f" — Lv. {value['level']}"
    minimum = value.get("minimum_level")
    maximum = value.get("maximum_level")
    if minimum is not None and maximum is not None:
        return (
            f" — Lv. {minimum}" if minimum == maximum else f" — Lv. {minimum}–{maximum}"
        )
    return ""


def _mapping_summary(value: dict[str, Any]) -> str:
    pokemon = value.get("pokemon")
    if isinstance(pokemon, dict) and pokemon.get("name"):
        return f"{pokemon['name']}{_level_suffix(value)}"
    move = value.get("move")
    if isinstance(move, dict) and move.get("name"):
        return f"{move['name']}{_level_suffix(value)}"
    target = value.get("target")
    if isinstance(target, dict) and target.get("name"):
        method = value.get("method")
        method_name = method.get("name") if isinstance(method, dict) else method
        suffix = f" — {method_name}" if method_name else ""
        return f"{target['name']}{suffix}"
    if value.get("name"):
        return str(value["name"])
    location = value.get("location")
    if isinstance(location, dict) and location.get("name"):
        return str(location["name"])
    identifiers = [
        f"{key.replace('_', ' ').title()}: {item}"
        for key, item in value.items()
        if key == "id" or key.endswith("_id")
    ]
    return ", ".join(identifiers) or "Structured value"


def _reference_id(value: dict[str, Any] | None) -> Any:
    return value.get("id") if value else None


def _machine_label(
    value: dict[str, Any],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    move = value.get("move") or {}
    machine = escape(str(value.get("name", "Machine")))
    return f"{machine} — {_reference_html(move, 'move', source_url, references)}"


def _format_machine_compatibility(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    previous = {_record_identity(item): item for item in before}
    current = {_record_identity(item): item for item in after}
    lines = []
    for key in sorted(set(previous) | set(current)):
        old = previous.get(key)
        new = current.get(key)
        if old is not None and new is not None:
            continue
        label = _machine_label(old or new, source_url, references)
        if old is not None:
            lines.append(f"{label}: {_diff('Compatible', 'Not compatible')}")
        else:
            lines.append(f"{label}: {_diff('Not compatible', 'Compatible')}")
    return _format_lines(lines, True)


def _record_identity(value: dict[str, Any]) -> Any:
    return value.get("id")


def _tutor_identity(value: dict[str, Any]) -> Any:
    return (value.get("move") or {}).get("id")


def _reference_html(
    value: dict[str, Any] | None,
    kind: str | None,
    source_url: str,
    references: ReferenceIndex | None,
) -> str:
    if not value or not value.get("name"):
        return "None"
    name = str(value["name"])
    if kind is None:
        return escape(name)
    identifier = value.get("id", value.get("slug", name))
    return ROUTES.html_link(
        resolved_reference(
            kind,
            identifier,
            name,
            value.get("slug"),
            index=references,
        ),
        source_url,
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
