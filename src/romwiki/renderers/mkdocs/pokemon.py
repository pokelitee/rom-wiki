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
    machines = record["machines"]
    tutor_moves = record.get("tutor_moves", [])
    level_up_moves = record.get("level_up_moves", [])
    egg_moves = record.get("egg_moves", [])
    evolutions = record.get("evolutions", [])
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
        "## Evolutions",
        "",
    ]
    if evolutions:
        lines.extend(
            [
                "| Evolves into | Condition | Method ID |",
                "| ------------ | --------- | --------: |",
                *[
                    (
                        f"| [{entry['target']['name']}]({entry['target']['slug']}.md) "
                        f"| {_evolution_condition(entry)} | {entry['method_id']} |"
                    )
                    for entry in evolutions
                ],
                "",
            ]
        )
    else:
        lines.extend(["No further evolution.", ""])
    lines.extend(
        [
            "## Compatible machines",
            "",
        ]
    )
    if machines and all("move" in machine for machine in machines):
        lines.extend(
            [
                "| Machine | Move |",
                "| ------- | ---- |",
                *[
                    (
                        f"| {machine['name']} | "
                        f"[{machine['move']['name']}]"
                        f"(../moves/{machine['move']['slug']}.md) |"
                    )
                    for machine in machines
                ],
                "",
            ]
        )
    else:
        lines.extend(
            [
                ", ".join(machine["name"] for machine in machines) or "None",
                "",
            ]
        )
    lines.extend(["## Move tutors", ""])
    if tutor_moves:
        lines.extend(
            [
                "| Move | Location | Requirement |",
                "| ---- | -------- | ---- |",
                *[
                    (
                        f"| [{tutor['move']['name']}]"
                        f"(../moves/{tutor['move']['slug']}.md) | "
                        f"{tutor['location']['name']} | "
                        f"{_tutor_requirement(tutor)} |"
                    )
                    for tutor in tutor_moves
                ],
                "",
            ]
        )
    else:
        lines.extend(["None.", ""])
    lines.extend(["## Level-up moves", ""])
    if level_up_moves:
        lines.extend(
            [
                "| Level | Move |",
                "| ----: | ---- |",
                *[
                    (
                        f"| {entry['level']} | "
                        f"[{entry['move']['name']}](../moves/{entry['move']['slug']}.md) |"
                    )
                    for entry in level_up_moves
                ],
                "",
            ]
        )
    else:
        lines.extend(["No level-up moves.", ""])
    lines.extend(["## Egg moves", ""])
    if egg_moves:
        lines.extend(
            [
                ", ".join(
                    f"[{move['name']}](../moves/{move['slug']}.md)"
                    for move in egg_moves
                ),
                "",
            ]
        )
    else:
        lines.extend(["None.", ""])
    lines.extend(
        [
            "---",
            "",
            (
                "Source: exact ROM record from "
                f"`{record['provenance']['archive']}` member "
                f"`{record['provenance']['member']}`."
            ),
            *(
                [
                    (
                        "Egg move source: exact ROM table entry at overlay offset "
                        f"`0x{record['egg_move_provenance']['overlay_offset']:X}`."
                    )
                ]
                if record.get("egg_move_provenance") is not None
                else []
            ),
            *(
                [
                    (
                        "Level-up learnset source: exact ROM record from "
                        f"`{record['learnset_provenance']['archive']}` member "
                        f"`{record['learnset_provenance']['member']}`."
                    )
                ]
                if record.get("learnset_provenance") is not None
                else []
            ),
            *(
                [
                    (
                        "Evolution source: exact ROM record from "
                        f"`{record['evolution_provenance']['archive']}` member "
                        f"`{record['evolution_provenance']['member']}`."
                    )
                ]
                if record.get("evolution_provenance") is not None
                else []
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _evolution_condition(entry: dict[str, Any]) -> str:
    method = entry["method"]["name"]
    parameter = entry["parameter_data"]
    value = parameter.get("value") if parameter is not None else None
    raw_name = parameter.get("name", "") if parameter is not None else ""
    name = (
        raw_name.replace("-", " ").title()
        if raw_name.islower()
        else raw_name
    )
    conditions = {
        "friendship": "High friendship",
        "friendship-day": "High friendship during the day",
        "friendship-night": "High friendship at night",
        "level": f"Level {value}",
        "trade": "Trade",
        "trade-held-item": f"Trade while holding {name}",
        "use-item": f"Use {name}",
        "level-attack-greater": f"Level {value} with Attack > Defense",
        "level-attack-equal": f"Level {value} with Attack = Defense",
        "level-defense-greater": f"Level {value} with Attack < Defense",
        "level-personality-low": f"Level up; personality branch {value} (low)",
        "level-personality-high": f"Level up; personality branch {value} (high)",
        "level-ninjask": f"Level {value} (Ninjask branch)",
        "level-shedinja": f"Level {value} (Shedinja branch)",
        "beauty": f"Beauty {value}",
        "use-item-male": f"Use {name} (male)",
        "use-item-female": f"Use {name} (female)",
        "level-held-item-day": f"Level up during the day while holding {name}",
        "level-held-item-night": f"Level up at night while holding {name}",
        "level-knowing-move": f"Level up knowing {name}",
        "level-with-party-species": f"Level up with {name} in the party",
        "level-male": f"Level {value} (male)",
        "level-female": f"Level {value} (female)",
        "level-magnetic-field": "Level up in a magnetic field",
        "level-moss-rock": "Level up near a Moss Rock",
        "level-ice-rock": "Level up near an Ice Rock",
    }
    return conditions.get(method, f"{method.replace('-', ' ').title()} ({value})")


def _shard_cost(costs: dict[str, int]) -> str:
    return ", ".join(
        f"{amount} {color.title()}"
        for color, amount in costs.items()
        if amount
    ) or "Free"


def _tutor_requirement(tutor: dict[str, Any]) -> str:
    if tutor.get("kind") == "special":
        return f"Friendship {tutor['minimum_friendship']}"
    return _shard_cost(tutor["shard_costs"])


def _write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
