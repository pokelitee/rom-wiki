from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.encounter_enrichment import (
    enrich_conditional_encounter_area,
    enrich_seasonal_encounter_area,
    pokemon_display_name,
)
from romwiki.pipeline.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.pipeline.trainer_rewards import calculate_base_prize_money
from romwiki.schema.trainers import (
    unresolved_trainer_variant_support,
    validate_trainer_battle_families,
)
from romwiki.schema.versions import (
    ENCOUNTERS_ENRICHED_SCHEMA_VERSION,
    MOVES_ENRICHED_SCHEMA_VERSION,
    POKEMON_ENRICHED_SCHEMA_VERSION,
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINER_PARTY_SCHEMA_VERSION,
    TRAINERS_ENRICHED_SCHEMA_VERSION,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.json_io import write_json_atomic
from romwiki.util.text import name_slug, normalize_display_name, title_case_slug


def enrich_personal_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    learnset_dataset: dict[str, Any] | None = None,
    evolution_dataset: dict[str, Any] | None = None,
    machine_dataset: dict[str, Any] | None = None,
    tutor_dataset: dict[str, Any] | None = None,
    egg_move_dataset: dict[str, Any] | None = None,
    static_encounter_dataset: dict[str, Any] | None = None,
    *,
    item_dataset: dict[str, Any] | None = None,
    type_names: Mapping[int, str] | None = None,
    move_names: Mapping[int, str] | None = None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
) -> dict[str, Any]:
    engine = get_engine(dataset["engine"]).enrich
    source_records = dataset.get("records")
    expected_count = engine.PERSONAL_RECORD_COUNT
    if not isinstance(source_records, list) or len(source_records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} personal records")
    type_names = _resolve_type_names(engine, dataset, type_names)
    move_names = _resolve_move_names(engine, dataset, move_names)
    ability_names = _resolve_ability_names(engine, dataset)
    item_names = _resolve_item_names(engine, dataset)
    pokemon_names = _resolve_pokemon_names(engine, dataset)

    learnsets = _validate_learnsets(engine, learnset_dataset, dataset["game"])
    evolutions = _validate_evolutions(engine, evolution_dataset, dataset["game"])
    evolution_item_names = _validate_evolution_item_names(evolution_dataset)
    evolution_item_slugs = _validate_evolution_item_slugs(
        item_dataset, dataset["game"], pokedb
    )
    machines = _validate_machines(engine, machine_dataset, dataset["game"])
    tutors, tutor_ids_by_member, tutor_locations = _validate_tutors(
        tutor_dataset, dataset["game"]
    )
    egg_moves = _validate_egg_moves(engine, egg_move_dataset, dataset["game"])
    static_encounters_by_species = _validate_static_encounters(
        static_encounter_dataset, dataset["game"]
    )
    records = []
    for expected_member, source in enumerate(source_records):
        if source.get("species_id") != expected_member:
            raise DataSourceError("Personal records must be ordered by member ID")
        records.append(
            _enrich_record(
                engine,
                source,
                pokedb,
                learnsets[expected_member],
                evolutions[expected_member],
                evolution_item_names,
                evolution_item_slugs,
                machines,
                tutors,
                tutor_ids_by_member.get(expected_member, []),
                tutor_locations,
                egg_moves.get(expected_member),
                static_encounters_by_species.get(expected_member, []),
                type_names,
                move_names,
                ability_names,
                item_names,
                pokemon_names,
                sprite_version,
                reference_version,
            )
        )
    _attach_battle_forms(engine, records)
    enriched = {
        "schema_version": POKEMON_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": dataset["engine"],
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
        enriched.setdefault("supplemental_sources", {})["machines"] = machine_dataset[
            "source"
        ]
    if tutor_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["move_tutors"] = tutor_dataset[
            "source"
        ]
    if egg_move_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["egg_moves"] = egg_move_dataset[
            "source"
        ]
    if static_encounter_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["static_encounters"] = (
            static_encounter_dataset["source"]
        )
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    if "ability_names" in dataset:
        enriched["ability_names"] = dataset["ability_names"]
    return enriched


def enrich_encounter_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    *,
    sprite_version: str | None = None,
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Encounter dataset records must be a list")
    engine = get_engine(dataset["engine"]).enrich
    pokemon_names = _resolve_pokemon_names(engine, dataset)
    encounter_format = get_engine(dataset["engine"]).formats.encounters
    enrich_area = (
        enrich_seasonal_encounter_area
        if encounter_format == "seasonal"
        else enrich_conditional_encounter_area
    )

    records = []
    for expected_area, source in enumerate(source_records):
        if source.get("area_id") != expected_area:
            raise DataSourceError("Encounter records must be ordered by area ID")
        records.append(
            enrich_area(engine, source, pokedb, sprite_version, pokemon_names)
        )
    return {
        "schema_version": ENCOUNTERS_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": dataset["engine"],
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
    pokemon_dataset: dict[str, Any] | None = None,
    move_dataset: dict[str, Any] | None = None,
    move_names: Mapping[int, str] | None = None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
) -> dict[str, Any]:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Trainer dataset records must be a list")
    engine = dataset.get("engine")
    if not isinstance(engine, str):
        raise DataSourceError("Trainer dataset must declare its source engine")
    engine_tables = get_engine(engine).enrich
    families = dataset.get("battle_families", [])
    support = dataset.get(
        "trainer_variant_support", unresolved_trainer_variant_support()
    )
    validate_trainer_battle_families(
        families,
        support,
        (record.get("trainer_id") for record in source_records),
    )
    pokemon_records = _trainer_pokemon_index(dataset, pokemon_dataset)
    move_records = _trainer_move_index(dataset, move_dataset)
    move_names = _resolve_move_names(engine_tables, dataset, move_names)
    item_names = _resolve_item_names(engine_tables, dataset)
    pokemon_names = _resolve_pokemon_names(engine_tables, dataset)
    records = []
    # Trainer IDs are expected to be consecutive, but not necessarily
    # starting at 0: Generation V's trainer archive has an unused member 0
    # with a different shape, so its real trainer IDs start at 1.
    base_trainer_id = source_records[0].get("trainer_id") if source_records else 0
    for offset, source in enumerate(source_records):
        if source.get("trainer_id") != base_trainer_id + offset:
            raise DataSourceError("Trainer records must be ordered by trainer ID")
        records.append(
            _enrich_trainer(
                source,
                pokedb,
                move_names,
                item_names,
                sprite_version,
                reference_version,
                engine=engine,
                pokemon_records=pokemon_records,
                move_records=move_records,
                pokemon_names=pokemon_names,
            )
        )
    enriched = {
        "schema_version": TRAINERS_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": engine,
        "dataset": "trainers",
        "party_schema_version": TRAINER_PARTY_SCHEMA_VERSION,
        "battle_family_schema_version": TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
        "trainer_variant_support": support,
        "battle_families": families,
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
    reference_version: str | None = None,
) -> dict[str, Any]:
    engine = get_engine(dataset["engine"]).enrich
    source_records = dataset.get("records")
    expected_count = engine.MOVE_RECORD_COUNT
    if not isinstance(source_records, list) or len(source_records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} move records")
    rom_move_names = _reference_name_table(
        dataset, "move_names", engine.MOVE_NAME_COUNT
    )
    type_names = _resolve_type_names(engine, dataset, type_names)
    move_names = _resolve_move_names(engine, dataset, move_names)
    pokemon_names = _resolve_pokemon_names(engine, dataset)

    machines = _validate_machines(engine, machine_dataset, dataset["game"])
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
                    _personal_member_reference(engine, member, pokedb, pokemon_names)
                    for member in members_by_tutor[tutor_id]
                ],
            }
        )
    egg_moves = _validate_egg_moves(engine, egg_move_dataset, dataset["game"])
    egg_move_pokemon: dict[int, list[dict[str, Any]]] = {}
    for species_id, egg_move_set in egg_moves.items():
        pokemon = _personal_member_reference(engine, species_id, pokedb, pokemon_names)
        for move_id in set(egg_move_set["move_ids"]):
            egg_move_pokemon.setdefault(move_id, []).append(pokemon)
    records = []
    for expected_id, source in enumerate(source_records):
        if source.get("move_id") != expected_id:
            raise DataSourceError("Move records must be ordered by member ID")
        public = 1 <= expected_id <= engine.MAX_MOVE_ID
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
                    else title_case_slug(slug)
                ),
                "replaces": (
                    _replaced_move(expected_id, slug, pokedb) if public else None
                ),
                "reference": (
                    pokedb.move_reference(expected_id, reference_version)
                    if public
                    else None
                ),
                "public": public,
                "damage_class": _named_id(
                    source["damage_class_id"],
                    engine.DAMAGE_CLASS_NAMES,
                    "move class",
                ),
                "type": _type_id(engine, source["type_id"], type_names),
                "machines": machines_by_move.get(expected_id, []),
                "tutors": tutors_by_move.get(expected_id, []),
                "egg_move_pokemon": egg_move_pokemon.get(expected_id, []),
            }
        )
    enriched = {
        "schema_version": MOVES_ENRICHED_SCHEMA_VERSION,
        "game": dataset["game"],
        "engine": dataset["engine"],
        "dataset": "moves",
        "record_count": len(records),
        "public_record_count": sum(record["public"] for record in records),
        "source": dataset["source"],
        "records": records,
    }
    if machine_dataset is not None:
        enriched["supplemental_sources"] = {"machines": machine_dataset["source"]}
    if tutor_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["move_tutors"] = tutor_dataset[
            "source"
        ]
    if egg_move_dataset is not None:
        enriched.setdefault("supplemental_sources", {})["egg_moves"] = egg_move_dataset[
            "source"
        ]
    if dataset.get("name_sources"):
        enriched["name_sources"] = dataset["name_sources"]
    return enriched


def write_enriched_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)


def _enrich_trainer(
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    item_names: list[str] | None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
    *,
    engine: str,
    pokemon_records: Mapping[int | str, dict[str, Any]] | None = None,
    move_records: Mapping[int, dict[str, Any]] | None = None,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any]:
    engine_tables = get_engine(engine).enrich
    party = []
    for raw_member in source["party"]:
        pokemon = normalize_trainer_party_member(
            engine,
            raw_member,
            has_custom_moves=source["has_custom_moves"],
        )
        species_id = pokemon["species_id"]
        form_id = pokemon["form_id"]
        game_record = None
        if form_id:
            slug = engine_tables.TRAINER_FORM_SLUGS.get((species_id, form_id))
            cosmetic_form = engine_tables.TRAINER_COSMETIC_FORM_LABELS.get(
                (species_id, form_id)
            )
            if slug is not None:
                if pokemon_records is not None:
                    game_record = pokemon_records.get(slug)
                reference = None if game_record else pokedb.pokemon_for_name(slug)
            elif cosmetic_form is not None:
                reference = pokedb.pokemon_for_id(species_id)
            else:
                raise DataSourceError(
                    f"Unknown trainer form {form_id} for species {species_id}"
                )
        else:
            cosmetic_form = None
            if pokemon_records is not None:
                game_record = pokemon_records.get(species_id)
            reference = None if game_record else pokedb.pokemon_for_id(species_id)
        pokemon = derive_trainer_party_attributes(
            engine,
            pokemon,
            trainer_id=source["trainer_id"],
            class_id=source["class_id"],
            class_gender=source.get("class_gender"),
            gender_ratio=(game_record.get("gender_ratio") if game_record else None),
            base_stats=(game_record.get("base_stats") if game_record else None),
        )
        if game_record:
            pokemon_slug = (
                game_record.get("base_species")
                if not game_record.get("public", True)
                else game_record["slug"]
            ) or game_record["slug"]
        else:
            pokemon_slug = reference["name"]
        if game_record:
            pokemon_name = game_record["name"]
        elif form_id and slug:
            pokemon_name = title_case_slug(slug)
        else:
            pokemon_name = pokemon_display_name(
                species_id, reference["name"], pokemon_names
            )
        pokemon_sprite = (
            game_record.get("sprite")
            if game_record
            else pokedb.pokemon_sprite(reference, sprite_version)
        )
        ability = _trainer_ability(pokemon.get("ability"), game_record)
        held_item = (
            _item_reference(pokemon["held_item_id"], pokedb, item_names)
            if pokemon["held_item_id"] is not None
            else None
        )
        canonical_member = {
            key: value
            for key, value in pokemon.items()
            if key not in {"held_item_id", "move_ids"}
        }
        party.append(
            {
                **canonical_member,
                "pokemon": {
                    "id": species_id,
                    "slug": pokemon_slug,
                    "name": pokemon_name
                    + (f" ({cosmetic_form})" if cosmetic_form else ""),
                    **(
                        {"page_slug": None}
                        if game_record
                        and not game_record.get("public", True)
                        and not game_record.get("base_species")
                        else {}
                    ),
                    "sprite": pokemon_sprite,
                    "types": game_record.get("types", []) if game_record else [],
                },
                "ability": ability,
                "held_item": (
                    _with_item_sprite(held_item, pokedb, reference_version)
                    if held_item is not None
                    else None
                ),
                "moves": [
                    {
                        "id": move_id,
                        "name": _move_name(move_id, pokedb, move_names),
                        **(
                            {
                                "type": move_records[move_id]["type"],
                                "damage_class": move_records[move_id]["damage_class"],
                            }
                            if move_records is not None and move_id in move_records
                            else {}
                        ),
                    }
                    for move_id in pokemon["move_ids"]
                    if move_id
                ],
            }
        )
    return {
        **source,
        "party": party,
        "base_prize_money": calculate_base_prize_money(source, engine=engine),
        "victory_item": (
            _with_item_sprite(
                _item_reference(source["victory_item_id"], pokedb, item_names),
                pokedb,
                reference_version,
            )
            if source.get("victory_item_id")
            else None
        ),
        # The ROM's "reward_item_ids" slots are the trainer's own AI battle
        # items (e.g. a carried Full Restore the AI uses on itself mid-fight)
        # — not something given to the player. See pokeemerald/pokeplatinum
        # decompilations for the equivalent trainer-struct field.
        "ai_battle_items": [
            _with_item_sprite(
                _item_reference(item_id, pokedb, item_names), pokedb, reference_version
            )
            for item_id in source["reward_item_ids"]
            if item_id
        ],
    }


def _trainer_pokemon_index(
    trainer_dataset: Mapping[str, Any],
    pokemon_dataset: dict[str, Any] | None,
) -> dict[int | str, dict[str, Any]] | None:
    if pokemon_dataset is None:
        return None
    if pokemon_dataset.get("game") != trainer_dataset.get("game"):
        raise DataSourceError("Trainer and Pokémon datasets must be for the same game")
    records = pokemon_dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Pokémon dataset records must be a list")
    index: dict[int | str, dict[str, Any]] = {}
    for record in records:
        member = record.get("member")
        slug = record.get("slug")
        if member is not None:
            index[member] = record
        if isinstance(slug, str):
            index[slug] = record
    return index


def _trainer_move_index(
    trainer_dataset: Mapping[str, Any],
    move_dataset: dict[str, Any] | None,
) -> dict[int, dict[str, Any]] | None:
    if move_dataset is None:
        return None
    if move_dataset.get("game") != trainer_dataset.get("game"):
        raise DataSourceError("Trainer and move datasets must be for the same game")
    records = move_dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Move dataset records must be a list")
    return {
        record["move_id"]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("move_id"), int)
    }


def _trainer_ability(
    value: dict[str, Any] | None,
    pokemon_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if value is None or pokemon_record is None:
        return None
    slot = value.get("slot")
    abilities = pokemon_record.get("abilities")
    if not isinstance(slot, int) or not isinstance(abilities, list):
        raise DataSourceError("Normalized trainer ability is missing its slot")
    if not pokemon_record.get("public", True) and not abilities:
        return None
    if not 1 <= slot <= len(abilities):
        raise DataSourceError(f"Trainer ability slot {slot} is out of range")
    ability = abilities[slot - 1]
    if not isinstance(ability, dict) or not ability.get("name"):
        return None
    return {**ability, "slot": slot, "source": value["source"]}


def _with_item_sprite(
    item: dict[str, Any], pokedb: PokeDBGeneration, reference_version: str | None
) -> dict[str, Any]:
    return {**item, "sprite_url": _item_sprite_url(item, pokedb, reference_version)}


def _item_sprite_url(
    item: dict[str, Any], pokedb: PokeDBGeneration, reference_version: str | None
) -> str | None:
    name = item.get("name")
    if not name:
        return None
    reference = pokedb.item_reference(
        pokedb.item_reference_slug(name), reference_version
    )
    return reference.get("sprite_url") if reference else None


def _attach_battle_forms(engine: Any, records: list[dict[str, Any]]) -> None:
    """Attach each battle-only transformation record's stats/types to its
    base species' record as `battle_forms`, e.g. Castform's page gains its
    real Sunny/Rainy/Snowy stat blocks even though those transformations
    have no PokéDB reference page or public record of their own.
    """
    transformation_members = getattr(engine, "TRANSFORMATION_MEMBERS", {})
    if not transformation_members:
        return
    by_base_slug: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        transformation = transformation_members.get(record["member"])
        if transformation is None:
            continue
        by_base_slug.setdefault(transformation["base_slug"], []).append(
            {
                "label": transformation["label"],
                "base_stats": record["base_stats"],
                "types": record["types"],
            }
        )
    if not by_base_slug:
        return
    for record in records:
        forms = by_base_slug.get(record["slug"])
        if forms:
            record["battle_forms"] = forms


def _enrich_record(
    engine: Any,
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    learnset: dict[str, Any] | None,
    evolution_set: dict[str, Any] | None,
    evolution_item_names: list[str],
    evolution_item_slugs: Mapping[int, str | None],
    machines: dict[int, dict[str, Any]],
    tutors: dict[int, dict[str, Any]],
    tutor_ids: list[int],
    tutor_locations: list[str],
    egg_move_set: dict[str, Any] | None,
    static_encounters: list[dict[str, Any]],
    type_names: Mapping[int, str] | None,
    move_names: Mapping[int, str] | None,
    ability_names: list[str] | None,
    item_names: list[str] | None,
    pokemon_names: list[str] | None,
    sprite_version: str | None,
    reference_version: str | None,
) -> dict[str, Any]:
    member = source["species_id"]
    transformation_members = getattr(engine, "TRANSFORMATION_MEMBERS", {})
    is_internal = member in engine.INTERNAL_MEMBERS
    if is_internal:
        slug = engine.INTERNAL_MEMBERS[member]
        identity = {"national_dex_id": None, "base_species": None, "form": None}
        sprite = None
        sprites = []
        portrait = None
        cry = None
        reference_data = None
        public = False
    elif member in engine.FORM_MEMBERS:
        slug = engine.FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        base_species = reference["species"]
        identity = {
            "national_dex_id": pokedb.pokemon_for_species(base_species)["id"],
            "base_species": base_species,
            "form": slug.removeprefix(f"{base_species}-"),
        }
        sprite = pokedb.pokemon_sprite(reference, sprite_version)
        sprites = pokedb.pokemon_sprites(reference, sprite_version)
        portrait = pokedb.pokemon_portrait(reference) or sprite
        cry = pokedb.pokemon_cry(reference)
        reference_data = pokedb.pokemon_reference(reference, reference_version)
        public = True
    elif member in transformation_members:
        transformation = transformation_members[member]
        base_slug = transformation["base_slug"]
        slug = transformation.get(
            "slug", f"{base_slug}-{name_slug(transformation['label'])}"
        )
        identity = {
            "national_dex_id": None,
            "base_species": base_slug,
            "form": None,
        }
        sprite = None
        sprites = []
        portrait = None
        cry = None
        reference_data = None
        public = False
    else:
        reference = pokedb.pokemon_for_id(member)
        slug = reference["name"]
        identity = {
            "national_dex_id": member,
            "base_species": reference["species"],
            "form": None,
        }
        sprite = pokedb.pokemon_sprite(reference, sprite_version)
        sprites = pokedb.pokemon_sprites(reference, sprite_version)
        portrait = pokedb.pokemon_portrait(reference) or sprite
        cry = pokedb.pokemon_cry(reference)
        reference_data = pokedb.pokemon_reference(reference, reference_version)
        public = True

    # Form and internal members keep their slug-derived labels; regular
    # species prefer the ROM's own name table ("Mr. Mime", "Farfetch'd").
    if (
        member in engine.FORM_MEMBERS
        or member in engine.INTERNAL_MEMBERS
        or member in transformation_members
    ):
        display_name = title_case_slug(slug)
    else:
        display_name = pokemon_display_name(member, slug, pokemon_names)

    return {
        "member": member,
        "slug": slug,
        "name": display_name,
        "public": public,
        **identity,
        "sprite": sprite,
        "portrait": portrait,
        "cry": cry,
        "sprites": sprites,
        "reference": reference_data,
        "base_stats": source["base_stats"],
        "types": (
            []
            if is_internal
            else [_type_id(engine, value, type_names) for value in source["type_ids"]]
        ),
        "catch_rate": source["catch_rate"],
        "base_experience": source["base_experience"],
        "ev_yields": source["ev_yields"],
        "held_items": (
            []
            if is_internal
            else [
                {
                    "rarity": rarity,
                    **_item_reference(
                        value,
                        pokedb,
                        item_names,
                        page_slugs=evolution_item_slugs,
                    ),
                }
                for rarity, value in (
                    ("common", source["wild_held_items"]["common"]),
                    ("rare", source["wild_held_items"]["rare"]),
                    *(
                        [("dark_grass", source["wild_held_items"]["dark_grass"])]
                        if source["wild_held_items"].get("dark_grass") is not None
                        else []
                    ),
                )
            ]
        ),
        "gender_ratio": source["gender_ratio"],
        "hatch_cycles": source["hatch_cycles"],
        "base_friendship": source["base_friendship"],
        "growth_rate": (
            None
            if is_internal
            else _named_id(
                source["growth_rate_id"], engine.GROWTH_RATE_NAMES, "growth rate"
            )
        ),
        "egg_groups": (
            []
            if is_internal
            else [
                _named_id(value, engine.EGG_GROUP_NAMES, "egg group")
                for value in source["egg_group_ids"]
            ]
        ),
        "abilities": (
            []
            if is_internal
            else [
                {**_ability_id(value, pokedb, ability_names), "is_hidden": index == 2}
                for index, value in enumerate(source["ability_ids"])
            ]
        ),
        "safari_flee_rate": source["safari_flee_rate"],
        "body_color": (
            None
            if is_internal
            else _named_id(source["body_color_id"], engine.COLOR_NAMES, "body color")
        ),
        "flip_sprite": source["flip_sprite"],
        "machines": (
            []
            if is_internal
            else _enrich_compatible_machines(
                engine, source["machine_ids"], machines, pokedb, move_names
            )
        ),
        "tutor_moves": (
            []
            if is_internal
            else _enrich_compatible_tutors(
                tutor_ids, tutors, tutor_locations, pokedb, move_names
            )
        ),
        "level_up_moves": (
            [] if is_internal else _enrich_level_up_moves(learnset, pokedb, move_names)
        ),
        "learnset_provenance": (
            None if is_internal or learnset is None else learnset["provenance"]
        ),
        "egg_moves": (
            [] if is_internal else _enrich_egg_moves(egg_move_set, pokedb, move_names)
        ),
        "egg_move_provenance": (
            None if is_internal else _egg_move_provenance(egg_move_set)
        ),
        "static_encounters": [
            {"level": entry["level"], "is_egg": entry["is_egg"]}
            for entry in (() if is_internal else static_encounters)
        ],
        "evolutions": (
            []
            if is_internal
            else _enrich_evolutions(
                engine,
                evolution_set,
                pokedb,
                evolution_item_names,
                evolution_item_slugs,
                move_names,
                pokemon_names,
            )
        ),
        "evolution_provenance": (
            evolution_set["provenance"]
            if not is_internal and evolution_set is not None
            else None
        ),
        "provenance": source["provenance"],
    }


def _validate_learnsets(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> list[dict[str, Any] | None]:
    expected_count = engine.PERSONAL_RECORD_COUNT
    if dataset is None:
        return [None] * expected_count
    if dataset.get("game") != game:
        raise DataSourceError(
            "Personal and learnset datasets must be for the same game"
        )
    records = dataset.get("records")
    if not isinstance(records, list) or len(records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} level-up learnsets")
    for expected_member, record in enumerate(records):
        if record.get("species_id") != expected_member:
            raise DataSourceError("Learnsets must be ordered by member ID")
    return records


def _validate_evolutions(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> list[dict[str, Any] | None]:
    expected_count = engine.PERSONAL_RECORD_COUNT
    if dataset is None:
        return [None] * expected_count
    if dataset.get("game") != game:
        raise DataSourceError(
            "Personal and evolution datasets must be for the same game"
        )
    records = dataset.get("records")
    if not isinstance(records, list) or len(records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} evolution records")
    for expected_member, record in enumerate(records):
        if record.get("species_id") != expected_member:
            raise DataSourceError("Evolution records must be ordered by member ID")
    return records


def _validate_egg_moves(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Egg move dataset must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Egg move records must be a list")
    # Two provenance shapes coexist here: a sparse ARM9-overlay table (Gen IV,
    # one entry per species that actually has egg moves, ordered by
    # table_index) and a dense per-species NARC archive (Gen V, one member per
    # species -- including ones with zero egg moves -- carrying a shared
    # RecordProvenance instead).
    if records and "provenance" in records[0]:
        return _validate_dense_egg_moves(engine, records)
    return _validate_sparse_egg_moves(engine, records)


def _validate_dense_egg_moves(
    engine: Any, records: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    result = {}
    for expected_member, record in enumerate(records):
        species_id = record.get("species_id")
        move_ids = record.get("move_ids")
        if species_id != expected_member:
            raise DataSourceError("Egg move records must be ordered by member ID")
        if not isinstance(move_ids, (list, tuple)) or any(
            not isinstance(move_id, int) or not 1 <= move_id <= engine.MAX_MOVE_ID
            for move_id in move_ids
        ):
            raise DataSourceError("Egg move record contains invalid move IDs")
        # Unlike the sparse (Gen IV) table, this generation's real ROM data
        # does contain a handful of duplicate move IDs within one species'
        # record (e.g. Swinub's own table lists Mud Shot twice) -- rejecting
        # them would mean guessing at "corrected" data instead of decoding
        # what's actually there; _enrich_egg_moves dedupes for display.
        if move_ids:
            result[species_id] = record
    return result


def _validate_sparse_egg_moves(
    engine: Any, records: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    result = {}
    previous_species = 0
    for expected_index, record in enumerate(records):
        species_id = record.get("species_id")
        move_ids = record.get("move_ids")
        if (
            not isinstance(species_id, int)
            or not previous_species < species_id <= engine.BASE_SPECIES_COUNT
            or record.get("table_index") != expected_index
        ):
            raise DataSourceError("Egg move records must be ordered by species ID")
        if (
            not isinstance(move_ids, (list, tuple))
            or not move_ids
            or any(
                not isinstance(move_id, int) or not 1 <= move_id <= engine.MAX_MOVE_ID
                for move_id in move_ids
            )
        ):
            raise DataSourceError("Egg move record contains invalid move IDs")
        if len(move_ids) != len(set(move_ids)) and not getattr(
            engine, "ALLOW_DUPLICATE_EGG_MOVES", False
        ):
            raise DataSourceError("Egg move record contains duplicate move IDs")
        result[species_id] = record
        previous_species = species_id
    return result


def _validate_static_encounters(
    dataset: dict[str, Any] | None, game: str
) -> dict[int, list[dict[str, Any]]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Static encounter dataset must be for the same game")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Static encounter records must be a list")
    by_species: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        species_id = record.get("species_id")
        if not isinstance(species_id, int):
            raise DataSourceError("Static encounter record is missing a species ID")
        by_species.setdefault(species_id, []).append(record)
    return by_species


def _validate_evolution_item_names(dataset: dict[str, Any] | None) -> list[str]:
    if dataset is None:
        return []
    item_names = dataset.get("item_names")
    if not isinstance(item_names, list) or not all(
        isinstance(name, str) for name in item_names
    ):
        raise DataSourceError("Evolution dataset must include ROM item names")
    return item_names


def _validate_evolution_item_slugs(
    dataset: dict[str, Any] | None,
    game: str,
    pokedb: PokeDBGeneration,
) -> dict[int, str | None]:
    if dataset is None:
        return {}
    if dataset.get("game") != game or not isinstance(dataset.get("records"), list):
        raise DataSourceError("Item dataset must be for the same game")
    public_records = [record for record in dataset["records"] if record.get("public")]
    counts: dict[str, int] = {}
    for record in public_records:
        slug = pokedb.item_slug(record["name"])
        counts[slug] = counts.get(slug, 0) + 1
    return {
        record["item_id"]: (f"{slug}-{record['item_id']}" if counts[slug] > 1 else slug)
        for record in public_records
        for slug in (pokedb.item_slug(record["name"]),)
    }


def _validate_machines(
    engine: Any, dataset: dict[str, Any] | None, game: str
) -> dict[int, dict[str, Any]]:
    if dataset is None:
        return {}
    if dataset.get("game") != game:
        raise DataSourceError("Machine dataset must be for the same game")
    records = dataset.get("records")
    expected_count = engine.MACHINE_COUNT
    if not isinstance(records, list) or len(records) != expected_count:
        raise DataSourceError(f"Expected exactly {expected_count} machine records")
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
                raise DataSourceError(
                    "Tutor compatibility contains duplicate tutor IDs"
                )
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
                    "name": title_case_slug(slug),
                },
                "location": _tutor_location(tutor, location_names),
            }
        )
    return result


def _tutor_location(tutor: dict[str, Any], location_names: list[str]) -> dict[str, Any]:
    if tutor.get("kind") == "special":
        return {"id": None, "name": tutor["location_name"]}
    location_id = tutor["location_id"]
    return {"id": location_id, "name": location_names[location_id]}


def _personal_member_reference(
    engine: Any,
    member: int,
    pokedb: PokeDBGeneration,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any]:
    if member in engine.FORM_MEMBERS:
        slug = engine.FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        national_dex_id = pokedb.pokemon_for_species(reference["species"])["id"]
        name = title_case_slug(slug)
    elif 1 <= member <= engine.BASE_SPECIES_COUNT:
        reference = pokedb.pokemon_for_id(member)
        slug = reference["name"]
        national_dex_id = member
        name = pokemon_display_name(member, slug, pokemon_names)
    else:
        raise DataSourceError(
            f"Tutor compatibility references internal member {member}"
        )
    return {
        "member": member,
        "national_dex_id": national_dex_id,
        "slug": slug,
        "name": name,
    }


def _enrich_compatible_machines(
    engine: Any,
    machine_ids: list[int],
    machines: dict[int, dict[str, Any]],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    if not machines:
        return [
            {"id": value, "name": engine.machine_name(value)} for value in machine_ids
        ]
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
                "item_id": machine.get("item_id"),
                "move": {
                    "id": machine["move_id"],
                    "slug": slug,
                    "name": title_case_slug(slug),
                },
            }
        )
    return result


def _enrich_evolutions(
    engine: Any,
    evolution_set: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    item_names: list[str],
    item_slugs: Mapping[int, str | None],
    move_names: Mapping[int, str] | None,
    pokemon_names: list[str] | None = None,
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
                    method_id, engine.EVOLUTION_METHOD_NAMES, "evolution method"
                ),
                "parameter_data": _evolution_parameter(
                    engine,
                    entry,
                    pokedb,
                    item_names,
                    item_slugs,
                    move_names,
                    pokemon_names,
                ),
                "target": {
                    "id": entry["target_species_id"],
                    "slug": target["name"],
                    "name": pokemon_display_name(
                        entry["target_species_id"], target["name"], pokemon_names
                    ),
                },
            }
        )
    return result


def _evolution_parameter(
    engine: Any,
    entry: dict[str, Any],
    pokedb: PokeDBGeneration,
    item_names: list[str],
    item_slugs: Mapping[int, str | None],
    move_names: Mapping[int, str] | None,
    pokemon_names: list[str] | None = None,
) -> dict[str, Any] | None:
    method_id = entry["method_id"]
    parameter = entry["parameter"]
    kind = engine.EVOLUTION_PARAMETER_KINDS.get(method_id)
    if kind == "item":
        if not 0 < parameter < len(item_names):
            raise DataSourceError(f"Unknown item ID: {parameter}")
        name = item_names[parameter]
        return {
            "kind": "item",
            "id": parameter,
            "slug": item_slugs.get(parameter, pokedb.item_slug(name)),
            "name": name,
        }
    if kind == "move":
        return {
            "kind": "move",
            "id": parameter,
            "name": _move_name(parameter, pokedb, move_names),
        }
    if kind == "pokemon":
        species = pokedb.pokemon_for_id(parameter)
        return {
            "kind": "pokemon",
            "id": parameter,
            "slug": species["name"],
            "name": pokemon_display_name(parameter, species["name"], pokemon_names),
        }
    if kind is not None:
        return {"kind": kind, "value": parameter}
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
                    "name": title_case_slug(slug),
                },
            }
        )
    return moves


def _egg_move_provenance(
    egg_move_set: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if egg_move_set is None:
        return None
    if "provenance" in egg_move_set:
        return dict(egg_move_set["provenance"])
    return {
        "overlay_offset": egg_move_set["overlay_offset"],
        "table_index": egg_move_set["table_index"],
    }


def _enrich_egg_moves(
    egg_move_set: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> list[dict[str, Any]]:
    moves = []
    seen: set[int] = set()
    for move_id in egg_move_set["move_ids"] if egg_move_set is not None else []:
        if move_id in seen:
            continue
        seen.add(move_id)
        slug = _move_name(move_id, pokedb, move_names)
        if slug is None:
            raise DataSourceError("Egg moves cannot reference move ID 0")
        moves.append({"id": move_id, "slug": slug, "name": title_case_slug(slug)})
    return moves


def _named_id(value: int, names: tuple[str, ...], label: str) -> dict[str, Any]:
    if not 0 <= value < len(names):
        raise DataSourceError(f"Unknown {label} ID: {value}")
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
    engine: Any, dataset: dict[str, Any], fallback: Mapping[int, str] | None
) -> dict[int, str]:
    result = dict(fallback or {})
    names = _reference_name_table(dataset, "type_names", engine.TYPE_NAME_COUNT)
    if names is not None:
        result.update((type_id, name_slug(name)) for type_id, name in enumerate(names))
    return result


def _resolve_move_names(
    engine: Any, dataset: dict[str, Any], fallback: Mapping[int, str] | None
) -> dict[int, str]:
    result = dict(fallback or {})
    names = _reference_name_table(dataset, "move_names", engine.MOVE_NAME_COUNT)
    if names is not None:
        result.update((move_id, name_slug(name)) for move_id, name in enumerate(names))
    return result


def _resolve_ability_names(engine: Any, dataset: dict[str, Any]) -> list[str] | None:
    return _reference_name_table(dataset, "ability_names", engine.ABILITY_NAME_COUNT)


def _resolve_pokemon_names(engine: Any, dataset: dict[str, Any]) -> list[str] | None:
    names = _reference_name_table(dataset, "pokemon_names", engine.POKEMON_NAME_COUNT)
    if names is None:
        return None
    return [normalize_display_name(name) for name in names]


def _resolve_item_names(engine: Any, dataset: dict[str, Any]) -> list[str] | None:
    return _reference_name_table(dataset, "item_names", engine.ITEM_NAME_COUNT)


def _item_reference(
    item_id: int,
    pokedb: PokeDBGeneration,
    item_names: list[str] | None,
    *,
    page_slugs: Mapping[int, str | None] | None = None,
) -> dict[str, Any]:
    if item_id == 0:
        return {"id": 0, "slug": None, "name": None}
    if item_names is None:
        reference_slug = pokedb.item_name(item_id)
        page_slug = (
            page_slugs.get(item_id) if page_slugs is not None else reference_slug
        )
        return {
            "id": item_id,
            "slug": page_slug,
            "name": title_case_slug(reference_slug),
        }
    if item_id >= len(item_names):
        raise DataSourceError(f"Unknown item ID: {item_id}")
    name = item_names[item_id]
    slug = pokedb.item_slug(name)
    if page_slugs is not None:
        slug = page_slugs.get(item_id)
    return {"id": item_id, "slug": slug, "name": name}


def _ability_id(
    ability_id: int,
    pokedb: PokeDBGeneration,
    ability_names: list[str] | None,
) -> dict[str, Any]:
    if ability_id == 0:
        return {"id": 0, "slug": None, "name": None}
    slug = pokedb.ability_name(ability_id)
    if ability_names is not None:
        if ability_id >= len(ability_names):
            raise DataSourceError(f"Unknown ability ID: {ability_id}")
        name = ability_names[ability_id]
    else:
        name = title_case_slug(slug)
    return {"id": ability_id, "slug": slug, "name": name}


def _replaced_move(
    move_id: int, slug: str, pokedb: PokeDBGeneration
) -> dict[str, Any] | None:
    canonical_slug = pokedb.move_name(move_id)
    if canonical_slug is None or canonical_slug == slug:
        return None
    return {"slug": canonical_slug, "name": title_case_slug(canonical_slug)}


def _type_id(
    engine: Any, value: int, type_names: Mapping[int, str] | None
) -> dict[str, Any]:
    if type_names is not None and value in type_names:
        return {"id": value, "name": type_names[value]}
    return _named_id(value, engine.TYPE_NAMES, "type")


def _move_name(
    move_id: int,
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
) -> str | None:
    if move_names is not None and move_id in move_names:
        return move_names[move_id]
    return pokedb.move_name(move_id)
