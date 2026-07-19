from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import catalog_index, write_catalog


def render_trainer_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = [record for record in dataset["records"] if record["party"]]
    output_root.mkdir(parents=True, exist_ok=True)
    fallback_links = []
    catalog_records = []
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
    for record in sorted(
        linked,
        key=lambda item: (
            (item["locations"] or item.get("script_references", []))[0]["name"],
            _trainer_label(item),
            item["trainer_id"],
        ),
    ):
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        _write_text(output_root / filename, _render_trainer(record))
        location_names = " / ".join(
            dict.fromkeys(
                location["name"]
                for location in record["locations"]
                + record.get("script_references", [])
            )
        )
        fallback_links.append(f"- [{location_names} — {label}](./{filename})")
        catalog_records.append(
            _catalog_record(record, filename.removesuffix(".md") + "/", location_names, True)
        )
    for record in unlinked:
        filename = f"trainer-{record['trainer_id']:04}.md"
        label = _trainer_label(record)
        _write_text(output_root / filename, _render_trainer(record))
        fallback_links.append(f"- [{label}](./{filename})")
        catalog_records.append(
            _catalog_record(record, filename.removesuffix(".md") + "/", "", False)
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
    return len(records)


def _catalog_record(
    record: dict[str, Any], filename: str, location_label: str, linked: bool
) -> dict[str, Any]:
    levels = [member["level"] for member in record["party"]]
    location_names = list(
        dict.fromkeys(
            location["name"]
            for location in record["locations"] + record.get("script_references", [])
        )
    )
    species = [member["pokemon"]["name"] for member in record["party"]]
    label = _trainer_label(record)
    return {
        "id": record["trainer_id"],
        "label": label,
        "url": filename,
        "class_name": record["class_name"],
        "name": record["name"],
        "locations": location_names,
        "location_label": location_label,
        "linked": linked,
        "double_battle": record["double_battle"],
        "party_size": len(record["party"]),
        "min_level": min(levels),
        "max_level": max(levels),
        "pokemon": species,
        "search_text": " ".join((label, *location_names, *species)).lower(),
    }


def _render_trainer(record: dict[str, Any]) -> str:
    label = _trainer_label(record)
    lines = [f"# {label}", "", f"Trainer ID: `{record['trainer_id']}`", ""]
    if record["double_battle"]:
        lines.extend(["Battle type: Double battle", ""])
    _append_locations(lines, record["locations"])
    _append_script_references(lines, record.get("script_references", []))
    lines.extend(["## Party", "", *_party_cards(record["party"])])
    lines.extend(
        [
            "",
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
    return "\n".join(lines)


def _party_cards(party: list[dict[str, Any]]) -> list[str]:
    lines = ['<div class="rw-party-grid">']
    for index, member in enumerate(party, start=1):
        pokemon = member["pokemon"]
        held_item = member["held_item"]
        item_name = (
            _display_name(held_item["name"])
            if held_item and held_item["name"]
            else "—"
        )
        lines.extend(
            [
                '<article class="rw-party-card">',
                f'<span class="rw-party-card__slot">Slot {index}</span>',
                f'<h3><a href="../../pokemon/{escape(pokemon["slug"], quote=True)}/">{escape(pokemon["name"])}</a></h3>',
                '<dl class="rw-summary__facts">',
                f"<div><dt>Level</dt><dd>{member['level']}</dd></div>",
                f"<div><dt>Held item</dt><dd>{escape(item_name)}</dd></div>",
                "</dl>",
                '<ul class="rw-party-card__moves" aria-label="Moves">',
            ]
        )
        if member["moves"]:
            for move in member["moves"]:
                slug = move["name"]
                lines.append(
                    f'<li><a href="../../moves/{escape(slug, quote=True)}/">{escape(_display_name(slug))}</a></li>'
                )
        else:
            lines.append("<li>Default moves</li>")
        lines.extend(["</ul>", "</article>"])
    lines.extend(["</div>", ""])
    return lines


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
            f"| [{location['name']}](../locations/header-{location['header_id']:03}.md) "
            f"| {location['header_id']} | "
            f"`{location['internal_name']}` | ({location['x']}, {location['z']}) | "
            f"`{location['event_file_id']}:{location['object_index']}` |"
        )
    lines.append("")


def _append_script_references(
    lines: list[str], references: list[dict[str, Any]]
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
        lines.append(
            f"| [{reference['name']}](../locations/header-{reference['header_id']:03}.md) "
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


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
