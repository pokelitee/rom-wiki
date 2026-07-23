from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.schema.versions import ABILITIES_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.json_io import write_json_atomic


def build_ability_dataset(
    pokemon_dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    *,
    reference_version: str | None = None,
) -> dict[str, Any]:
    if pokemon_dataset.get("dataset") != "pokemon":
        raise DataSourceError("Abilities require an enriched Pokémon dataset")
    engine_id = pokemon_dataset.get("engine")
    if not isinstance(engine_id, str):
        raise DataSourceError("Pokémon dataset must declare its source engine")
    expected_count = get_engine(engine_id).enrich.ABILITY_NAME_COUNT
    ability_names = pokemon_dataset.get("ability_names")
    if not isinstance(ability_names, list) or len(ability_names) != expected_count:
        raise DataSourceError(
            f"Expected exactly {expected_count} ROM-derived ability names"
        )

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
                    "sprite": pokemon.get("sprite"),
                    "slots": slots,
                }
            )

    records = [
        {
            "ability_id": ability_id,
            "slug": pokedb.ability_name(ability_id),
            "name": ability_names[ability_id],
            "reference": pokedb.ability_reference(ability_id, reference_version),
            "pokemon": pokemon_by_ability.get(ability_id, []),
        }
        for ability_id in range(1, len(ability_names))
    ]
    return {
        "schema_version": ABILITIES_ENRICHED_SCHEMA_VERSION,
        "game": pokemon_dataset["game"],
        "dataset": "abilities",
        "record_count": len(records),
        "assigned_record_count": sum(bool(record["pokemon"]) for record in records),
        "source": pokemon_dataset["source"],
        "name_source": pokemon_dataset.get("name_sources", {}).get("ability_names"),
        "records": records,
    }


def write_ability_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
