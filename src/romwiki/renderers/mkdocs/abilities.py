from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.components import record_nav_link, record_navigation
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


def render_ability_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
    *,
    only_pages: frozenset[str] | None = None,
) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    filenames = {
        "index.md",
        *(
            f"{record['slug']}.md"
            for record in records
            if only_pages is None or record["slug"] in only_pages
        ),
    }
    prune_catalog_pages(output_root, filenames)

    fallback_links = []
    catalog_records = []
    page_count = 0
    for index, record in enumerate(records):
        change = record_comparison(comparison, record["ability_id"])
        filename = f"{record['slug']}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        if only_pages is None or record["slug"] in only_pages:
            write_text(
                output_root / filename,
                _render_record(
                    record,
                    previous,
                    following,
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
                    "ability",
                    record["ability_id"],
                    f"#{record['ability_id']:03} {record['name']}",
                    record["slug"],
                ),
                "abilities/index.md",
            )
        )
        pokemon_names = [pokemon["name"] for pokemon in record["pokemon"]]
        pokemon_refs = [
            ROUTES.catalog_reference(
                entity_reference(
                    "pokemon",
                    pokemon.get("member", pokemon["national_dex_id"]),
                    pokemon["name"],
                    pokemon.get("slug"),
                ),
                "abilities/",
            )
            for pokemon in record["pokemon"]
        ]
        catalog_records.append(
            add_change_status({
                "id": record["ability_id"],
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "pokemon": pokemon_names,
                "pokemon_refs": pokemon_refs,
                "pokemon_count": len(pokemon_names),
                "status": "assigned" if pokemon_names else "unassigned",
                "search_text": " ".join((record["name"], *pokemon_names)).lower(),
            }, change)
        )

    write_catalog(output_root, "abilities", catalog_records)
    write_text(
        output_root / "index.md",
        catalog_index(
            "Abilities",
            "Abilities extracted from the ROM, with every Pokémon and form that "
            "can have them.",
            "abilities",
            fallback_links,
        ),
    )
    return page_count


def _render_record(
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    change: dict[str, Any] | None = None,
    baseline_name: str | None = None,
    references: ReferenceIndex | None = None,
) -> str:
    source_file = f"abilities/{record['slug']}.md"
    lines = [
        f"# {record['name']}",
        "",
        *_ability_summary(record),
        *_ability_description(record),
        *comparison_section(change, baseline_name, source_file, references),
        "## Pokémon",
        "",
    ]
    if record["pokemon"]:
        lines.extend(
            [
                "| <span class=\"rw-visually-hidden\">Sprite</span> | Pokémon | "
                "National Pokédex | Ability slot |",
                "| ---- | ------- | ---------------: | ------------ |",
                *[
                    (
                        f"| {_sprite_cell(pokemon)} | {_pokemon_link(pokemon, source_file)} | "
                        f"#{pokemon['national_dex_id']:03} | "
                        f"{', '.join(str(slot) for slot in pokemon['slots'])} |"
                    )
                    for pokemon in record["pokemon"]
                ],
                "",
            ]
        )
    else:
        lines.extend(["No Pokémon in this game are assigned this ability.", ""])

    lines.extend(
        [
            '<details class="rw-source-details" markdown="1">',
            "<summary>Data provenance</summary>",
            "",
            "The ability name and Pokémon assignments are exact ROM facts. Ability "
            "behavior is never inferred from the ROM or the name; effect and "
            "flavor text come from PokéDB / PokéAPI reference data.",
            "",
            "</details>",
            "",
        ]
    )
    _append_record_navigation(lines, record, previous, following)
    return "\n".join(lines)


def _ability_summary(record: dict[str, Any]) -> list[str]:
    return [
        '<section class="rw-ability-summary">',
        '<dl class="rw-summary__facts">',
        f"<div><dt>Ability ID</dt><dd>{record['ability_id']}</dd></div>",
        f"<div><dt>Pokémon with this ability</dt><dd>{len(record['pokemon'])}</dd></div>",
        "</dl>",
        "</section>",
        "",
    ]


def _ability_description(record: dict[str, Any]) -> list[str]:
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
            f"{_label(reference['version'])} Pokédex" if reference.get("version") else "Pokédex"
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
        lines = ["No PokéDB reference data is available for this ability.", ""]
    return lines


def _sprite_cell(pokemon: dict[str, Any]) -> str:
    sprite = pokemon.get("sprite")
    if not sprite or not sprite.get("url"):
        return '<span class="rw-table-sprite rw-table-sprite--empty" aria-hidden="true">—</span>'
    return (
        f'<img class="rw-table-sprite" src="{escape(sprite["url"], quote=True)}" '
        f'alt="" loading="lazy">'
    )


def _label(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))


def _pokemon_link(pokemon: dict[str, Any], source_file: str) -> str:
    return pokemon_markdown_link(
        pokemon.get("member", pokemon["national_dex_id"]),
        pokemon["name"],
        pokemon.get("slug"),
        source_file,
    )


def _append_record_navigation(
    lines: list[str],
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
) -> None:
    source_url = f"abilities/{record['slug']}/"
    previous_link = None
    if previous is not None:
        label = f"← {previous['name']}"
        href = ROUTES.published_href(
            entity_reference("ability", previous["ability_id"], label, previous["slug"]),
            source_url,
        )
        previous_link = record_nav_link(href, label, "prev")
    following_link = None
    if following is not None:
        label = f"{following['name']} →"
        href = ROUTES.published_href(
            entity_reference("ability", following["ability_id"], label, following["slug"]),
            source_url,
        )
        following_link = record_nav_link(href, label, "next")
    lines.extend(record_navigation(previous_link, following_link, "Ability navigation"))
