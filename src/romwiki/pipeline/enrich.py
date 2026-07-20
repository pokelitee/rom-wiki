from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
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
DAMAGE_CLASS_NAMES = ("physical", "special", "status")
EVOLUTION_METHOD_NAMES = (
    "none",
    "friendship",
    "friendship-day",
    "friendship-night",
    "level",
    "trade",
    "trade-held-item",
    "use-item",
    "level-attack-greater",
    "level-attack-equal",
    "level-defense-greater",
    "level-personality-low",
    "level-personality-high",
    "level-ninjask",
    "level-shedinja",
    "beauty",
    "use-item-male",
    "use-item-female",
    "level-held-item-day",
    "level-held-item-night",
    "level-knowing-move",
    "level-with-party-species",
    "level-male",
    "level-female",
    "level-magnetic-field",
    "level-moss-rock",
    "level-ice-rock",
)
_EVOLUTION_LEVEL_PARAMETERS = {4, 8, 9, 10, 13, 14, 22, 23}
_EVOLUTION_ITEM_PARAMETERS = {6, 7, 16, 17, 18, 19}
_EVOLUTION_PERSONALITY_PARAMETERS = {11, 12}


def enrich_personal_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    learnset_dataset: dict[str, Any] | None = None,
    evolution_dataset: dict[str, Any] | None = None,
    machine_dataset: dict[str, Any] | None = None,
    tutor_dataset: dict[str, Any] | None = None,
    egg_move_dataset: dict[str, Any] | None = None,
    *,
    type_names: Mapping[int, str] | None = None,
    move_names: Mapping[int, str] | None = None,
    sprite_version: str | None = None,
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list) or len(source_records) != 508:
        raise DataSourceError("Expected exactly 508 Gen IV personal records")
    type_names = _resolve_type_names(dataset, type_names)
    move_names = _resolve_move_names(dataset, move_names)
    ability_names = _resolve_ability_names(dataset)
    item_names = _resolve_item_names(dataset)

    learnsets = _validate_learnsets(learnset_dataset, dataset["game"])
    evolutions = _validate_evolutions(evolution_dataset, dataset["game"])
    evolution_item_names = _validate_evolution_item_names(evolution_dataset)
    machines = _validate_machines(machine_dataset, dataset["game"])
    tutors, tutor_ids_by_member, tutor_locations = _validate_tutors(
        tutor_dataset, dataset["game"]
    )
    egg_moves = _validate_egg_moves(egg_move_dataset, dataset["game"])
    records = []
    for expected_member, source in enumerate(source_records):
        if source.get("species_id") != expected_member:
            raise DataSourceError("Personal records must be ordered by member ID")
        records.append(
            _enrich_record(
                source,
                pokedb,
                learnsets[expected_member],
                evolutions[expected_member],
                evolution_item_names,
                machines,
                tutors,
                tutor_ids_by_member.get(expected_member, []),
                tutor_locations,
                egg_moves.get(expected_member),
                type_names,
                move_names,
                ability_names,
                item_names,
                sprite_version,
            )
        )
    enriched = {
        "schema_version": 1,
        "game": dataset["game"],
        "dataset": "pokemon",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": dataset["source"],
        "records": records,
    }
    if learnset_dataset is not None:
        enriched["supplemental_sources"] = {
            "level_up_learnsets": learnset_dataset["source"]
        }
    if evolution_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["evolutions"] = (
            evolution_dataset["source"]
        )
    if machine_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["machines"] = (
            machine_dataset["source"]
        )
    if tutor_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["move_tutors"] = (
            tutor_dataset["source"]
        )
    if egg_move_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["egg_moves"] = (
            egg_move_dataset["source"]
        )
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    if "ability_names" in dataset:
        enriched["ability_names"] = dataset["ability_names"]
    return enriched


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


def enrich_trainer_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    *,
    move_names: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Trainer dataset records must be a list")
    move_names = _resolve_move_names(dataset, move_names)
    item_names = _resolve_item_names(dataset)
    records = []
    for expected_id, source in enumerate(source_records):
        if source.get("trainer_id") != expected_id:
            raise DataSourceError("Trainer records must be ordered by trainer ID")
        records.append(_enrich_trainer(source, pokedb, move_names, item_names))
    enriched = {
        "schema_version": 1,
        "game": dataset["game"],
        "dataset": "trainers",
        "record_count": len(records),
        "active_record_count": sum(bool(record["party"]) for record in records),
        "linked_record_count": sum(bool(record["locations"]) for record in records),
        "location_reference_count": sum(len(record["locations"]) for record in records),
        "source": dataset["source"],
        "records": records,
    }
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    return enriched


def enrich_move_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    machine_dataset: dict[str, Any] | None = None,
    tutor_dataset: dict[str, Any] | None = None,
    egg_move_dataset: dict[str, Any] | None = None,
    *,
    type_names: Mapping[int, str] | None = None,
    move_names: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list) or len(source_records) != 471:
        raise DataSourceError("Expected exactly 471 Gen IV move records")
    rom_move_names = _reference_name_table(dataset, "move_names", 468)
    type_names = _resolve_type_names(dataset, type_names)
    move_names = _resolve_move_names(dataset, move_names)

    machines = _validate_machines(machine_dataset, dataset["game"])
    machines_by_move: dict[int, list[dict[str, Any]]] = {}
    for machine in machines.values():
        machines_by_move.setdefault(machine["move_id"], []).append(machine)
    tutors, tutor_ids_by_member, tutor_locations = _validate_tutors(
        tutor_dataset, dataset["game"]
    )
    members_by_tutor: dict[int, list[int]] = {tutor_id: [] for tutor_id in tutors}
    for member, tutor_ids in tutor_ids_by_member.items():
        for tutor_id in tutor_ids:
            members_by_tutor[tutor_id].append(member)
    tutors_by_move: dict[int, list[dict[str, Any]]] = {}
    for tutor_id, tutor in tutors.items():
        tutors_by_move.setdefault(tutor["move_id"], []).append(
            {
                **tutor,
                "location": _tutor_location(tutor, tutor_locations),
                "compatible_pokemon": [
                    _personal_member_reference(member, pokedb)
                    for member in members_by_tutor[tutor_id]
                ],
            }
        )
    egg_moves = _validate_egg_moves(egg_move_dataset, dataset["game"])
    egg_move_pokemon: dict[int, list[dict[str, Any]]] = {}
    for species_id, egg_move_set in egg_moves.items():
        pokemon = _personal_member_reference(species_id, pokedb)
        for move_id in egg_move_set["move_ids"]:
            egg_move_pokemon.setdefault(move_id, []).append(pokemon)
    records = []
    for expected_id, source in enumerate(source_records):
        if source.get("move_id") != expected_id:
            raise DataSourceError("Move records must be ordered by member ID")
        public = 1 <= expected_id <= 467
        slug = (
            _move_name(expected_id, pokedb, move_names)
            if public
            else f"internal-move-{expected_id}"
        )
        records.append(
            {
                **source,
                "slug": slug,
                "name": (
                    rom_move_names[expected_id]
                    if public and rom_move_names is not None
                    else _display_name(slug)
                ),
                "replaces": (
                    _replaced_move(expected_id, slug, pokedb) if public else None
                ),
                "public": public,
                "damage_class": _named_id(
                    source["damage_class_id"], DAMAGE_CLASS_NAMES, "move class"
                ),
                "type": _type_id(source["type_id"], type_names),
                "machines": machines_by_move.get(expected_id, []),
                "tutors": tutors_by_move.get(expected_id, []),
                "egg_move_pokemon": egg_move_pokemon.get(expected_id, []),
            }
        )
    enriched = {
        "schema_version": 1,
        "game": dataset["game"],
        "dataset": "moves",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": dataset["source"],
        "records": records,
    }
    if machine_dataset is not None:
        enriched["supplemental_sources"] = {"machines": machine_dataset["source"]}
    if tutor_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["move_tutors"] = (
            tutor_dataset["source"]
        )
    if egg_move_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["egg_moves"] = (
            egg_move_dataset["source"]
        )
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    return enriched


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


_TRAINER_FORMS = {
    (386, 1): "deoxys-attack",
    (386, 2): "deoxys-defense",
    (386, 3): "deoxys-speed",
    (413, 1): "wormadam-sandy",
    (413, 2): "wormadam-trash",
    (479, 1): "rotom-heat",
    (479, 2): "rotom-wash",
    (479, 3): "rotom-frost",
    (479, 4): "rotom-fan",
    (479, 5): "rotom-mow",
    (487, 1): "giratina-origin",
    (492, 1): "shaymin-sky",
}
_TRAINER_COSMETIC_FORMS = {
    (422, 1): "East Sea",
    (423, 1): "East Sea",
}


def _enrich_trainer(
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    item_names: list[str] | None,
) -> dict[str, Any]:
    party = []
    for pokemon in source["party"]:
        species_id = pokemon["species_id"]
        form_id = pokemon["form_id"]
        if form_id:
            slug = _TRAINER_FORMS.get((species_id, form_id))
            cosmetic_form = _TRAINER_COSMETIC_FORMS.get((species_id, form_id))
            if slug is not None:
                reference = pokedb.pokemon_for_name(slug)
            elif cosmetic_form is not None:
                reference = pokedb.pokemon_for_id(species_id)
            else:
                raise DataSourceError(
                    f"Unknown trainer form {form_id} for species {species_id}"
                )
        else:
            reference = pokedb.pokemon_for_id(species_id)
            cosmetic_form = None
        party.append(
            {
                **pokemon,
                "pokemon": {
                    "id": species_id,
                    "slug": reference["name"],
                    "name": _display_name(reference["name"])
                    + (f" ({cosmetic_form})" if cosmetic_form else ""),
                },
                "held_item": {
                    **_item_reference(pokemon["held_item_id"], pokedb, item_names),
                }
                if pokemon["held_item_id"] is not None
                else None,
                "moves": [
                    {"id": move_id, "name": _move_name(move_id, pokedb, move_names)}
                    for move_id in pokemon["move_ids"]
                    if move_id
                ],
            }
        )
    return {
        **source,
        "party": party,
        "reward_items": [
            _item_reference(item_id, pokedb, item_names)
            for item_id in source["reward_item_ids"]
            if item_id
        ],
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


def _enrich_record(
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    learnset: dict[str, Any] | None,
    evolution_set: dict[str, Any] | None,
    evolution_item_names: list[str],
    machines: dict[int, dict[str, Any]],
    tutors: dict[int, dict[str, Any]],
    tutor_ids: list[int],
    tutor_locations: list[str],
    egg_move_set: dict[str, Any] | None,
    type_names: Mapping[int, str] | None,
    move_names: Mapping[int, str] | None,
    ability_names: list[str] | None,
    item_names: list[str] | None,
    sprite_version: str | None,
) -> dict[str, Any]:
    member = source["species_id"]
    if member in PERSONAL_INTERNAL_MEMBERS:
        slug = PERSONAL_INTERNAL_MEMBERS[member]
        identity = {"national_dex_id": None, "base_species": None, "form": None}
        sprite = None
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
        sprite = pokedb.pokemon_sprite(reference, sprite_version)
        public = True
    else:
        reference = pokedb.pokemon_for_id(member)
        slug = reference["name"]
        identity = {
            "national_dex_id": member,
            "base_species": reference["species"],
            "form": None,
        }
        sprite = pokedb.pokemon_sprite(reference, sprite_version)
        public = True

    return {
        "member": member,
        "slug": slug,
        "name": _display_name(slug),
        "public": public,
        **identity,
        "sprite": sprite,
        "base_stats": source["base_stats"],
        "types": [_type_id(value, type_names) for value in source["type_ids"]],
        "catch_rate": source["catch_rate"],
        "base_experience": source["base_experience"],
        "ev_yields": source["ev_yields"],
        "held_items": [
            {"rarity": rarity, **_item_reference(value, pokedb, item_names)}
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
            _ability_id(value, pokedb, ability_names)
            for value in source["ability_ids"]
        ],
        "safari_flee_rate": source["safari_flee_rate"],
        "body_color": _named_id(source["body_color_id"], COLOR_NAMES, "body color"),
        "flip_sprite": source["flip_sprite"],
        "machines": _enrich_compatible_machines(
            source["machine_ids"], machines, pokedb, move_names
        ),
        "tutor_moves": _enrich_compatible_tutors(
            tutor_ids, tutors, tutor_locations, pokedb, move_names
        ),
        "level_up_moves": _enrich_level_up_moves(learnset, pokedb, move_names),
        "learnset_provenance": learnset["provenance"] if learnset is not None else None,
        "egg_moves": _enrich_egg_moves(egg_move_set, pokedb, move_names),
        "egg_move_provenance": (
            {
                "overlay_offset": egg_move_set["overlay_offset"],
                "table_index": egg_move_set["table_index"],
            }
            if egg_move_set is not None
            else None
        ),
        "evolutions": _enrich_evolutions(
            evolution_set, pokedb, evolution_item_names, move_names
        ),
        "evolution_provenance": (
            evolution_set["provenance"] if evolution_set is not None else None
        ),
        "provenance": source["provenance"],
    }


def _validate_learnsets(
    dataset: dict[str, Any] | None, game: str
) -> list[dict[str, Any] | None]:
    if dataset is None:
        return [None] * 508
    if dataset.get("game") != game:
        raise DataSourceError("Personal and learnset datasets must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list) or len(records) != 508:
        raise DataSourceError("Expected exactly 508 Gen IV level-up learnsets")
    for expected_member, record in enumerate(records):
        if record.get("species_id") != expected_member:
            raise DataSourceError("Learnsets must be ordered by member ID")
    return records


def _validate_evolutions(
    dataset: dict[str, Any] | None, game: str
) -> list[dict[str, Any] | None]:
    if dataset is None:
        return [None] * 508
    if dataset.get("game") != game:
        raise DataSourceError("Personal and evolution datasets must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list) or len(records) != 508:
        raise DataSourceError("Expected exactly 508 Gen IV evolution records")
    for expected_member, record in enumerate(records):
        if record.get("species_id") != expected_member:
            raise DataSourceError("Evolution records must be ordered by member ID")
    return records


def _validate_egg_moves(
    dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Egg move dataset must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Egg move records must be a list")
    result = {}
    previous_species = 0
    for expected_index, record in enumerate(records):
        species_id = record.get("species_id")
        move_ids = record.get("move_ids")
        if (
            not isinstance(species_id, int)
            or not previous_species < species_id <= 493
            or record.get("table_index") != expected_index
        ):
            raise DataSourceError("Egg move records must be ordered by species ID")
        if not isinstance(move_ids, (list, tuple)) or not move_ids or any(
            not isinstance(move_id, int) or not 1 <= move_id <= 467
            for move_id in move_ids
        ):
            raise DataSourceError("Egg move record contains invalid move IDs")
        if len(move_ids) != len(set(move_ids)):
            raise DataSourceError("Egg move record contains duplicate move IDs")
        result[species_id] = record
        previous_species = species_id
    return result


def _validate_evolution_item_names(dataset: dict[str, Any] | None) -> list[str]:
    if dataset is None:
        return []
    item_names = dataset.get("item_names")
    if not isinstance(item_names, list) or not all(
        isinstance(name, str) for name in item_names
    ):
        raise DataSourceError("Evolution dataset must include ROM item names")
    return item_names


def _validate_machines(
    dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Machine dataset must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list) or len(records) != 100:
        raise DataSourceError("Expected exactly 100 Gen IV machine records")
    result = {}
    for expected_id, record in enumerate(records, start=1):
        if record.get("machine_id") != expected_id:
            raise DataSourceError("Machine records must be ordered by machine ID")
        result[expected_id] = record
    return result


def _validate_tutors(
    dataset: dict[str, Any] | None, game: str
) -> tuple[dict[int, dict[str, Any]], dict[int, list[int]], list[str]]:
    if dataset is None:
        return {}, {}, []
    if dataset.get("game") != game:
        raise DataSourceError("Tutor dataset must be for the same game")
    records = dataset.get("records")
    special_records = dataset.get("special_records", [])
    compatibility = dataset.get("compatibility")
    special_compatibility = dataset.get("special_compatibility", [])
    location_names = dataset.get("location_names")
    if not isinstance(records, list) or not records:
        raise DataSourceError("Tutor records must be a nonempty list")
    if not isinstance(special_records, list):
        raise DataSourceError("Special tutor records must be a list")
    if not isinstance(compatibility, list):
        raise DataSourceError("Tutor compatibility records must be a list")
    if not isinstance(special_compatibility, list):
        raise DataSourceError("Special tutor compatibility records must be a list")
    if not isinstance(location_names, list) or not all(
        isinstance(name, str) for name in location_names
    ):
        raise DataSourceError("Tutor location names must be a list")
    tutors = {}
    for expected_id, record in enumerate(records + special_records, start=1):
        if record.get("tutor_id") != expected_id:
            raise DataSourceError("Tutor records must be ordered by tutor ID")
        if record.get("kind") == "special":
            if not isinstance(record.get("location_name"), str):
                raise DataSourceError("Special tutor has an invalid location")
        else:
            location_id = record.get("location_id")
            if not isinstance(location_id, int) or not 0 <= location_id < len(
                location_names
            ):
                raise DataSourceError("Tutor record references an unknown location")
        tutors[expected_id] = record
    ids_by_member = {}
    for compatibility_group in (compatibility, special_compatibility):
        group_members = set()
        for record in compatibility_group:
            member = record.get("personal_member")
            tutor_ids = record.get("tutor_ids")
            if not isinstance(member, int) or member in group_members:
                raise DataSourceError(
                    "Tutor compatibility has an invalid personal member"
                )
            group_members.add(member)
            if not isinstance(tutor_ids, (list, tuple)) or any(
                value not in tutors for value in tutor_ids
            ):
                raise DataSourceError(
                    "Tutor compatibility references an unknown tutor ID"
                )
            existing = ids_by_member.setdefault(member, [])
            if any(value in existing for value in tutor_ids):
                raise DataSourceError("Tutor compatibility contains duplicate tutor IDs")
            existing.extend(tutor_ids)
    return tutors, ids_by_member, location_names


def _enrich_compatible_tutors(
    tutor_ids: list[int],
    tutors: dict[int, dict[str, Any]],
    location_names: list[str],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    result = []
    for tutor_id in tutor_ids:
        tutor = tutors[tutor_id]
        slug = _move_name(tutor["move_id"], pokedb, move_names)
        if slug is None:
            raise DataSourceError(f"Tutor {tutor_id} references move ID 0")
        result.append(
            {
                **tutor,
                "move": {
                    "id": tutor["move_id"],
                    "slug": slug,
                    "name": _display_name(slug),
                },
                "location": _tutor_location(tutor, location_names),
            }
        )
    return result


def _tutor_location(
    tutor: dict[str, Any], location_names: list[str]
) -> dict[str, Any]:
    if tutor.get("kind") == "special":
        return {"id": None, "name": tutor["location_name"]}
    location_id = tutor["location_id"]
    return {"id": location_id, "name": location_names[location_id]}


def _personal_member_reference(
    member: int, pokedb: PokeDBGeneration
) -> dict[str, Any]:
    if member in PERSONAL_FORM_MEMBERS:
        slug = PERSONAL_FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        national_dex_id = pokedb.pokemon_for_species(reference["species"])["id"]
    elif 1 <= member <= 493:
        reference = pokedb.pokemon_for_id(member)
        slug = reference["name"]
        national_dex_id = member
    else:
        raise DataSourceError(f"Tutor compatibility references internal member {member}")
    return {
        "member": member,
        "national_dex_id": national_dex_id,
        "slug": slug,
        "name": _display_name(slug),
    }


def _enrich_compatible_machines(
    machine_ids: list[int],
    machines: dict[int, dict[str, Any]],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    if not machines:
        return [{"id": value, "name": _machine_name(value)} for value in machine_ids]
    result = []
    for machine_id in machine_ids:
        try:
            machine = machines[machine_id]
        except KeyError as error:
            raise DataSourceError(
                f"Pokémon compatibility references unknown machine ID {machine_id}"
            ) from error
        slug = _move_name(machine["move_id"], pokedb, move_names)
        if slug is None:
            raise DataSourceError(f"Machine {machine['name']} references move ID 0")
        result.append(
            {
                "id": machine_id,
                "name": machine["name"],
                "kind": machine["kind"],
                "number": machine["number"],
                "move": {
                    "id": machine["move_id"],
                    "slug": slug,
                    "name": _display_name(slug),
                },
            }
        )
    return result


def _enrich_evolutions(
    evolution_set: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    item_names: list[str],
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    if evolution_set is None:
        return []
    result = []
    for entry in evolution_set["evolutions"]:
        method_id = entry["method_id"]
        target = pokedb.pokemon_for_id(entry["target_species_id"])
        result.append(
            {
                **entry,
                "method": _named_id(
                    method_id, EVOLUTION_METHOD_NAMES, "evolution method"
                ),
                "parameter_data": _evolution_parameter(
                    entry, pokedb, item_names, move_names
                ),
                "target": {
                    "id": entry["target_species_id"],
                    "slug": target["name"],
                    "name": _display_name(target["name"]),
                },
            }
        )
    return result


def _evolution_parameter(
    entry: dict[str, Any],
    pokedb: PokeDBGeneration,
    item_names: list[str],
    move_names: Mapping[int, str] | None,
) -> dict[str, Any] | None:
    method_id = entry["method_id"]
    parameter = entry["parameter"]
    if method_id in _EVOLUTION_LEVEL_PARAMETERS:
        return {"kind": "level", "value": parameter}
    if method_id in _EVOLUTION_ITEM_PARAMETERS:
        if not 0 < parameter < len(item_names):
            raise DataSourceError(f"Unknown Gen IV item ID: {parameter}")
        name = item_names[parameter]
        return {
            "kind": "item",
            "id": parameter,
            "slug": pokedb.item_slug(name),
            "name": name,
        }
    if method_id in _EVOLUTION_PERSONALITY_PARAMETERS:
        return {"kind": "personality", "value": parameter}
    if method_id == 15:
        return {"kind": "beauty", "value": parameter}
    if method_id == 20:
        return {
            "kind": "move",
            "id": parameter,
            "name": _move_name(parameter, pokedb, move_names),
        }
    if method_id == 21:
        species = pokedb.pokemon_for_id(parameter)
        return {
            "kind": "species",
            "id": parameter,
            "slug": species["name"],
            "name": _display_name(species["name"]),
        }
    if parameter:
        return {"kind": "raw", "value": parameter}
    return None


def _enrich_level_up_moves(
    learnset: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    moves = []
    for entry in learnset["moves"] if learnset is not None else []:
        slug = _move_name(entry["move_id"], pokedb, move_names)
        if slug is None:
            raise DataSourceError("Level-up learnsets cannot reference move ID 0")
        moves.append(
            {
                "level": entry["level"],
                "move": {
                    "id": entry["move_id"],
                    "slug": slug,
                    "name": _display_name(slug),
                },
            }
        )
    return moves


def _enrich_egg_moves(
    egg_move_set: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    moves = []
    for move_id in egg_move_set["move_ids"] if egg_move_set is not None else []:
        slug = _move_name(move_id, pokedb, move_names)
        if slug is None:
            raise DataSourceError("Egg moves cannot reference move ID 0")
        moves.append({"id": move_id, "slug": slug, "name": _display_name(slug)})
    return moves


def _named_id(value: int, names: tuple[str, ...], label: str) -> dict[str, Any]:
    if not 0 <= value < len(names):
        raise DataSourceError(f"Unknown Gen IV {label} ID: {value}")
    return {"id": value, "name": names[value]}


def _reference_name_table(
    dataset: dict[str, Any], field: str, expected_count: int
) -> list[str] | None:
    names = dataset.get(field)
    if names is None:
        return None
    if (
        not isinstance(names, list)
        or len(names) != expected_count
        or any(not isinstance(name, str) or not name for name in names)
    ):
        raise DataSourceError(
            f"Expected exactly {expected_count} ROM-derived {field.replace('_', ' ')}"
        )
    return names


def _resolve_type_names(
    dataset: dict[str, Any], fallback: Mapping[int, str] | None
) -> dict[int, str]:
    result = dict(fallback or {})
    names = _reference_name_table(dataset, "type_names", len(TYPE_NAMES))
    if names is not None:
        result.update(
            (type_id, _name_slug(name)) for type_id, name in enumerate(names)
        )
    return result


def _resolve_move_names(
    dataset: dict[str, Any], fallback: Mapping[int, str] | None
) -> dict[int, str]:
    result = dict(fallback or {})
    names = _reference_name_table(dataset, "move_names", 468)
    if names is not None:
        result.update((move_id, _name_slug(name)) for move_id, name in enumerate(names))
    return result


def _resolve_ability_names(dataset: dict[str, Any]) -> list[str] | None:
    return _reference_name_table(dataset, "ability_names", 124)


def _resolve_item_names(dataset: dict[str, Any]) -> list[str] | None:
    return _reference_name_table(dataset, "item_names", 468)


def _item_reference(
    item_id: int,
    pokedb: PokeDBGeneration,
    item_names: list[str] | None,
) -> dict[str, Any]:
    if item_id == 0:
        return {"id": 0, "slug": None, "name": None}
    if item_names is None:
        slug = pokedb.item_name(item_id)
        return {"id": item_id, "slug": slug, "name": _display_name(slug)}
    if item_id >= len(item_names):
        raise DataSourceError(f"Unknown Gen IV item ID: {item_id}")
    name = item_names[item_id]
    return {"id": item_id, "slug": pokedb.item_slug(name), "name": name}


def _ability_id(
    ability_id: int,
    pokedb: PokeDBGeneration,
    ability_names: list[str] | None,
) -> dict[str, Any]:
    slug = pokedb.ability_name(ability_id)
    if ability_id == 0:
        return {"id": 0, "slug": None, "name": None}
    if ability_names is not None:
        if ability_id >= len(ability_names):
            raise DataSourceError(f"Unknown Gen IV ability ID: {ability_id}")
        name = ability_names[ability_id]
    else:
        name = _display_name(slug)
    return {"id": ability_id, "slug": slug, "name": name}


def _replaced_move(
    move_id: int, slug: str, pokedb: PokeDBGeneration
) -> dict[str, Any] | None:
    canonical_slug = pokedb.move_name(move_id)
    if canonical_slug is None or canonical_slug == slug:
        return None
    return {"slug": canonical_slug, "name": _display_name(canonical_slug)}


def _type_id(
    value: int, type_names: Mapping[int, str] | None
) -> dict[str, Any]:
    if type_names is not None and value in type_names:
        return {"id": value, "name": type_names[value]}
    return _named_id(value, TYPE_NAMES, "type")


def _move_name(
    move_id: int,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> str | None:
    if move_names is not None and move_id in move_names:
        return move_names[move_id]
    return pokedb.move_name(move_id)


def _name_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


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
