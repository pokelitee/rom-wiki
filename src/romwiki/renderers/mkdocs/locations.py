from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def render_location_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    name_counts = Counter(record["name"] for record in records)
    index = [
        "# Locations",
        "",
        "Map headers, item pickups, shops, warps, outdoor connections, encounters, "
        "and trainers extracted from the ROM.",
        "",
    ]
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
        index.append(f"- [{label}](./{filename})")
    _write_text(output_root / "index.md", "\n".join(index) + "\n")
    return len(records)


def _render_location(record: dict[str, Any]) -> str:
    lines = [
        f"# {record['name']}",
        "",
        f"Internal map: `{record['internal_name']}`  ",
        f"Header ID: `{record['header_id']}`  ",
        f"Matrix ID: `{record['matrix_id']}`",
        "",
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
    _append_trainers(lines, record["trainers"])
    _append_warps(lines, record["warps"])
    _append_connections(lines, record["connections"])
    lines.extend(
        [
            "---",
            "",
            "Source: exact map header, event, script, item-data, and map-matrix "
            "records from the ROM.",
            "",
        ]
    )
    return "\n".join(lines)


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
        label = "Common Poké Mart" if shop["kind"] == "common" else "Specialty shop"
        if kind_counts[shop["kind"]] > 1:
            label += f" {kind_indices[shop['kind']]}"
        lines.extend(
            [
                f"### {label}",
                "",
                "| Item | Item ID | Price | Available after |",
                "| ---- | ------: | ----: | --------------- |",
            ]
        )
        for item in shop["items"]:
            price = f"₽{item['price']:,}" if item["price"] is not None else "—"
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
