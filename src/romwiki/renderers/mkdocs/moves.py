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
    class_badge,
    display_name,
    record_nav_link,
    record_navigation,
    tutor_requirement,
    type_badges,
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
    pokemon_markdown_link,
)


def render_move_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    output_root.mkdir(parents=True, exist_ok=True)
    prune_catalog_pages(
        output_root,
        {
            "index.md",
            *(
                f"{record['slug']}.md"
                for record in public_records
                if only_pages is None or record["slug"] in only_pages
            ),
        },
    )
    fallback_links = []
    catalog_records = []
    page_count = 0
    name_source = dataset.get("name_sources", {}).get("move_names")
    for index, record in enumerate(public_records):
        change = record_comparison(comparison, record["move_id"])
        filename = f"{record['slug']}.md"
        previous = public_records[index - 1] if index else None
        following = public_records[index + 1] if index + 1 < len(public_records) else None
        if only_pages is None or record["slug"] in only_pages:
            _write_text(
                output_root / filename,
                _render_record(
                    record,
                    previous,
                    following,
                    name_source,
                    change,
                    comparison.get("baseline") if comparison else None,
                    references,
                ),
            )
            page_count += 1
        fallback_links.append(
            "- "
            + ROUTES.markdown_link(
                entity_reference(
                    "move",
                    record["move_id"],
                    record["name"],
                    record["slug"],
                ),
                "moves/index.md",
            )
        )
        machines = [machine["name"] for machine in record.get("machines", [])]
        replaced_name = (
            record["replaces"]["name"] if record.get("replaces") else None
        )
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
            add_change_status({
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
                    (
                        record["name"],
                        *machines,
                        *access_methods,
                        *((replaced_name,) if replaced_name else ()),
                    )
                ).lower(),
            }, change)
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
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
    name_source: dict[str, Any] | None = None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
) -> str:
    source_file = f"moves/{record['slug']}.md"
    lines = [
        f"# {record['name']}",
        "",
        '<section class="rw-move-summary">',
        type_badges([record["type"]]),
        '<dl class="rw-summary__facts">',
        f"<div><dt>Class</dt><dd>{class_badge(record['damage_class'])}</dd></div>",
        f"<div><dt>Power</dt><dd>{_optional_value(record['power'])}</dd></div>",
        f"<div><dt>Accuracy</dt><dd>{_accuracy(record['accuracy'])}</dd></div>",
        f"<div><dt>PP</dt><dd>{record['pp']}</dd></div>",
        "</dl>",
        "</section>",
        "",
        *_move_description(record),
        *comparison_section(change, baseline_name, source_file, references),
        "## Battle properties",
        "",
        "| Property | Value |",
        "| -------- | ----- |",
        f"| Type | {type_badges([record['type']])} |",
        f"| Damage class | {class_badge(record['damage_class'])} |",
        f"| Power | {_optional_value(record['power'])} |",
        f"| Accuracy | {_accuracy(record['accuracy'])} |",
        f"| PP | {record['pp']} |",
        f"| Machine | {_machine_names(record)} |",
        f"| Move tutor | {_tutor_locations(record)} |",
        *(
            [f"| Replaces | {record['replaces']['name']} |"]
            if record.get("replaces")
            else []
        ),
        f"| Priority | {record['priority']:+d} |",
        f"| Effect chance | {_effect_chance(record['effect_chance'])} |",
        "",
        "## Tutor compatibility",
        "",
        *_tutor_compatibility(record, source_file),
        "## Egg move learners",
        "",
        *_egg_move_learners(record, source_file),
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
            "shown in their native engine representation. The ROM does not store a "
            "human-readable effect description; the Effect section and Pokédex "
            "quote above come from PokéDB / PokéAPI reference data."
        ),
        *(
            [
                "Move name source: ROM message table "
                f"`{name_source['archive']}` member `{name_source['member']}`."
            ]
            if name_source is not None
            else []
        ),
        "",
        "</details>",
        "",
    ]
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"moves/{record['slug']}/"
    previous_link = None
    if previous is not None:
        label = f"← {previous['name']}"
        href = ROUTES.published_href(
            entity_reference("move", previous["move_id"], label, previous["slug"]),
            source_url,
        )
        previous_link = record_nav_link(href, label, "prev")
    following_link = None
    if following is not None:
        label = f"{following['name']} →"
        href = ROUTES.published_href(
            entity_reference("move", following["move_id"], label, following["slug"]),
            source_url,
        )
        following_link = record_nav_link(href, label, "next")
    lines.extend(record_navigation(previous_link, following_link, "Move navigation"))


def _move_description(record: dict[str, Any]) -> list[str]:
    reference = record.get("reference") or {}
    short_effect = reference.get("short_effect")
    effect = reference.get("effect")
    flavor_text = reference.get("flavor_text")
    lines: list[str] = []
    if short_effect or effect:
        lines.extend(["## Effect", ""])
        if short_effect:
            lines.append(f'<p><strong>{escape(" ".join(short_effect.split()))}</strong></p>')
        if effect and effect != short_effect:
            lines.append(f'<p>{escape(" ".join(effect.split()))}</p>')
        lines.append("")
    if flavor_text:
        version_label = (
            f"{display_name(reference['version'])} Pokédex"
            if reference.get("version")
            else "Pokédex"
        )
        lines.extend(
            [
                '<figure class="rw-pokedex-entry">',
                f"<blockquote>{escape(' '.join(flavor_text.split()))}</blockquote>",
                f"<figcaption>{escape(version_label)}</figcaption>",
                "</figure>",
                "",
            ]
        )
    if not lines:
        lines = ["No PokéDB reference data is available for this move.", ""]
    return lines


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


def _tutor_compatibility(
    record: dict[str, Any], source_file: str
) -> list[str]:
    tutors = record.get("tutors", [])
    if not tutors:
        return ["Not taught by a shard move tutor.", ""]
    lines = []
    for tutor in tutors:
        costs = tutor_requirement(tutor)
        pokemon = ", ".join(
            _pokemon_link(value, source_file)
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


def _egg_move_learners(
    record: dict[str, Any], source_file: str
) -> list[str]:
    pokemon = record.get("egg_move_pokemon", [])
    if not pokemon:
        return ["None.", ""]
    return [
        ", ".join(
            _pokemon_link(value, source_file) for value in pokemon
        ),
        "",
    ]


def _pokemon_link(value: dict[str, Any], source_file: str) -> str:
    return pokemon_markdown_link(
        value.get("id", value.get("slug", value["name"])),
        value["name"],
        value.get("slug"),
        source_file,
    )


