from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.renderers.mkdocs.catalog import (
    catalog_index,
    prune_catalog_pages,
    write_catalog,
    write_text,
)


def render_ability_pages(dataset: dict[str, Any], output_root: Path) -> int:
    records = dataset["records"]
    output_root.mkdir(parents=True, exist_ok=True)
    filenames = {"index.md", *(f"{record['slug']}.md" for record in records)}
    prune_catalog_pages(output_root, filenames)

    fallback_links = []
    catalog_records = []
    for index, record in enumerate(records):
        filename = f"{record['slug']}.md"
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        write_text(output_root / filename, _render_record(record, previous, following))
        fallback_links.append(
            f"- [#{record['ability_id']:03} {record['name']}]({filename})"
        )
        pokemon_names = [pokemon["name"] for pokemon in record["pokemon"]]
        catalog_records.append(
            {
                "id": record["ability_id"],
                "label": record["name"],
                "slug": record["slug"],
                "url": f"{record['slug']}/",
                "pokemon": pokemon_names,
                "pokemon_count": len(pokemon_names),
                "status": "assigned" if pokemon_names else "unassigned",
                "search_text": " ".join((record["name"], *pokemon_names)).lower(),
            }
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
) -> str:
    lines = [
        f"# {record['name']}",
        "",
        f"- Ability ID: {record['ability_id']}",
        "",
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
                        f"| [{pokemon['name']}](../pokemon/{pokemon['slug']}.md) | "
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
            _page_navigation(previous, following),
            "",
        ]
    )
    return "\n".join(lines)


def _page_navigation(
    previous: dict[str, Any] | None, following: dict[str, Any] | None
) -> str:
    links = []
    if previous is not None:
        links.append(f"[← {previous['name']}]({previous['slug']}.md)")
    links.append("[All abilities](index.md)")
    if following is not None:
        links.append(f"[{following['name']} →]({following['slug']}.md)")
    return " · ".join(links)
