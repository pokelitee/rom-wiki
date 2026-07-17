from __future__ import annotations

from pathlib import Path
from typing import Any


def render_pokemon_pages(dataset: dict[str, Any], output_root: Path) -> int:
    public_records = [record for record in dataset["records"] if record["public"]]
    output_root.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Pokémon", "", "Extracted Pokémon and form data.", ""]
    for record in public_records:
        filename = f"{record['slug']}.md"
        _write_text(output_root / filename, _render_record(record))
        dex = record["national_dex_id"]
        index_lines.append(f"- [#{dex:03} {record['name']}]({filename})")
    _write_text(output_root / "index.md", "\n".join(index_lines) + "\n")
    return len(public_records)


def _render_record(record: dict[str, Any]) -> str:
    stats = record["base_stats"]
    types = " / ".join(value["name"].title() for value in record["types"])
    abilities = ", ".join(
        value["name"].replace("-", " ").title()
        for value in record["abilities"]
        if value["name"] is not None
    )
    machines = ", ".join(value["name"] for value in record["machines"]) or "None"
    lines = [
        f"# {record['name']}",
        "",
        f"**National Pokédex:** #{record['national_dex_id']:03}",
        "",
        f"**Types:** {types}",
        "",
        f"**Abilities:** {abilities or 'None'}",
        "",
        "## Base stats",
        "",
        "| HP | Attack | Defense | Speed | Sp. Atk | Sp. Def |",
        "| --: | -----: | ------: | ----: | ------: | ------: |",
        (
            f"| {stats['hp']} | {stats['attack']} | {stats['defense']} | "
            f"{stats['speed']} | {stats['special_attack']} | "
            f"{stats['special_defense']} |"
        ),
        "",
        "## Training and breeding",
        "",
        f"- Catch rate: {record['catch_rate']}",
        f"- Base experience: {record['base_experience']}",
        f"- Base friendship: {record['base_friendship']}",
        f"- Hatch cycles: {record['hatch_cycles']}",
        f"- Growth rate: {record['growth_rate']['name'].replace('-', ' ').title()}",
        "- Egg groups: " + " / ".join(
            value["name"].replace("-", " ").title() for value in record["egg_groups"]
        ),
        "",
        "## Compatible machines",
        "",
        machines,
        "",
        "---",
        "",
        (
            "Source: exact ROM record from "
            f"`{record['provenance']['archive']}` member "
            f"`{record['provenance']['member']}`."
        ),
        "",
    ]
    return "\n".join(lines)


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
