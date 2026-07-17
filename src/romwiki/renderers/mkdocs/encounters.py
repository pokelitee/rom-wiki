from __future__ import annotations

from pathlib import Path
from typing import Any
from collections import Counter


def render_encounter_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = [record for record in dataset["records"] if record["active"]]
    output_root.mkdir(parents=True, exist_ok=True)
    index = [
        "# Wild encounters",
        "",
        "Encounter tables extracted from the ROM and linked to their in-game "
        "locations through Platinum's map headers.",
        "",
    ]
    linked = [record for record in records if record.get("locations")]
    unlinked = [record for record in records if not record.get("locations")]
    name_counts = Counter(record["name"] for record in linked)
    index.extend(["## Locations", ""])
    for record in sorted(linked, key=lambda item: (item["name"], item["area_id"])):
        filename = f"area-{record['area_id']:03}.md"
        _write_text(output_root / filename, _render_area(record))
        label = record["name"]
        if name_counts[label] > 1:
            internal_names = ", ".join(
                dict.fromkeys(location["internal_name"] for location in record["locations"])
            )
            label = f"{label} — {internal_names}"
        index.append(f"- [{label}]({filename})")
    if unlinked:
        index.extend(
            [
                "",
                "## Unreferenced encounter records",
                "",
                "These populated archive members are not referenced by a static map "
                "header. They may be unused data or selected by game logic that has "
                "not yet been linked.",
                "",
            ]
        )
        for record in unlinked:
            filename = f"area-{record['area_id']:03}.md"
            _write_text(output_root / filename, _render_area(record))
            index.append(f"- [{record['name']}]({filename})")
    _write_text(output_root / "index.md", "\n".join(index) + "\n")
    return len(records)


def _render_area(record: dict[str, Any]) -> str:
    lines = [f"# {record['name']}", ""]
    _append_locations(lines, record.get("locations", []))
    _append_walking(lines, record["walking"])
    for heading, key in (
        ("Surf", "surf"),
        ("Old Rod", "old_rod"),
        ("Good Rod", "good_rod"),
        ("Super Rod", "super_rod"),
    ):
        _append_water(lines, heading, record[key])
    _append_special(lines, record["special"])
    lines.extend(
        [
            "---",
            "",
            (
                "Source: exact ROM record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _append_locations(lines: list[str], locations: list[dict[str, Any]]) -> None:
    if not locations:
        return
    lines.extend(["## Map headers", "", "| Header | Location | Internal map |", "| -----: | -------- | ------------ |"])
    for location in locations:
        lines.append(
            f"| {location['header_id']} | {location['name']} | "
            f"`{location['internal_name']}` |"
        )
    lines.append("")


def _append_walking(lines: list[str], method: dict[str, Any]) -> None:
    if not method["rate"]:
        return
    lines.extend(
        [
            "## Walking",
            "",
            f"Encounter rate: {method['rate']}",
            "",
            "| Slot | Pokémon | Level |",
            "| ---: | ------- | ----: |",
        ]
    )
    for index, slot in enumerate(method["slots"]):
        lines.append(
            f"| {index + 1} | {_pokemon_link(slot['pokemon'])} | "
            f"{slot['level']} |"
        )
    lines.append("")


def _append_water(lines: list[str], heading: str, method: dict[str, Any]) -> None:
    if not method["rate"]:
        return
    lines.extend(
        [
            f"## {heading}",
            "",
            f"Encounter rate: {method['rate']}",
            "",
            "| Slot | Pokémon | Levels |",
            "| ---: | ------- | -----: |",
        ]
    )
    for index, slot in enumerate(method["slots"]):
        levels = _level_range(slot["minimum_level"], slot["maximum_level"])
        lines.append(f"| {index + 1} | {_pokemon_link(slot['pokemon'])} | {levels} |")
    lines.append("")


def _append_special(lines: list[str], special: dict[str, Any]) -> None:
    groups = [
        ("Swarm", special["swarm"]),
        ("Day replacements", special["day"]),
        ("Night replacements", special["night"]),
        ("Poké Radar", special["radar"]),
    ]
    groups.extend(
        (f"Dual-slot: {game.replace('-', ' ').title()}", pokemon)
        for game, pokemon in special["dual_slot"].items()
    )
    populated = [(label, values) for label, values in groups if any(values)]
    if not populated:
        return
    lines.extend(["## Special encounters", ""])
    for label, values in populated:
        names = ", ".join(_pokemon_link(value) for value in values if value)
        lines.append(f"- {label}: {names}")
    lines.append("")


def _pokemon_link(pokemon: dict[str, Any] | None) -> str:
    if pokemon is None:
        return "None"
    return f"[{pokemon['name']}](../pokemon/{pokemon['slug']}.md)"


def _level_range(minimum: int, maximum: int) -> str:
    return str(minimum) if minimum == maximum else f"{minimum}–{maximum}"


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
