from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)
from romwiki.renderers.mkdocs.comparisons import (
    add_change_status,
    comparison_section,
    record_comparison,
)
from romwiki.renderers.mkdocs.references import ROUTES, ReferenceIndex, entity_reference


def render_ability_pages(
    dataset: dict[str, Any],
    output_root: Path,
    comparison: dict[str, Any] | None = None,
    references: ReferenceIndex | None = None,
) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    filenames = {"index.md", *(f"{record['slug']}.md" for record in records)}
    prune_catalog_pages(output_root, filenames)

    fallback_links = []
    catalog_records = []
    for index, record in enumerate(records):
        change = record_comparison(comparison, record["ability_id"])
        filename = f"{record['slug']}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
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
    return len(records)


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
        f"- Ability ID: {record['ability_id']}",
        "",
        *comparison_section(change, baseline_name, source_file, references),
        "## Pokémon",
        "",
    ]
    if record["pokemon"]:
        lines.extend(
            [
                "| Pokémon | National Pokédex | Ability slot |",
                "| ------- | ---------------: | ------------ |",
                *[
                    (
                        f"| {_pokemon_link(pokemon, source_file)} | "
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
            "## Source",
            "",
            "The ability name and Pokémon assignments are extracted from the ROM. "
            "Ability behavior is not inferred from the name or from external "
            "reference data.",
            "",
            _page_navigation(previous, following, source_file),
            "",
        ]
    )
    return "\n".join(lines)


def _pokemon_link(pokemon: dict[str, Any], source_file: str) -> str:
    reference = entity_reference(
        "pokemon",
        pokemon.get("member", pokemon["national_dex_id"]),
        pokemon["name"],
        pokemon.get("slug"),
    )
    return ROUTES.markdown_link(reference, source_file)


def _page_navigation(
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    source_file: str,
) -> str:
    links = []
    if previous is not None:
        links.append(ROUTES.markdown_link(
            entity_reference(
                "ability",
                previous["ability_id"],
                f"← {previous['name']}",
                previous["slug"],
            ),
            source_file,
        ))
    links.append("[All abilities](index.md)")
    if following is not None:
        links.append(ROUTES.markdown_link(
            entity_reference(
                "ability",
                following["ability_id"],
                f"{following['name']} →",
                following["slug"],
            ),
            source_file,
        ))
    return " · ".join(links)
