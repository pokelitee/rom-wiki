from __future__ import annotations

from typing import Any

from romwiki.pipeline.encounter_identity import encounter_route_key
from romwiki.sources import PokeDBGeneration
from romwiki.util.text import title_case_slug


def enrich_conditional_encounter_area(
    engine: Any,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any]:
    if "walking_variants" in source:
        return _enrich_hgss_encounter_area(
            engine, source, pokedb, sprite_version, pokemon_names
        )
    walking = {
        "rate": source["walking_rate"],
        "slots": [
            {
                **slot,
                "chance": engine.WALKING_SLOT_CHANCES[index],
                "pokemon": _encounter_pokemon(
                    slot["species_id"], pokedb, sprite_version, pokemon_names
                ),
            }
            for index, slot in enumerate(source["walking_slots"])
        ],
    }
    methods = {
        name: {
            "rate": method["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"], pokedb, sprite_version, pokemon_names
                    ),
                }
                for index, slot in enumerate(method["slots"])
            ],
        }
        for name, method, chances in (
            ("surf", source["surf"], engine.WATER_SLOT_CHANCES),
            ("old_rod", source["old_rod"], engine.FISHING_SLOT_CHANCES),
            ("good_rod", source["good_rod"], engine.FISHING_SLOT_CHANCES),
            ("super_rod", source["super_rod"], engine.FISHING_SLOT_CHANCES),
        )
    }
    special = {
        "swarm": _encounter_special_slots(
            source["swarm_species_ids"],
            source["walking_slots"],
            engine.SWARM_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
        ),
        "day": _encounter_special_slots(
            source["day_species_ids"],
            source["walking_slots"],
            engine.TIMED_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
        ),
        "night": _encounter_special_slots(
            source["night_species_ids"],
            source["walking_slots"],
            engine.TIMED_SLOT_INDICES,
            engine.WALKING_SLOT_CHANCES,
            pokedb,
            sprite_version,
            pokemon_names,
        ),
        "radar": _encounter_pokemon_list(
            source["radar_species_ids"], pokedb, sprite_version, pokemon_names
        ),
        "unown_forms": _resolve_unown_forms(engine, source["unown_table_id"]),
        "dual_slot": {
            game: _encounter_special_slots(
                species_ids,
                source["walking_slots"],
                engine.DUAL_SLOT_SLOT_INDICES,
                engine.WALKING_SLOT_CHANCES,
                pokedb,
                sprite_version,
                pokemon_names,
            )
            for game, species_ids in source["dual_slot_species_ids"].items()
        },
    }
    active = bool(
        walking["rate"]
        or any(method["rate"] for method in methods.values())
        or any(entry["pokemon"] for entry in special["swarm"])
        or any(entry["pokemon"] for entry in special["day"])
        or any(entry["pokemon"] for entry in special["night"])
        or any(special["radar"])
        or special["unown_forms"]
        or any(
            entry["pokemon"]
            for entries in special["dual_slot"].values()
            for entry in entries
        )
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
        "bonus_slot_methodology_source": engine.BONUS_SLOT_METHODOLOGY_SOURCE,
        "encounter_form_rates": source["encounter_form_rates"],
        "unown_table_id": source["unown_table_id"],
        "provenance": source["provenance"],
    }


def _enrich_hgss_encounter_area(
    engine: Any,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None,
    pokemon_names: list[str] | None,
) -> dict[str, Any]:
    walking_variants = {
        period: {
            "rate": source["walking_rate"],
            "slots": [
                {
                    **slot,
                    "chance": engine.WALKING_SLOT_CHANCES[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"], pokedb, sprite_version, pokemon_names
                    ),
                }
                for index, slot in enumerate(slots)
            ],
        }
        for period, slots in source["walking_variants"].items()
    }
    methods = {
        name: {
            "rate": source[name]["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"], pokedb, sprite_version, pokemon_names
                    ),
                }
                for index, slot in enumerate(source[name]["slots"])
            ],
        }
        for name, chances in (
            ("surf", engine.WATER_SLOT_CHANCES),
            ("rock_smash", engine.ROCK_SMASH_SLOT_CHANCES),
            ("old_rod", engine.FISHING_SLOT_CHANCES),
            ("good_rod", engine.FISHING_SLOT_CHANCES),
            ("super_rod", engine.FISHING_SLOT_CHANCES),
        )
    }
    special = {
        "format": "hgss",
        "land_swarm": _encounter_pokemon(
            source["swarm_species_ids"][0], pokedb, sprite_version, pokemon_names
        ),
        "surf_swarm": _encounter_pokemon(
            source["swarm_species_ids"][1], pokedb, sprite_version, pokemon_names
        ),
        "hoenn_radio": _encounter_pokemon_list(
            source["radio_species_ids"][:2], pokedb, sprite_version, pokemon_names
        ),
        "sinnoh_radio": _encounter_pokemon_list(
            source["radio_species_ids"][2:], pokedb, sprite_version, pokemon_names
        ),
        "night_fishing": _encounter_pokemon(
            source["night_fishing_species_id"],
            pokedb,
            sprite_version,
            pokemon_names,
        ),
        "fishing_swarm": _encounter_pokemon(
            source["fishing_swarm_species_id"],
            pokedb,
            sprite_version,
            pokemon_names,
        ),
    }
    locations = source.get("locations", [])
    names = list(dict.fromkeys(location["name"] for location in locations))
    return {
        "area_id": source["area_id"],
        "name": " / ".join(names) or f"Encounter Area {source['area_id']:03}",
        "locations": locations,
        "active": bool(
            source["walking_rate"]
            or any(method["rate"] for method in methods.values())
            or any(value for key, value in special.items() if key != "format")
        ),
        "walking": walking_variants["day"],
        "walking_variants": walking_variants,
        **methods,
        "special": special,
        "provenance": source["provenance"],
    }


def enrich_seasonal_encounter_area(
    engine: Any,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any]:
    methods = {
        name: {
            "rate": source[name]["rate"],
            "slots": [
                {
                    **slot,
                    "chance": chances[index],
                    "pokemon": _encounter_pokemon(
                        slot["species_id"], pokedb, sprite_version, pokemon_names
                    ),
                }
                for index, slot in enumerate(source[name]["slots"])
            ],
        }
        for name, chances in zip(
            engine.ENCOUNTER_METHOD_NAMES,
            engine.ENCOUNTER_METHOD_SLOT_CHANCES,
            strict=True,
        )
    }
    active = any(method["rate"] for method in methods.values())
    location_names = list(dict.fromkeys(source.get("location_names", [])))
    label = f"Map {source['map_index']:03}"
    if source.get("season"):
        label += f" ({source['season'].title()})"
    return {
        "area_id": source["area_id"],
        "map_index": source["map_index"],
        "season": source.get("season"),
        "slug": encounter_route_key(source),
        "name": " / ".join(location_names) or label,
        "location_names": location_names,
        "active": active,
        **methods,
        "provenance": source["provenance"],
    }


def pokemon_display_name(
    species_id: int, slug: str, pokemon_names: list[str] | None
) -> str:
    if pokemon_names is not None and 0 < species_id < len(pokemon_names):
        return pokemon_names[species_id]
    return title_case_slug(slug)


def _encounter_pokemon_list(
    species_ids: list[int],
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> list[dict[str, Any] | None]:
    return [
        _encounter_pokemon(species_id, pokedb, sprite_version, pokemon_names)
        for species_id in species_ids
    ]


def _encounter_pokemon(
    species_id: int | None,
    pokedb: PokeDBGeneration,
    sprite_version: str | None = None,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any] | None:
    if species_id in {None, 0}:
        return None
    reference = pokedb.pokemon_for_id(species_id)
    return {
        "id": species_id,
        "slug": reference["name"],
        "name": pokemon_display_name(species_id, reference["name"], pokemon_names),
        "sprite": pokedb.pokemon_sprite(reference, sprite_version),
    }


def _encounter_special_slots(
    species_ids: tuple[int, ...],
    walking_slots: list[dict[str, Any]],
    slot_indices: tuple[int, ...],
    chances: tuple[int, ...],
    pokedb: PokeDBGeneration,
    sprite_version: str | None,
    pokemon_names: list[str] | None,
) -> list[dict[str, Any]]:
    """Apply special species replacements without changing slot odds or levels."""
    return [
        {
            "pokemon": _encounter_pokemon(
                species_id, pokedb, sprite_version, pokemon_names
            ),
            "level": walking_slots[slot_index]["level"],
            "chance": chances[slot_index],
        }
        for species_id, slot_index in zip(species_ids, slot_indices, strict=True)
    ]


def _resolve_unown_forms(engine: Any, unown_table_id: int) -> list[str]:
    index = unown_table_id - 1
    if not (0 <= index < len(engine.UNOWN_FORM_TABLES)):
        return []
    return [
        engine.UNOWN_FORM_NAMES[form_id] for form_id in engine.UNOWN_FORM_TABLES[index]
    ]
