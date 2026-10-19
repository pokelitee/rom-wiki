from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any, cast

from romwiki.engines.registry import get_engine
from romwiki.pipeline.enrichment.common import (
    national_dex_id_for_member,
    pokemon_display_name,
)
from romwiki.pipeline.enrichment.names import (
    resolve_item_names,
    resolve_move_names,
    resolve_pokemon_names,
)
from romwiki.pipeline.enrichment.references import item_reference, move_name
from romwiki.pipeline.enrichment.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.pipeline.enrichment.trainer_rewards import calculate_base_prize_money
from romwiki.schema.enriched import (
    EntityLink,
    MoveDataset,
    MoveEnrichedRecord,
    PokemonDataset,
    PokemonEnrichedRecord,
    TrainerDataset,
    TrainerEnrichedFields,
    TrainerEnrichedRecord,
    TrainerItem,
)
from romwiki.schema.trainers import (
    TrainerAttribute,
    unresolved_trainer_variant_support,
    validate_trainer_battle_families,
)
from romwiki.schema.versions import (
    TRAINER_BATTLE_FAMILY_SCHEMA_VERSION,
    TRAINER_PARTY_SCHEMA_VERSION,
    TRAINERS_ENRICHED_SCHEMA_VERSION,
)
from romwiki.sources import PokeDBGeneration
from romwiki.util.errors import DataSourceError
from romwiki.util.text import title_case_slug


def enrich_trainer_dataset(
    dataset: dict[str, Any],
    pokedb: PokeDBGeneration,
    *,
    pokemon_dataset: PokemonDataset | None = None,
    move_dataset: MoveDataset | None = None,
    move_names: Mapping[int, str] | None = None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
) -> TrainerDataset:
    source_records = dataset.get("records")
    if not isinstance(source_records, list):
        raise DataSourceError("Trainer dataset records must be a list")
    engine = dataset.get("engine")
    if not isinstance(engine, str):
        raise DataSourceError("Trainer dataset must declare its source engine")
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
    move_names = resolve_move_names(dataset, move_names)
    item_names = resolve_item_names(dataset)
    pokemon_names = resolve_pokemon_names(dataset)
    records: list[TrainerEnrichedRecord] = []
    # IDs are consecutive but may start above zero when an archive reserves
    # leading members for a different record shape.
    base_trainer_id = source_records[0].get("trainer_id") if source_records else 0
    for offset, source in enumerate(source_records):
        if source.get("trainer_id") != base_trainer_id + offset:
            raise DataSourceError("Trainer records must be ordered by trainer ID")
        records.append(
            enrich_trainer_record(
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
    enriched: TrainerDataset = {
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


@cache
def _trainer_form_species(engine: str) -> frozenset[int]:
    """Species IDs with at least one known form entry for this engine."""
    engine_tables = get_engine(engine).enrich
    return frozenset(
        species_id
        for species_id, _form_id in (
            *engine_tables.TRAINER_FORM_SLUGS,
            *engine_tables.TRAINER_COSMETIC_FORM_LABELS,
        )
    )


def enrich_trainer_record(
    source: dict[str, Any],
    pokedb: PokeDBGeneration,
    move_names: Mapping[int, str] | None,
    item_names: list[str] | None,
    sprite_version: str | None = None,
    reference_version: str | None = None,
    *,
    engine: str,
    pokemon_records: Mapping[int | str, PokemonEnrichedRecord] | None = None,
    move_records: Mapping[int, MoveEnrichedRecord] | None = None,
    pokemon_names: list[str] | None = None,
) -> TrainerEnrichedRecord:
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
                reference = pokedb.pokemon_for_id(
                    national_dex_id_for_member(engine_tables, species_id)
                )
            elif species_id in _trainer_form_species(engine):
                # This species has known forms in the engine's table, but not
                # this specific form ID -- likely a parsing bug rather than a
                # deliberate hack encoding, so fail loudly instead of
                # silently resolving to the wrong Pokemon.
                raise DataSourceError(
                    f"Unknown trainer form {form_id} for species {species_id}"
                )
            else:
                # A hack's own data can set a form bit for a species with no
                # real Generation IV form entry at all (e.g. Sacred
                # Gold/Storm Silver's Pinsir). Resolve to the base species
                # reference rather than failing the build. The raw form ID
                # is still retained on the record below, so this never
                # claims the data doesn't exist -- only that it has no
                # distinct game entry to link.
                reference = pokedb.pokemon_for_id(
                    national_dex_id_for_member(engine_tables, species_id)
                )
        else:
            cosmetic_form = None
            if pokemon_records is not None:
                game_record = pokemon_records.get(species_id)
            reference = (
                None
                if game_record
                else pokedb.pokemon_for_id(
                    national_dex_id_for_member(engine_tables, species_id)
                )
            )
        pokemon = derive_trainer_party_attributes(
            engine,
            pokemon,
            trainer_id=source["trainer_id"],
            class_id=source["class_id"],
            class_gender=source.get("class_gender"),
            gender_ratio=(game_record.get("gender_ratio") if game_record else None),
            base_stats=(game_record.get("base_stats") if game_record else None),
        )
        if pokemon["moves_source"] == "level-up" and game_record is not None:
            pokemon["move_ids"] = _default_level_up_move_ids(
                game_record.get("level_up_moves", []), pokemon["level"]
            )
        if game_record:
            pokemon_slug = (
                game_record.get("base_species")
                if not game_record.get("public", True)
                else game_record["slug"]
            ) or game_record["slug"]
        else:
            # `reference` is only ever None when `game_record` is truthy
            # (see the assignments above), so it's guaranteed set here.
            assert reference is not None
            pokemon_slug = reference["name"]
        if game_record:
            pokemon_name = game_record["name"]
        elif form_id and slug:
            pokemon_name = title_case_slug(slug)
        else:
            assert reference is not None
            pokemon_name = pokemon_display_name(
                species_id, reference["name"], pokemon_names
            )
        if game_record:
            pokemon_sprite = game_record.get("sprite")
        else:
            assert reference is not None
            pokemon_sprite = pokedb.pokemon_sprite(reference, sprite_version)
        ability = _trainer_ability(pokemon.get("ability"), game_record)
        held_item = (
            item_reference(pokemon["held_item_id"], pokedb, item_names)
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
                    "id": national_dex_id_for_member(engine_tables, species_id),
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
                        "name": move_name(move_id, pokedb, move_names),
                        # `move_records` (the enriched `moves` dataset, see
                        # `enrich_trainer_dataset`'s `move_dataset` param)
                        # already computed each move's real page slug via
                        # its own ROM-decoded name table -- reusing it here
                        # (rather than falling back to PokeDB's canonical
                        # slug) avoids linking to a move page that doesn't
                        # exist under that slug (see
                        # `pipeline/enrichment/references.py`'s
                        # `move_reference` for the same fix elsewhere).
                        **(
                            {
                                "slug": move_records[move_id]["slug"],
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
    enriched_fields: TrainerEnrichedFields = {
        "party": party,
        "base_prize_money": calculate_base_prize_money(source, engine=engine),
        "victory_item": (
            _with_item_sprite(
                item_reference(source["victory_item_id"], pokedb, item_names),
                pokedb,
                reference_version,
            )
            if source.get("victory_item_id")
            else None
        ),
        # These slots are consumables available to the battle AI, not rewards
        # given to the player.
        "ai_battle_items": [
            _with_item_sprite(
                item_reference(item_id, pokedb, item_names), pokedb, reference_version
            )
            for item_id in source["reward_item_ids"]
            if item_id
        ],
    }
    return cast(TrainerEnrichedRecord, {**source, **enriched_fields})


def _default_level_up_move_ids(learnset: object, level: int) -> list[int]:
    """Resolve the four-move window used when no moves are stored per party slot."""

    if not isinstance(learnset, list):
        raise DataSourceError("Pokémon level-up moves must be a list")
    moves: list[int] = []
    for entry in learnset:
        if not isinstance(entry, Mapping):
            raise DataSourceError("Pokémon level-up move entries must be objects")
        learned_at = entry.get("level")
        move = entry.get("move")
        move_id = move.get("id") if isinstance(move, Mapping) else None
        if not isinstance(learned_at, int) or not isinstance(move_id, int):
            raise DataSourceError("Pokémon level-up move entries are incomplete")
        if learned_at > level:
            continue
        if move_id in moves:
            moves.remove(move_id)
        moves.append(move_id)
        if len(moves) > 4:
            moves.pop(0)
    return moves


def _trainer_pokemon_index(
    trainer_dataset: Mapping[str, Any],
    pokemon_dataset: PokemonDataset | None,
) -> dict[int | str, PokemonEnrichedRecord] | None:
    if pokemon_dataset is None:
        return None
    if pokemon_dataset.get("game") != trainer_dataset.get("game"):
        raise DataSourceError("Trainer and Pokémon datasets must be for the same game")
    records = pokemon_dataset.get("records")
    if not isinstance(records, list):
        raise DataSourceError("Pokémon dataset records must be a list")
    index: dict[int | str, PokemonEnrichedRecord] = {}
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
    move_dataset: MoveDataset | None,
) -> dict[int, MoveEnrichedRecord] | None:
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
    value: TrainerAttribute | None,
    pokemon_record: PokemonEnrichedRecord | None,
) -> dict[str, Any] | None:
    if value is None or pokemon_record is None:
        return None
    slot = value.get("slot")
    abilities = pokemon_record.get("abilities")
    if not isinstance(slot, int) or not isinstance(abilities, list):
        raise DataSourceError("Normalized trainer ability is missing its slot")
    if not pokemon_record.get("public", True) and not abilities:
        return None
    if slot == 0:
        possible = [
            ability
            for ability in abilities
            if isinstance(ability, dict) and ability.get("name")
        ]
        unique = []
        seen = set()
        for ability in possible:
            identity = (ability.get("id"), ability.get("name"))
            if identity not in seen:
                seen.add(identity)
                unique.append(ability)
        identities = {(ability.get("id"), ability.get("name")) for ability in unique}
        if len(identities) != 1:
            return {
                "slot": 0,
                "source": value["source"],
                "possibilities": unique,
            }
        ability = unique[0]
        return {**ability, "slot": 0, "source": value["source"]}
    if not 1 <= slot <= len(abilities):
        raise DataSourceError(f"Trainer ability slot {slot} is out of range")
    ability = abilities[slot - 1]
    if not isinstance(ability, dict) or not ability.get("name"):
        return None
    return {**ability, "slot": slot, "source": value["source"]}


def _with_item_sprite(
    item: EntityLink, pokedb: PokeDBGeneration, reference_version: str | None
) -> TrainerItem:
    return {**item, "sprite_url": _item_sprite_url(item, pokedb, reference_version)}


def _item_sprite_url(
    item: EntityLink, pokedb: PokeDBGeneration, reference_version: str | None
) -> str | None:
    name = item.get("name")
    if not name:
        return None
    reference = pokedb.item_reference(
        pokedb.item_reference_slug(name), reference_version
    )
    return reference.get("sprite_url") if reference else None
