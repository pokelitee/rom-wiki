from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from romwiki.pipeline.comparisons import (
    comparison_by_key,
    normalize_comparison_value,
)
from romwiki.renderers.mkdocs.catalog import write_text
from romwiki.renderers.mkdocs.references import (
    ROUTES,
    ReferenceIndex,
    entity_reference,
    escape_markdown,
    resolved_reference,
)


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
    "wild_encounters": "encounter",
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
) -> list[str]:
    if entry is None:
        return []
    baseline = baseline_name or "the clean base game"
    status = entry["status"]
    lines = ["## Changes from base game", ""]
    if status == "unchanged":
        return [
            *lines,
            f"Verified unchanged from **{escape(baseline)}** for all compared fields.",
            "",
        ]
    if status == "added":
        return [
            *lines,
            f"This record was added and does not exist in **{escape(baseline)}**.",
            "",
        ]
    if status == "removed":
        return [
            *lines,
            f"This record exists in **{escape(baseline)}** but not in this hack.",
            "",
        ]
    lines.extend(
        [
            f"Compared with **{escape(baseline)}**.",
            "",
            '<div class="rw-catalog__table-wrap" markdown="1">',
            "",
            "| Field | Base game | This game |",
            "| ----- | --------- | --------- |",
        ]
    )
    for change in entry["changes"]:
        before, after = _format_change(
            change,
            entry.get("kind"),
            source_file.removesuffix(".md") + ("/" if source_file else ""),
            references,
        )
        lines.append(
            f"| {escape(str(change['label']))} | "
            f"{before} | {after} |"
        )
    lines.extend(["", "</div>", ""])
    return lines


def add_change_status(
    catalog_record: dict[str, Any], entry: dict[str, Any] | None
) -> dict[str, Any]:
    if entry is not None:
        catalog_record["change_status"] = entry["status"]
    return catalog_record


def render_changes_pages(
    comparisons: dict[str, dict[str, Any]], output_root: Path
) -> int:
    changes_root = output_root / "changes"
    changes_root.mkdir(parents=True, exist_ok=True)
    if not comparisons:
        for path in changes_root.rglob("*.md"):
            if path.name != "index.md":
                path.unlink()
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
            lines.extend(["All compared records are unchanged.", ""])
            continue
        lines.extend(
            [
                "| Record | Status | Changed fields |",
                "| ------ | ------ | -------------- |",
            ]
        )
        for record in changed:
            href = _change_href(kind, record)
            label = escape_markdown(record["label"])
            record_cell = f"[{label}]({href})" if href else label
            labels = ", ".join(change["label"] for change in record["changes"])
            lines.append(
                f"| {record_cell} | "
                f"{record['status'].title()} | {labels or '—'} |"
            )
            if record["status"] == "removed":
                removed_paths.add(
                    Path(kind) / f"{_removed_slug(record)}.md"
                )
                _render_removed_page(comparison, record, changes_root)
                total_pages += 1
        lines.append("")
    for path in changes_root.rglob("*.md"):
        relative = path.relative_to(changes_root)
        if relative != Path("index.md") and relative not in removed_paths:
            path.unlink()
    write_text(changes_root / "index.md", "\n".join(lines))
    return total_pages


def _change_href(kind: str, record: dict[str, Any]) -> str | None:
    if record["status"] == "removed":
        return f"{kind}/{_removed_slug(record)}.md"
    if not record.get("detail_available", True):
        return None
    reference = entity_reference(
        _ROUTE_KINDS[kind], record["key"], record["label"], record.get("slug") or record["key"]
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
        "!!! warning \"Removed in this hack\"",
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
        return escape(value).replace("|", "&#124;") or "—"
    if isinstance(value, (int, float)):
        return str(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    exact = escape(encoded).replace("|", "&#124;")
    if isinstance(value, dict):
        summary = escape(_mapping_summary(value)).replace("|", "&#124;")
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
) -> tuple[str, str]:
    before = change["before"]
    after = change["after"]
    if kind == "pokemon":
        specialized = _format_pokemon_change(change, source_url, references)
        if specialized is not None:
            return specialized
    if isinstance(before, dict) and isinstance(after, dict):
        return _format_mapping_change(before, after)
    if not isinstance(before, list) or not isinstance(after, list):
        return _format_value(before), _format_value(after)
    field = change.get("field")
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
        return (
            f"Order changed ({len(before)} entries)",
            f"Order changed ({len(after)} entries)",
        )
    return _format_delta("removed", removed), _format_delta("added", added)


def _format_pokemon_change(
    change: dict[str, Any],
    source_url: str,
    references: ReferenceIndex | None,
) -> tuple[str, str] | None:
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
        return _format_machine_compatibility(
            before, after, source_url, references
        )
    if field == "egg_moves":
        return _format_compatibility(
            before, after, _move_identity, source_url, references
        )
    if field == "tutor_moves":
        return _format_compatibility(
            before, after, _tutor_identity, source_url, references
        )
    if field == "level_up_moves":
        return _format_level_up_moves(before, after, source_url, references)
    if field in {"base_stats", "ev_yields"}:
        return _format_mapping_change(before, after)
    return None


def _format_slots(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    label: str,
    reference_kind: str | None = None,
    source_url: str = "",
    references: ReferenceIndex | None = None,
) -> tuple[str, str]:
    previous = []
    current = []
    for index in range(max(len(before), len(after))):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        if _reference_id(old) == _reference_id(new):
            continue
        old_label = _reference_html(old, reference_kind, source_url, references)
        new_label = _reference_html(new, reference_kind, source_url, references)
        previous.append(f"{label} {index + 1}: {old_label}")
        current.append(f"{label} {index + 1}: {new_label}")
    trusted = reference_kind is not None
    return _format_lines(previous, trusted), _format_lines(current, trusted)


def _format_compatibility(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    identity: Any,
    source_url: str,
    references: ReferenceIndex | None,
) -> tuple[str, str]:
    previous = {identity(item): item for item in before}
    current = {identity(item): item for item in after}
    old_lines = []
    new_lines = []
    for key in sorted(set(previous) | set(current), key=str):
        old = previous.get(key)
        new = current.get(key)
        if old is not None and new is not None:
            continue
        value = old or new
        move = value.get("move") if isinstance(value, dict) else None
        display = _reference_html(
            move or value, "move", source_url, references
        )
        old_lines.append(f"{display}: {'Compatible' if old else 'Not compatible'}")
        new_lines.append(f"{display}: {'Compatible' if new else 'Not compatible'}")
    return _format_lines(old_lines, True), _format_lines(new_lines, True)


def _format_level_up_moves(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    source_url: str,
    references: ReferenceIndex | None,
) -> tuple[str, str]:
    previous = _level_moves_by_id(before)
    current = _level_moves_by_id(after)
    changed_old = []
    changed_new = []
    removed_old = []
    removed_new = []
    added_old = []
    added_new = []
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
        old_name = _reference_html(old or new, "move", source_url, references)
        new_name = _reference_html(new or old, "move", source_url, references)
        old_line = f"{old_name}: {_level_label(old_levels)}"
        new_line = f"{new_name}: {_level_label(new_levels)}"
        if old and new:
            changed_old.append(old_line)
            changed_new.append(new_line)
        elif old:
            removed_old.append(old_line)
            removed_new.append(new_line)
        else:
            added_old.append(old_line)
            added_new.append(new_line)
    groups = [
        ("level changes", changed_old, changed_new),
        ("moves removed", removed_old, removed_new),
        ("moves added", added_old, added_new),
    ]
    groups = [group for group in groups if group[1]]
    if not groups:
        return "Order changed", "Order changed"
    return _format_change_groups(
        groups, side=1, trusted=True
    ), _format_change_groups(groups, side=2, trusted=True)


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
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[str, str]:
    old_lines = []
    new_lines = []
    for key in sorted(before.keys() | after.keys()):
        if before.get(key) == after.get(key):
            continue
        label = key.replace("_", " ").title()
        old_lines.append(f"{label}: {_plain_value(before.get(key))}")
        new_lines.append(f"{label}: {_plain_value(after.get(key))}")
    return _format_lines(old_lines), _format_lines(new_lines)


def _format_lines(values: list[str], trusted: bool = False) -> str:
    if not values:
        return "No changes"
    if len(values) == 1:
        return values[0] if trusted else escape(values[0]).replace("|", "&#124;")
    return '<ul class="rw-comparison-list">' + "".join(
        f"<li>{value if trusted else escape(value).replace('|', '&#124;')}</li>"
        for value in values
    ) + "</ul>"


def _format_change_groups(
    groups: list[tuple[str, list[str], list[str]]],
    *,
    side: int,
    trusted: bool = False,
) -> str:
    values = []
    for label, previous, current in groups:
        lines = previous if side == 1 else current
        count = len(lines)
        entries = "".join(
            f"<li>{line if trusted else escape(line)}</li>" for line in lines
        )
        values.append(
            f"<details><summary>{count} {label}</summary>"
            f'<ul class="rw-comparison-list">{entries}</ul></details>'
        )
    return "".join(values)


def _mapping_summary(value: dict[str, Any]) -> str:
    pokemon = value.get("pokemon")
    if isinstance(pokemon, dict) and pokemon.get("name"):
        level = f" — Lv. {value['level']}" if value.get("level") is not None else ""
        return f"{pokemon['name']}{level}"
    move = value.get("move")
    if isinstance(move, dict) and move.get("name"):
        level = f" — Lv. {value['level']}" if value.get("level") is not None else ""
        return f"{move['name']}{level}"
    target = value.get("target")
    if isinstance(target, dict) and target.get("name"):
        method = value.get("method")
        method_name = method.get("name") if isinstance(method, dict) else method
        suffix = f" — {method_name}" if method_name else ""
        return f"{target['name']}{suffix}"
    if value.get("name"):
        return str(value["name"])
    identifiers = [
        f"{key.replace('_', ' ').title()}: {item}"
        for key, item in value.items()
        if key == "id" or key.endswith("_id")
    ]
    return ", ".join(identifiers) or "Structured value"


def _plain_value(value: Any) -> str:
    if value is None:
        return "None"
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return str(value)


def _reference_id(value: dict[str, Any] | None) -> Any:
    return value.get("id") if value else None


def _machine_identity(value: dict[str, Any]) -> Any:
    return value.get("id")


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
) -> tuple[str, str]:
    previous = {_machine_identity(item): item for item in before}
    current = {_machine_identity(item): item for item in after}
    old_lines = []
    new_lines = []
    for key in sorted(set(previous) | set(current)):
        old = previous.get(key)
        new = current.get(key)
        if old is not None and new is not None:
            continue
        if old is not None:
            old_lines.append(
                f"{_machine_label(old, source_url, references)}: Compatible"
            )
            new_lines.append(
                f"{escape(str(old.get('name', 'Machine')))}: Not compatible"
            )
        else:
            old_lines.append(
                f"{escape(str(new.get('name', 'Machine')))}: Not compatible"
            )
            new_lines.append(
                f"{_machine_label(new, source_url, references)}: Compatible"
            )
    return _format_lines(old_lines, True), _format_lines(new_lines, True)


def _move_identity(value: dict[str, Any]) -> Any:
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
        return name
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


def _format_delta(label: str, values: list[Any]) -> str:
    if not values:
        return "No entries"
    ordered = sorted(values, key=_canonical)
    if len(ordered) == 1:
        return _format_value(ordered[0])
    entries = "".join(f"<li>{_format_value(value)}</li>" for value in ordered)
    return (
        f"<details><summary>{len(ordered)} {label}</summary>"
        f"<ul>{entries}</ul></details>"
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


