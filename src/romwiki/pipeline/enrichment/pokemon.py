from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from romwiki.engines.concerns import EnrichmentTables
from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment.common import (
    ability_reference_id,
    named_id,
    national_dex_id_for_member,
    pokemon_display_name,
    tutor_location,
    type_id,
    validate_egg_moves,
    validate_machines,
    validate_tutors,
)
from romwiki.pipeline.enrichment.names import (
    resolve_ability_names,
    resolve_item_names,
    resolve_move_names,
    resolve_pokemon_names,
    resolve_type_names,
)
from romwiki.pipeline.enrichment.references import (
    item_reference,
    move_name,
    move_reference,
    with_rom_description,
)
from romwiki.schema.enriched import (
    EntityLink,
    EvolutionParameter,
    LevelUpMove,
    MachineCompatibility,
    MoveLink,
    PokemonBattleForm,
    PokemonDataset,
    PokemonEnrichedRecord,
    PokemonEvolution,
    PokemonEvolutionFields,
    PokemonHeldItem,
    PokemonIdentityFields,
    PokemonLearnsetFields,
    PokemonMoveCompatibility,
    PokemonSpeciesTraits,
    TutorMoveCompatibility,
)
from romwiki.schema.versions import POKEMON_ENRICHED_SCHEMA_VERSION
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import name_slug, title_case_slug


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
    move_dataset: dict[str, Any] | None = None,
    type_names: Mapping[int, str] | None = None,
    move_names: Mapping[int, str] | None = None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
) -> PokemonDataset:
    engine = get_engine(dataset["engine"]).enrich
    source_records = dataset.get("records")
    if not isinstance(source_records, list) or not source_records:
        raise DataSourceError("Expected personal records")
    type_names = resolve_type_names(dataset, type_names)
    move_names = resolve_move_names(dataset, move_names)
    # A move whose exact ROM-decoded name diverges stylistically from
    # PokeDB's canonical one (e.g. "SOLARBEAM" vs "Solar Beam") gets its own
    # `moves` page under the ROM-derived slug (see `moves.py`'s own
    # `enrich_move_dataset`) -- resolving that same table here (independent
    # of `move_names` above, which only carries this profile's static
    # overrides) lets `move_reference`'s `page_slugs` correct cross-
    # reference links to the page that actually exists, the same
    # `page_slugs`-override pattern `evolution_item_slugs` already uses for
    # items.
    move_page_slugs = (
        resolve_move_names(move_dataset, None) if move_dataset is not None else {}
    )
    ability_names = resolve_ability_names(dataset)
    item_names = resolve_item_names(dataset)
    pokemon_names = resolve_pokemon_names(dataset)
    pokemon_descriptions = dataset.get("pokemon_descriptions")
    if pokemon_descriptions is not None and not isinstance(pokemon_descriptions, list):
        raise DataSourceError("ROM-derived Pokémon descriptions must be a list")

    learnsets = _validate_learnsets(
        learnset_dataset, dataset["game"], len(source_records)
    )
    evolutions = _validate_evolutions(
        evolution_dataset, dataset["game"], len(source_records)
    )
    evolution_item_names = _validate_evolution_item_names(evolution_dataset)
    evolution_item_slugs = _validate_evolution_item_slugs(
        item_dataset, dataset["game"], pokedb
    )
    machines = validate_machines(engine, machine_dataset, dataset["game"])
    tutors, tutor_ids_by_member, tutor_locations = validate_tutors(
        tutor_dataset, dataset["game"]
    )
    egg_moves = validate_egg_moves(engine, egg_move_dataset, dataset["game"])
    static_encounters_by_species = _validate_static_encounters(
        static_encounter_dataset, dataset["game"]
    )
    lookups = _RecordLookups(
        engine=engine,
        pokedb=pokedb,
        evolution_item_names=evolution_item_names,
        evolution_item_slugs=evolution_item_slugs,
        machines=machines,
        tutors=tutors,
        tutor_locations=tutor_locations,
        type_names=type_names,
        move_names=move_names,
        move_page_slugs=move_page_slugs,
        ability_names=ability_names,
        item_names=item_names,
        pokemon_names=pokemon_names,
        pokemon_descriptions=pokemon_descriptions,
        sprite_version=sprite_version,
        reference_version=reference_version,
    )
    records = []
    for expected_member, source in enumerate(source_records):
        if source.get("species_id") != expected_member:
            raise DataSourceError("Personal records must be ordered by member ID")
        records.append(
            _enrich_record(
                lookups,
                source,
                learnsets[expected_member],
                evolutions[expected_member],
                tutor_ids_by_member.get(expected_member, []),
                egg_moves.get(expected_member),
                static_encounters_by_species.get(expected_member, []),
            )
        )
    _attach_battle_forms(engine, records)
    enriched: PokemonDataset = {
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
    if "ability_descriptions" in dataset:
        enriched["ability_descriptions"] = dataset["ability_descriptions"]
    if dataset.get("description_sources"):
        enriched["description_sources"] = dataset["description_sources"]
    return enriched


def _attach_battle_forms(
    engine: EnrichmentTables, records: list[PokemonEnrichedRecord]
) -> None:
    """Attach each battle-only transformation record's stats/types to its
    base species' record as `battle_forms`, e.g. Castform's page gains its
    real Sunny/Rainy/Snowy stat blocks even though those transformations
    have no PokéDB reference page or public record of their own.
    """
    transformation_members = engine.TRANSFORMATION_MEMBERS
    if not transformation_members:
        return
    by_base_slug: dict[str, list[PokemonBattleForm]] = {}
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


@dataclass(frozen=True, slots=True)
class _RecordLookups:
    """Dataset-wide inputs shared by every personal record's enrichment."""

    engine: EnrichmentTables
    pokedb: PokeDBGeneration
    evolution_item_names: list[str]
    evolution_item_slugs: Mapping[int, str | None]
    machines: dict[int, dict[str, Any]]
    tutors: dict[int, dict[str, Any]]
    tutor_locations: list[str]
    type_names: Mapping[int, str] | None
    move_names: Mapping[int, str] | None
    move_page_slugs: Mapping[int, str] | None
    ability_names: list[str] | None
    item_names: list[str] | None
    pokemon_names: list[str] | None
    pokemon_descriptions: list[str] | None
    sprite_version: str | None
    reference_version: str | None


@dataclass(frozen=True, slots=True)
class _MemberIdentity:
    slug: str
    national_dex_id: int | None
    base_species: str | None
    form: str | None
    public: bool
    pokedb_record: dict[str, Any] | None


def _enrich_record(
    lookups: _RecordLookups,
    source: dict[str, Any],
    learnset: dict[str, Any] | None,
    evolution_set: dict[str, Any] | None,
    tutor_ids: list[int],
    egg_move_set: dict[str, Any] | None,
    static_encounters: list[dict[str, Any]],
) -> PokemonEnrichedRecord:
    member = source["species_id"]
    is_internal = member in lookups.engine.INTERNAL_MEMBERS
    return {
        **_identity_fields(lookups, member),
        **_species_traits(lookups, source, is_internal),
        **_move_compatibility(lookups, source, tutor_ids, is_internal),
        **_learnset_fields(lookups, learnset, egg_move_set, is_internal),
        "static_encounters": [
            {"level": entry["level"], "is_egg": entry["is_egg"]}
            for entry in (() if is_internal else static_encounters)
        ],
        **_evolution_fields(lookups, evolution_set, is_internal),
        "provenance": source["provenance"],
    }


def _member_identity(lookups: _RecordLookups, member: int) -> _MemberIdentity:
    engine = lookups.engine
    pokedb = lookups.pokedb
    if member in engine.INTERNAL_MEMBERS:
        return _MemberIdentity(
            slug=engine.INTERNAL_MEMBERS[member],
            national_dex_id=None,
            base_species=None,
            form=None,
            public=False,
            pokedb_record=None,
        )
    if member in engine.FORM_MEMBERS:
        slug = engine.FORM_MEMBERS[member]
        reference = pokedb.pokemon_for_name(slug)
        base_species = reference["species"]
        return _MemberIdentity(
            slug=slug,
            national_dex_id=pokedb.pokemon_for_species(base_species)["id"],
            base_species=base_species,
            form=slug.removeprefix(f"{base_species}-"),
            public=True,
            pokedb_record=reference,
        )
    transformation = engine.TRANSFORMATION_MEMBERS.get(member)
    if transformation is not None:
        base_slug = transformation["base_slug"]
        return _MemberIdentity(
            slug=transformation.get(
                "slug", f"{base_slug}-{name_slug(transformation['label'])}"
            ),
            national_dex_id=None,
            base_species=base_slug,
            form=None,
            public=False,
            pokedb_record=None,
        )
    national_dex_id = national_dex_id_for_member(engine, member)
    reference = pokedb.pokemon_for_id(national_dex_id)
    return _MemberIdentity(
        slug=reference["name"],
        national_dex_id=national_dex_id,
        base_species=reference["species"],
        form=None,
        public=True,
        pokedb_record=reference,
    )


def _identity_fields(lookups: _RecordLookups, member: int) -> PokemonIdentityFields:
    """Resolve a member's page identity, display name, and reference media."""
    engine = lookups.engine
    pokedb = lookups.pokedb
    identity = _member_identity(lookups, member)
    # Form and internal members keep their slug-derived labels; regular
    # species prefer the ROM's own name table ("Mr. Mime", "Farfetch'd").
    if (
        member in engine.FORM_MEMBERS
        or member in engine.INTERNAL_MEMBERS
        or member in engine.TRANSFORMATION_MEMBERS
    ):
        display_name = title_case_slug(identity.slug)
    else:
        display_name = pokemon_display_name(
            member, identity.slug, lookups.pokemon_names
        )
    record = identity.pokedb_record
    if record is None:
        sprite = None
        portrait = None
        cry = None
        sprites = []
        reference_data = None
    else:
        sprite = pokedb.pokemon_sprite(record, lookups.sprite_version)
        sprites = pokedb.pokemon_sprites(record, lookups.sprite_version)
        portrait = pokedb.pokemon_portrait(record) or sprite
        cry = pokedb.pokemon_cry(record)
        reference_data = pokedb.pokemon_reference(record, lookups.reference_version)
    return {
        "member": member,
        "slug": identity.slug,
        "name": display_name,
        "public": identity.public,
        "national_dex_id": identity.national_dex_id,
        "base_species": identity.base_species,
        "form": identity.form,
        "sprite": sprite,
        "portrait": portrait,
        "cry": cry,
        "sprites": sprites,
        "reference": with_rom_description(
            reference_data,
            _rom_pokedex_description(lookups, identity.national_dex_id),
            label="ROM Pokédex",
        ),
    }


def _rom_pokedex_description(
    lookups: _RecordLookups, national_dex_id: int | None
) -> str | None:
    descriptions = lookups.pokemon_descriptions
    if (
        descriptions is None
        or national_dex_id is None
        or national_dex_id >= len(descriptions)
    ):
        return None
    return descriptions[national_dex_id]


def _species_traits(
    lookups: _RecordLookups, source: dict[str, Any], is_internal: bool
) -> PokemonSpeciesTraits:
    """Resolve stats, types, abilities, held items, and breeding traits."""
    engine = lookups.engine
    return {
        "base_stats": source["base_stats"],
        "types": (
            []
            if is_internal
            else [
                type_id(engine, value, lookups.type_names)
                for value in source["type_ids"]
            ]
        ),
        "catch_rate": source["catch_rate"],
        "base_experience": source["base_experience"],
        "ev_yields": source["ev_yields"],
        "held_items": [] if is_internal else _wild_held_items(lookups, source),
        "gender_ratio": source["gender_ratio"],
        "hatch_cycles": source["hatch_cycles"],
        "base_friendship": source["base_friendship"],
        "growth_rate": (
            None
            if is_internal
            else named_id(
                source["growth_rate_id"], engine.GROWTH_RATE_NAMES, "growth rate"
            )
        ),
        "egg_groups": (
            []
            if is_internal
            else [
                named_id(value, engine.EGG_GROUP_NAMES, "egg group")
                for value in source["egg_group_ids"]
            ]
        ),
        "abilities": (
            []
            if is_internal
            else [
                {
                    **_ability_id(value, lookups),
                    "is_hidden": index == 2,
                }
                for index, value in enumerate(source["ability_ids"])
            ]
        ),
        "safari_flee_rate": source["safari_flee_rate"],
        "body_color": (
            None
            if is_internal
            else named_id(source["body_color_id"], engine.COLOR_NAMES, "body color")
        ),
        "flip_sprite": source["flip_sprite"],
    }


def _wild_held_items(
    lookups: _RecordLookups, source: dict[str, Any]
) -> list[PokemonHeldItem]:
    held_items = source["wild_held_items"]
    rarities = [("common", held_items["common"]), ("rare", held_items["rare"])]
    if held_items.get("dark_grass") is not None:
        rarities.append(("dark_grass", held_items["dark_grass"]))
    return [
        {
            "rarity": rarity,
            **item_reference(
                value,
                lookups.pokedb,
                lookups.item_names,
                page_slugs=lookups.evolution_item_slugs,
            ),
        }
        for rarity, value in rarities
    ]


def _move_compatibility(
    lookups: _RecordLookups,
    source: dict[str, Any],
    tutor_ids: list[int],
    is_internal: bool,
) -> PokemonMoveCompatibility:
    if is_internal:
        return {"machines": [], "tutor_moves": []}
    return {
        "machines": _enrich_compatible_machines(
            lookups.engine,
            source["machine_ids"],
            lookups.machines,
            lookups.pokedb,
            lookups.move_names,
            lookups.move_page_slugs,
        ),
        "tutor_moves": _enrich_compatible_tutors(
            tutor_ids,
            lookups.tutors,
            lookups.tutor_locations,
            lookups.pokedb,
            lookups.move_names,
            lookups.move_page_slugs,
        ),
    }


def _learnset_fields(
    lookups: _RecordLookups,
    learnset: dict[str, Any] | None,
    egg_move_set: dict[str, Any] | None,
    is_internal: bool,
) -> PokemonLearnsetFields:
    if is_internal:
        return {
            "level_up_moves": [],
            "learnset_provenance": None,
            "egg_moves": [],
            "egg_move_provenance": None,
        }
    return {
        "level_up_moves": _enrich_level_up_moves(
            learnset, lookups.pokedb, lookups.move_names, lookups.move_page_slugs
        ),
        "learnset_provenance": None if learnset is None else learnset["provenance"],
        "egg_moves": _enrich_egg_moves(
            egg_move_set, lookups.pokedb, lookups.move_names, lookups.move_page_slugs
        ),
        "egg_move_provenance": _egg_move_provenance(egg_move_set),
    }


def _evolution_fields(
    lookups: _RecordLookups,
    evolution_set: dict[str, Any] | None,
    is_internal: bool,
) -> PokemonEvolutionFields:
    if is_internal:
        return {"evolutions": [], "evolution_provenance": None}
    return {
        "evolutions": _enrich_evolutions(
            lookups.engine,
            evolution_set,
            lookups.pokedb,
            lookups.evolution_item_names,
            lookups.evolution_item_slugs,
            lookups.move_names,
            lookups.pokemon_names,
        ),
        "evolution_provenance": (
            evolution_set["provenance"] if evolution_set is not None else None
        ),
    }


def _validate_learnsets(
    dataset: dict[str, Any] | None, game: str, expected_count: int
) -> list[dict[str, Any] | None]:
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
    dataset: dict[str, Any] | None, game: str, expected_count: int
) -> list[dict[str, Any] | None]:
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


def _enrich_compatible_tutors(
    tutor_ids: list[int],
    tutors: dict[int, dict[str, Any]],
    location_names: list[str],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    move_page_slugs: Mapping[int, str] | None,
) -> list[TutorMoveCompatibility]:
    result = []
    for tutor_id in tutor_ids:
        tutor = tutors[tutor_id]
        move = move_reference(
            tutor["move_id"], pokedb, move_names, page_slugs=move_page_slugs
        )
        if move is None:
            raise DataSourceError(f"Tutor {tutor_id} references move ID 0")
        result.append(
            cast(
                TutorMoveCompatibility,
                {
                    **tutor,
                    "move": move,
                    "location": tutor_location(tutor, location_names),
                },
            )
        )
    return result


def _enrich_compatible_machines(
    engine: EnrichmentTables,
    machine_ids: list[int],
    machines: dict[int, dict[str, Any]],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    move_page_slugs: Mapping[int, str] | None,
) -> list[MachineCompatibility]:
    if not machines:
        return [
            {"id": value, "name": engine.machine_name(value)} for value in machine_ids
        ]
    result: list[MachineCompatibility] = []
    for machine_id in machine_ids:
        try:
            machine = machines[machine_id]
        except KeyError as error:
            raise DataSourceError(
                f"Pokémon compatibility references unknown machine ID {machine_id}"
            ) from error
        move = move_reference(
            machine["move_id"], pokedb, move_names, page_slugs=move_page_slugs
        )
        if move is None:
            raise DataSourceError(f"Machine {machine['name']} references move ID 0")
        result.append(
            {
                "id": machine_id,
                "name": machine["name"],
                "kind": machine["kind"],
                "number": machine["number"],
                "item_id": machine.get("item_id"),
                "move": move,
            }
        )
    return result


def _enrich_evolutions(
    engine: EnrichmentTables,
    evolution_set: dict[str, Any] | None,
    pokedb: PokeDBGeneration,
    item_names: list[str],
    item_slugs: Mapping[int, str | None],
    move_names: Mapping[int, str] | None,
    pokemon_names: list[str] | None = None,
) -> list[PokemonEvolution]:
    if evolution_set is None:
        return []
    result = []
    for entry in evolution_set["evolutions"]:
        method_id = entry["method_id"]
        target_member = entry["target_species_id"]
        target_national_dex_id = national_dex_id_for_member(engine, target_member)
        target = pokedb.pokemon_for_id(target_national_dex_id)
        evolution: PokemonEvolution = {
            "method_id": method_id,
            "parameter": entry["parameter"],
            "target_species_id": target_member,
            "method": named_id(
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
                "id": target_national_dex_id,
                "slug": target["name"],
                # `pokemon_names` (when present) is a ROM-extracted name
                # table indexed the same raw way as `target_member`
                # itself, not National Dex order.
                "name": pokemon_display_name(
                    target_member, target["name"], pokemon_names
                ),
            },
        }
        result.append(evolution)
    return result


def _evolution_parameter(
    engine: EnrichmentTables,
    entry: dict[str, Any],
    pokedb: PokeDBGeneration,
    item_names: list[str],
    item_slugs: Mapping[int, str | None],
    move_names: Mapping[int, str] | None,
    pokemon_names: list[str] | None = None,
) -> EvolutionParameter | None:
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
            "name": move_name(parameter, pokedb, move_names),
        }
    if kind == "pokemon":
        national_dex_id = national_dex_id_for_member(engine, parameter)
        species = pokedb.pokemon_for_id(national_dex_id)
        return {
            "kind": "pokemon",
            "id": national_dex_id,
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
    move_page_slugs: Mapping[int, str] | None,
) -> list[LevelUpMove]:
    moves: list[LevelUpMove] = []
    for entry in learnset["moves"] if learnset is not None else []:
        move = move_reference(
            entry["move_id"], pokedb, move_names, page_slugs=move_page_slugs
        )
        if move is None:
            raise DataSourceError("Level-up learnsets cannot reference move ID 0")
        moves.append({"level": entry["level"], "move": move})
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
    move_page_slugs: Mapping[int, str] | None,
) -> list[MoveLink]:
    moves: list[MoveLink] = []
    seen: set[int] = set()
    for move_id in egg_move_set["move_ids"] if egg_move_set is not None else []:
        if move_id in seen:
            continue
        seen.add(move_id)
        move = move_reference(move_id, pokedb, move_names, page_slugs=move_page_slugs)
        if move is None:
            raise DataSourceError("Egg moves cannot reference move ID 0")
        moves.append(move)
    return moves


def _ability_id(ability_id: int, lookups: _RecordLookups) -> EntityLink:
    if ability_id == 0:
        return {"id": 0, "slug": None, "name": None}
    reference_id = ability_reference_id(lookups.engine, ability_id)
    if reference_id is None:
        raise DataSourceError(f"Ability ID {ability_id} has no PokéDB entry")
    slug = lookups.pokedb.ability_name(reference_id)
    if slug is None:
        raise DataSourceError(f"Unknown ability ID: {ability_id}")
    ability_names = lookups.ability_names
    if ability_names is not None:
        if ability_id >= len(ability_names):
            raise DataSourceError(f"Unknown ability ID: {ability_id}")
        name = ability_names[ability_id]
    else:
        name = title_case_slug(slug)
    return {"id": ability_id, "slug": slug, "name": name}
