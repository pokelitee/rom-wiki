from __future__ import annotations

from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment.references import with_rom_description
from romwiki.schema.enriched import (
    AbilityDataset,
    AbilityEnrichedRecord,
    AbilityPokemon,
    PokemonDataset,
)
from romwiki.schema.versions import ABILITIES_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError


def build_ability_dataset(
    pokemon_dataset: PokemonDataset,
    pokedb: PokeDBGeneration,
    pickup_dataset: dict[str, Any] | None = None,
    *,
    reference_version: str | None = None,
) -> AbilityDataset:
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
    descriptions = pokemon_dataset.get("ability_descriptions")
    if descriptions is not None and (
        not isinstance(descriptions, list) or len(descriptions) != expected_count
    ):
        raise DataSourceError(
            f"Expected exactly {expected_count} ROM-derived ability descriptions"
        )

    pokemon_by_ability: dict[int, list[AbilityPokemon]] = {}
    for pokemon in pokemon_dataset.get("records", []):
        if not pokemon.get("public"):
            continue
        slots_by_ability: dict[int, list[int]] = {}
        hidden_by_ability: dict[int, bool] = {}
        for slot, ability in enumerate(pokemon.get("abilities", []), start=1):
            ability_id = ability.get("id")
            if isinstance(ability_id, int) and ability_id:
                slots_by_ability.setdefault(ability_id, []).append(slot)
                if ability.get("is_hidden"):
                    hidden_by_ability[ability_id] = True
        for ability_id, slots in slots_by_ability.items():
            pokemon_by_ability.setdefault(ability_id, []).append(
                {
                    "member": pokemon["member"],
                    "national_dex_id": pokemon["national_dex_id"],
                    "slug": pokemon["slug"],
                    "name": pokemon["name"],
                    "sprite": pokemon.get("sprite"),
                    "slots": slots,
                    "is_hidden": hidden_by_ability.get(ability_id, False),
                }
            )

    # Generation V's pickup table is one shared, sliding-window array (see
    # gen5/shared/pickup.py) rather than Generation IV's separate common/rare
    # item lists plus a rate curve, so its raw dataset carries a
    # `level_ranges` field directly instead of Gen IV's `tables` shape; it
    # also has no Honey Gather / Honey Tree equivalent to attach.
    is_sliding_pickup = pickup_dataset is not None and "level_ranges" in pickup_dataset
    pickup_tables = (
        pickup_dataset["tables"]
        if pickup_dataset is not None and not is_sliding_pickup
        else None
    )
    records: list[AbilityEnrichedRecord] = []
    for ability_id in range(1, len(ability_names)):
        slug = pokedb.ability_name(ability_id)
        pickup = None
        if is_sliding_pickup and pickup_dataset is not None and slug == "pickup":
            pickup = {"level_ranges": pickup_dataset["level_ranges"]}
        elif pickup_tables is not None and slug == "pickup":
            pickup = {
                "common_items": pickup_tables["common_items"],
                "rare_items": pickup_tables["rare_items"],
                "common_rate": pickup_tables["common_rate"],
            }
        elif pickup_tables is not None and slug == "honey-gather":
            pickup = {"honey_gather_rate": pickup_tables["honey_gather_rate"]}
        records.append(
            {
                "ability_id": ability_id,
                "slug": slug,
                "name": ability_names[ability_id],
                "reference": with_rom_description(
                    pokedb.ability_reference(ability_id, reference_version),
                    descriptions[ability_id] if descriptions is not None else None,
                ),
                "pokemon": pokemon_by_ability.get(ability_id, []),
                "pickup": pickup,
            }
        )
    return {
        "schema_version": ABILITIES_ENRICHED_SCHEMA_VERSION,
        "game": pokemon_dataset["game"],
        "engine": pokemon_dataset["engine"],
        "dataset": "abilities",
        "record_count": len(records),
        "assigned_record_count": sum(bool(record["pokemon"]) for record in records),
        "source": pokemon_dataset["source"],
        "name_source": pokemon_dataset.get("name_sources", {}).get("ability_names"),
        "description_source": pokemon_dataset.get("description_sources", {}).get(
            "ability_descriptions"
        ),
        "records": records,
    }
