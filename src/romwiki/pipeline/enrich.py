from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import PERSONAL_FORM_MEMBERS, PERSONAL_INTERNAL_MEMBERS
from romwiki.errors import DataSourceError
from romwiki.sources import PokeDBGeneration


TYPE_NAMES = (
    "normal", "fighting", "flying", "poison", "ground", "rock", "bug",
    "ghost", "steel", "unknown", "fire", "water", "grass", "electric",
    "psychic", "ice", "dragon", "dark",
)
EGG_GROUP_NAMES = (
    "none", "monster", "water-1", "bug", "flying", "field", "fairy",
    "grass", "human-like", "water-3", "mineral", "amorphous", "water-2",
    "ditto", "dragon", "undiscovered",
)
GROWTH_RATE_NAMES = (
    "medium-fast", "erratic", "fluctuating", "medium-slow", "fast", "slow",
)
COLOR_NAMES = (
    "red", "blue", "yellow", "green", "black", "brown", "purple", "gray",
    "white", "pink", "internal",
)


def enrich_personal_dataset(
    dataset: dict[str, Any], pokedb: PokeDBGeneration
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list) or len(source_records) != 508:
        raise DataSourceError("Expected exactly 508 Gen IV personal records")

    records = []
    for expected_member, source in enumerate(source_records):
        if source.get("species_id") != expected_member:
            raise DataSourceError("Personal records must be ordered by member ID")
        records.append(_enrich_record(source, pokedb))
    return {
        "schema_version": 1,
        "game": dataset["game"],
        "dataset": "pokemon",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": dataset["source"],
        "records": records,
    }


def enrich_encounter_dataset(
    dataset: dict[str, Any], pokedb: PokeDBGeneration
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Encounter dataset records must be a list")

    records = []
    for expected_area, source in enumerate(source_records):
        if source.get("area_id") != expected_area:
            raise DataSourceError("Encounter records must be ordered by area ID")
        records.append(_enrich_encounter_area(source, pokedb))
    return {
        "schema_version": 1,
        "game": dataset["game"],
        "dataset": "wild_encounters",
        "record_count": len(records),
        "active_record_count": sum(record["active"] for record in records),
        "source": dataset["source"],
        "records": records,
    }


def write_enriched_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    _write_json(output_path, dataset)


def _enrich_encounter_area(
    source: dict[str, Any], pokedb: PokeDBGeneration
) -> dict[str, Any]:
    walking = {
        "rate": source["walking_rate"],
        "slots": [
            {**slot, "pokemon": _encounter_pokemon(slot["species_id"], pokedb)}
            for slot in source["walking_slots"]
        ],
    }
    methods = {
        name: {
            "rate": method["rate"],
            "slots": [
                {**slot, "pokemon": _encounter_pokemon(slot["species_id"], pokedb)}
                for slot in method["slots"]
            ],
        }
        for name, method in (
            ("surf", source["surf"]),
            ("old_rod", source["old_rod"]),
            ("good_rod", source["good_rod"]),
            ("super_rod", source["super_rod"]),
        )
    }
    special = {
        "swarm": _encounter_pokemon_list(source["swarm_species_ids"], pokedb),
        "day": _encounter_pokemon_list(source["day_species_ids"], pokedb),
        "night": _encounter_pokemon_list(source["night_species_ids"], pokedb),
        "radar": _encounter_pokemon_list(source["radar_species_ids"], pokedb),
        "forms": _encounter_pokemon_list(source["form_species_ids"], pokedb),
        "dual_slot": {
            game: _encounter_pokemon_list(species_ids, pokedb)
            for game, species_ids in source["dual_slot_species_ids"].items()
        },
    }
    active = bool(
        walking["rate"]
        or any(method["rate"] for method in methods.values())
        or any(
            value
            for values in special.values()
            if isinstance(values, list)
            for value in values
        )
        or any(value for values in special["dual_slot"].values() for value in values)
    )
    locations = source.get("locations", [])
    names = list(dict.fromkeys(location["name"] for location in locations))
    return {
        "area_id": source["area_id"],
        "name": " / ".join(names) or f"Encounter Area {source['area_id']:03}",
        "locations": locations,
        "active": active,
        "walking": walking,
        **methods,
        "special": special,
        "unknown_value": source["unknown_value"],
        "provenance": source["provenance"],
    }


def _encounter_pokemon_list(
    species_ids: list[int], pokedb: PokeDBGeneration
) -> list[dict[str, Any] | None]:
    return [_encounter_pokemon(species_id, pokedb) for species_id in species_ids]


def _encounter_pokemon(
    species_id: int, pokedb: PokeDBGeneration
) -> dict[str, Any] | None:
    if species_id == 0:
        return None
    reference = pokedb.pokemon_for_id(species_id)
    return {
        "id": species_id,
        "slug": reference["name"],
        "name": _display_name(reference["name"]),
    }


def _enrich_record(source: dict[str, Any], pokedb: PokeDBGeneration) -> dict[str, Any]:
    member = source["species_id"]
    if member in PERSONAL_INTERNAL_MEMBERS:
        slug = PERSONAL_INTERNAL_MEMBERS[member]
        identity = {"national_dex_id": None, "base_species": None, "form": None}
        public = False
    elif member in PERSONAL_FORM_MEMBERS:
        slug = PERSONAL_FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        base_species = reference["species"]
        identity = {
            "national_dex_id": pokedb.pokemon_for_species(base_species)["id"],
            "base_species": base_species,
            "form": slug.removeprefix(f"{base_species}-"),
        }
        public = True
    else:
        reference = pokedb.pokemon_for_id(member)
        slug = reference["name"]
        identity = {
            "national_dex_id": member,
            "base_species": reference["species"],
            "form": None,
        }
        public = True

    return {
        "member": member,
        "slug": slug,
        "name": _display_name(slug),
        "public": public,
        **identity,
        "base_stats": source["base_stats"],
        "types": [_named_id(value, TYPE_NAMES, "type") for value in source["type_ids"]],
        "catch_rate": source["catch_rate"],
        "base_experience": source["base_experience"],
        "ev_yields": source["ev_yields"],
        "held_items": [
            {"rarity": rarity, "id": value, "name": pokedb.item_name(value)}
            for rarity, value in (
                ("common", source["wild_held_items"]["common"]),
                ("rare", source["wild_held_items"]["rare"]),
            )
        ],
        "gender_ratio": source["gender_ratio"],
        "hatch_cycles": source["hatch_cycles"],
        "base_friendship": source["base_friendship"],
        "growth_rate": _named_id(source["growth_rate_id"], GROWTH_RATE_NAMES, "growth rate"),
        "egg_groups": [
            _named_id(value, EGG_GROUP_NAMES, "egg group")
            for value in source["egg_group_ids"]
        ],
        "abilities": [
            {"id": value, "name": pokedb.ability_name(value)}
            for value in source["ability_ids"]
        ],
        "safari_flee_rate": source["safari_flee_rate"],
        "body_color": _named_id(source["body_color_id"], COLOR_NAMES, "body color"),
        "flip_sprite": source["flip_sprite"],
        "machines": [
            {"id": value, "name": _machine_name(value)} for value in source["machine_ids"]
        ],
        "provenance": source["provenance"],
    }


def _named_id(value: int, names: tuple[str, ...], label: str) -> dict[str, Any]:
    if not 0 <= value < len(names):
        raise DataSourceError(f"Unknown Gen IV {label} ID: {value}")
    return {"id": value, "name": names[value]}


def _machine_name(machine_id: int) -> str:
    if machine_id <= 92:
        return f"TM{machine_id:02}"
    if machine_id <= 100:
        return f"HM{machine_id - 92:02}"
    return f"MACHINE{machine_id:03}"


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
