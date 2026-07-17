from __future__ import annotations

from pathlib import Path
from typing import Any


def render_trainer_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = [record for record in dataset["records"] if record["party"]]
    output_root.mkdir(parents=True, exist_ok=True)
    index = [
        "# Trainers",
        "",
        "Trainer parties and battle settings extracted directly from the ROM.",
        "",
    ]
    linked = [record for record in records if record["locations"]]
    unlinked = [record for record in records if not record["locations"]]
    index.extend(["## Located overworld trainers", ""])
    for record in sorted(
        linked, key=lambda item: (item["locations"][0]["name"], _trainer_label(item), item["trainer_id"])
    ):
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        _write_text(output_root / filename, _render_trainer(record))
        location_names = " / ".join(
            dict.fromkeys(location["name"] for location in record["locations"])
        )
        index.append(f"- [{location_names} — {label}](./{filename})")
    index.extend(
        [
            "",
            "## Unlinked trainer records",
            "",
            "These records are not referenced by a direct overworld trainer object. "
            "They may be invoked by local story scripts, used for rematches or facilities, "
            "or retained as unused data.",
            "",
        ]
    )
    for record in unlinked:
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        _write_text(output_root / filename, _render_trainer(record))
        index.append(f"- [{label}](./{filename})")
    _write_text(output_root / "index.md", "\n".join(index) + "\n")
    return len(records)


def _render_trainer(record: dict[str, Any]) -> str:
    label = _trainer_label(record)
    lines = [f"# {label}", "", f"Trainer ID: `{record['trainer_id']}`", ""]
    if record["double_battle"]:
        lines.extend(["Battle type: Double battle", ""])
    _append_locations(lines, record["locations"])
    lines.extend(
        [
            "## Party",
            "",
            "| Slot | Pokémon | Level | Held item | Moves |",
            "| ---: | ------- | ----: | --------- | ----- |",
        ]
    )
    for index, member in enumerate(record["party"], start=1):
        pokemon = member["pokemon"]
        link = f"[{pokemon['name']}](../pokemon/{pokemon['slug']}.md)"
        held_item = member["held_item"]
        item_name = (
            _display_name(held_item["name"])
            if held_item and held_item["name"]
            else "—"
        )
        moves = ", ".join(_display_name(move["name"]) for move in member["moves"]) or "—"
        lines.append(
            f"| {index} | {link} | {member['level']} | {item_name} | {moves} |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            (
                f"Source: exact ROM trainer record from `{record['provenance']['archive']}` "
                f"member `{record['provenance']['member']}` and party record from "
                f"`{record['party_provenance']['archive']}` member "
                f"`{record['party_provenance']['member']}`."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _append_locations(lines: list[str], locations: list[dict[str, Any]]) -> None:
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
        lines.append(
            f"| {location['name']} | {location['header_id']} | "
            f"`{location['internal_name']}` | ({location['x']}, {location['z']}) | "
            f"`{location['event_file_id']}:{location['object_index']}` |"
        )
    lines.append("")


def _trainer_label(record: dict[str, Any]) -> str:
    return " ".join(value for value in (record["class_name"], record["name"]) if value)


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
