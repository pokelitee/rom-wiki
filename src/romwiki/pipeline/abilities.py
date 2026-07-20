from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.errors import DataSourceError
from romwiki.sources import PokeDBGeneration


def build_ability_dataset(
    pokemon_dataset: dict[str, Any], pokedb: PokeDBGeneration
) -> dict[str, Any]:
    if pokemon_dataset.get("dataset") != "pokemon":
        raise DataSourceError("Abilities require an enriched Pokémon dataset")
    ability_names = pokemon_dataset.get("ability_names")
    if not isinstance(ability_names, list) or len(ability_names) != 124:
        raise DataSourceError("Expected exactly 124 ROM-derived ability names")

    pokemon_by_ability: dict[int, list[dict[str, Any]]] = {}
    for pokemon in pokemon_dataset.get("records", []):
        if not pokemon.get("public"):
            continue
        slots_by_ability: dict[int, list[int]] = {}
        for slot, ability in enumerate(pokemon.get("abilities", []), start=1):
            ability_id = ability.get("id")
            if isinstance(ability_id, int) and ability_id:
                slots_by_ability.setdefault(ability_id, []).append(slot)
        for ability_id, slots in slots_by_ability.items():
            pokemon_by_ability.setdefault(ability_id, []).append(
                {
                    "member": pokemon["member"],
                    "national_dex_id": pokemon["national_dex_id"],
                    "slug": pokemon["slug"],
                    "name": pokemon["name"],
                    "slots": slots,
                }
            )

    records = [
        {
            "ability_id": ability_id,
            "slug": pokedb.ability_name(ability_id),
            "name": ability_names[ability_id],
            "pokemon": pokemon_by_ability.get(ability_id, []),
        }
        for ability_id in range(1, len(ability_names))
    ]
    return {
        "schema_version": 1,
        "game": pokemon_dataset["game"],
        "dataset": "abilities",
        "record_count": len(records),
        "assigned_record_count": sum(bool(record["pokemon"]) for record in records),
        "source": pokemon_dataset["source"],
        "name_source": pokemon_dataset.get("name_sources", {}).get("ability_names"),
        "records": records,
    }


def write_ability_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
