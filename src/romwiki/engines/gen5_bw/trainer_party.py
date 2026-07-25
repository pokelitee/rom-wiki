from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.schema.trainers import NormalizedTrainerPokemon
from romwiki.util.errors import DataSourceError

_STATS = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")

# Trainer.java's own comment on the "SB" byte: "Fm = 1 for forced female,
# Ml = 1 for forced male" -- packed as two separate bits, not an enum, but
# real data never sets both (verified against Gym Leader Burgh's forced-male/
# forced-female Emolga pair, trainer 23).
_FORCED_GENDER_NAMES = {1: "Male", 2: "Female"}


def normalize_trainer_party_member(
    member: Mapping[str, Any], has_custom_moves: bool
) -> NormalizedTrainerPokemon:
    required = (
        "species_id",
        "form_id",
        "level",
        "held_item_id",
        "move_ids",
        "difficulty",
        "ability_slot",
        "forced_gender_flag",
    )
    missing = [field for field in required if field not in member]
    if missing:
        raise DataSourceError(
            "Gen V trainer party member is missing fields: " + ", ".join(missing)
        )
    difficulty = member["difficulty"]
    if not isinstance(difficulty, int) or not 0 <= difficulty <= 255:
        raise DataSourceError("Gen V trainer difficulty must be a byte")
    iv = difficulty * 31 // 255
    move_ids = list(member["move_ids"]) if has_custom_moves else []
    ability_slot = member["ability_slot"]
    forced_gender_flag = member["forced_gender_flag"]
    return {
        "species_id": member["species_id"],
        "form_id": member["form_id"],
        "level": member["level"],
        "held_item_id": member["held_item_id"],
        "move_ids": move_ids,
        "moves_source": "explicit" if has_custom_moves else "level-up",
        # ability_slot 0 means "random" (Gen5RomHandler.java's own comment:
        # "Ab Ab = ability number, 0 for random") -- genuine in-game
        # randomness this project doesn't simulate, unlike a stored slot.
        "ability": (
            {"source": "stored", "slot": ability_slot} if ability_slot else None
        ),
        # Unlike Generation IV, nature isn't derived from a documented,
        # reproducible personality-value algorithm for this generation (the
        # randomizer community's own Trainer/TrainerPokemon model has no
        # nature field at all for Gen V) -- it's genuine runtime randomness,
        # so it stays unavailable rather than guessed.
        "nature": None,
        "gender": (
            {"source": "stored", "name": _FORCED_GENDER_NAMES[forced_gender_flag]}
            if forced_gender_flag in _FORCED_GENDER_NAMES
            else None
        ),
        "ivs": {"source": "derived", "values": {stat: iv for stat in _STATS}},
        "evs": {"source": "engine-default", "values": {stat: 0 for stat in _STATS}},
        "calculated_stats": None,
        "source_fields": {
            field: member[field]
            for field in ("difficulty", "ability_slot", "forced_gender_flag")
            if field in member
        },
    }


def derive_trainer_party_attributes(
    member: NormalizedTrainerPokemon,
    *,
    trainer_id: int,
    class_id: int,
    class_gender: str | None,
    gender_ratio: int | None,
    base_stats: Mapping[str, Any] | None,
) -> NormalizedTrainerPokemon:
    # Ability and gender are already resolved in normalize_trainer_party_member
    # (stored directly in the ROM, not RNG-derived); nature and calculated
    # stats stay unavailable since this generation's runtime RNG for them
    # isn't one this project reproduces. Nothing left to derive here --
    # this function exists only to satisfy the shared enrichment contract.
    return member
