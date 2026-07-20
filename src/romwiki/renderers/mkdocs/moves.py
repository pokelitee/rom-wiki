from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
)
from romwiki.renderers.mkdocs.components import type_badges


def render_move_pages(dataset: dict[str, Any], output_root: Path) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {"index.md", *(f"{record['slug']}.md" for record in public_records)},
    )
    fallback_links = []
    catalog_records = []
    for index, record in enumerate(public_records):
        filename = f"{record['slug']}.md"
        previous = public_records[index - 1] if index else None
        following = public_records[index + 1] if index + 1 < len(public_records) else None
        _write_text(output_root / filename, _render_record(record, previous, following))
        fallback_links.append(f"- [{record['name']}]({filename})")
        machines = [machine["name"] for machine in record.get("machines", [])]
        access_methods = [
            method
            for method, available in (
                ("machine", bool(machines)),
                ("move tutor", bool(record.get("tutors"))),
                ("egg move", bool(record.get("egg_move_pokemon"))),
            )
            if available
        ]
        catalog_records.append(
            {
                "id": record["move_id"],
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "type": record["type"]["name"],
                "damage_class": record["damage_class"]["name"],
                "power": record["power"],
                "accuracy": record["accuracy"],
                "pp": record["pp"],
                "machines": machines,
                "access_methods": access_methods,
                "search_text": " ".join(
                    (record["name"], *machines, *access_methods)
                ).lower(),
            }
        )
    write_catalog(output_root, "moves", catalog_records)
    _write_text(
        output_root / "index.md",
        catalog_index(
            "Moves",
            "Move mechanics extracted directly from the game image.",
            "moves",
            fallback_links,
        ),
    )
    return len(public_records)


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"# {record['name']}",
        "",
        '<section class="rw-move-summary">',
        type_badges([record["type"]]),
        '<dl class="rw-summary__facts">',
        f"<div><dt>Class</dt><dd>{_display_name(record['damage_class']['name'])}</dd></div>",
        f"<div><dt>Power</dt><dd>{_optional_value(record['power'])}</dd></div>",
        f"<div><dt>Accuracy</dt><dd>{_accuracy(record['accuracy'])}</dd></div>",
        f"<div><dt>PP</dt><dd>{record['pp']}</dd></div>",
        "</dl>",
        "</section>",
        "",
        "## Battle properties",
        "",
        "| Property | Value |",
        "| -------- | ----- |",
        f"| Type | {_display_name(record['type']['name'])} |",
        f"| Damage class | {_display_name(record['damage_class']['name'])} |",
        f"| Power | {_optional_value(record['power'])} |",
        f"| Accuracy | {_accuracy(record['accuracy'])} |",
        f"| PP | {record['pp']} |",
        f"| Machine | {_machine_names(record)} |",
        f"| Move tutor | {_tutor_locations(record)} |",
        f"| Priority | {record['priority']:+d} |",
        f"| Effect chance | {_effect_chance(record['effect_chance'])} |",
        "",
        "## Tutor compatibility",
        "",
        *_tutor_compatibility(record),
        "## Egg move learners",
        "",
        *_egg_move_learners(record),
        '<details class="rw-source-details" markdown="1">',
        "<summary>Engine details and provenance</summary>",
        "",
        "| Native field | Value |",
        "| ------------ | ----- |",
        f"| Effect ID | `{record['effect_id']}` |",
        f"| Target ID | `0x{record['target_id']:04X}` |",
        f"| Flags | `0x{record['flags']:02X}` |",
        f"| Contest effect ID | `{record['contest_effect_id']}` |",
        f"| Contest type ID | `{record['contest_type_id']}` |",
        "",
        (
            "Source: exact ROM record from "
            f"`{record['provenance']['archive']}` member "
            f"`{record['provenance']['member']}`. Effect, target, and flag IDs are "
            "shown in their native engine representation."
        ),
        "",
        "</details>",
        "",
    ]
    _append_record_navigation(lines, previous, following)
    return "\n".join(lines)


def _append_record_navigation(
    lines: list[str],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    if previous is None and following is None:
        return
    lines.extend(['<nav class="rw-record-nav" aria-label="Move navigation">'])
    if previous is not None:
        lines.append(
            f'<a href="../{previous["slug"]}/">&larr; {previous["name"]}</a>'
        )
    else:
        lines.append("<span></span>")
    if following is not None:
        lines.append(
            f'<a href="../{following["slug"]}/">{following["name"]} &rarr;</a>'
        )
    lines.extend(["</nav>", ""])


def _optional_value(value: int) -> str:
    return str(value) if value else "—"


def _accuracy(value: int) -> str:
    return f"{value}%" if value else "Always hits"


def _effect_chance(value: int) -> str:
    return f"{value}%" if value else "—"


def _machine_names(record: dict[str, Any]) -> str:
    return ", ".join(machine["name"] for machine in record.get("machines", [])) or "—"


def _tutor_locations(record: dict[str, Any]) -> str:
    return ", ".join(
        tutor["location"]["name"] for tutor in record.get("tutors", [])
    ) or "—"


def _tutor_compatibility(record: dict[str, Any]) -> list[str]:
    tutors = record.get("tutors", [])
    if not tutors:
        return ["Not taught by a shard move tutor.", ""]
    lines = []
    for tutor in tutors:
        if tutor.get("kind") == "special":
            costs = f"Friendship {tutor['minimum_friendship']}"
        else:
            costs = ", ".join(
                f"{amount} {color.title()}"
                for color, amount in tutor["shard_costs"].items()
                if amount
            ) or "Free"
        pokemon = ", ".join(
            f"[{value['name']}](../pokemon/{value['slug']}.md)"
            for value in tutor["compatible_pokemon"]
        ) or "None"
        lines.extend(
            [
                f"**{tutor['location']['name']} — {costs}:**",
                "",
                pokemon,
                "",
            ]
        )
    return lines


def _egg_move_learners(record: dict[str, Any]) -> list[str]:
    pokemon = record.get("egg_move_pokemon", [])
    if not pokemon:
        return ["None.", ""]
    return [
        ", ".join(
            f"[{value['name']}](../pokemon/{value['slug']}.md)" for value in pokemon
        ),
        "",
    ]


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
