from __future__ import annotations

from pathlib import Path
from typing import Any


def render_move_pages(dataset: dict[str, Any], output_root: Path) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    output_root.mkdir(parents=True, exist_ok=True)
    index_lines = [
        "# Moves",
        "",
        "Move mechanics extracted directly from the game image.",
        "",
        "| Move | Type | Class | Power | Accuracy | PP |",
        "| ---- | ---- | ----- | ----: | -------: | -: |",
    ]
    for record in public_records:
        filename = f"{record['slug']}.md"
        _write_text(output_root / filename, _render_record(record))
        index_lines.append(
            f"| [{record['name']}]({filename}) | {_display_name(record['type']['name'])} "
            f"| {_display_name(record['damage_class']['name'])} | "
            f"{_optional_value(record['power'])} | "
            f"{_accuracy(record['accuracy'])} | {record['pp']} |"
        )
    _write_text(output_root / "index.md", "\n".join(index_lines) + "\n")
    return len(public_records)


def _render_record(record: dict[str, Any]) -> str:
    lines = [
        f"# {record['name']}",
        "",
        "| Property | Value |",
        "| -------- | ----- |",
        f"| Type | {_display_name(record['type']['name'])} |",
        f"| Damage class | {_display_name(record['damage_class']['name'])} |",
        f"| Power | {_optional_value(record['power'])} |",
        f"| Accuracy | {_accuracy(record['accuracy'])} |",
        f"| PP | {record['pp']} |",
        f"| Priority | {record['priority']:+d} |",
        f"| Effect ID | `{record['effect_id']}` |",
        f"| Effect chance | {_effect_chance(record['effect_chance'])} |",
        f"| Target ID | `0x{record['target_id']:04X}` |",
        f"| Flags | `0x{record['flags']:02X}` |",
        f"| Contest effect ID | `{record['contest_effect_id']}` |",
        f"| Contest type ID | `{record['contest_type_id']}` |",
        "",
        "---",
        "",
        (
            "Source: exact ROM record from "
            f"`{record['provenance']['archive']}` member "
            f"`{record['provenance']['member']}`. Effect, target, and flag IDs are "
            "shown in their native engine representation."
        ),
        "",
    ]
    return "\n".join(lines)


def _optional_value(value: int) -> str:
    return str(value) if value else "—"


def _accuracy(value: int) -> str:
    return f"{value}%" if value else "Always hits"


def _effect_chance(value: int) -> str:
    return f"{value}%" if value else "—"


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
