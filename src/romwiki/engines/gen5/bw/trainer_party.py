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
        "ability_slot",
        "forced_gender_flag",
    )
    missing = [field for field in required if field not in member]
    if missing:
        raise DataSourceError(
            "Gen V trainer party member is missing fields: " + ", ".join(missing)
        )
    iv_strength = member.get("iv_strength", member.get("difficulty"))
    if not isinstance(iv_strength, int) or not 0 <= iv_strength <= 255:
        raise DataSourceError("Gen V trainer IV-strength value must be a byte")
    iv = iv_strength * 31 // 255
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
        "ivs": {"source": "derived", "values": dict.fromkeys(_STATS, iv)},
        "evs": {"source": "engine-default", "values": dict.fromkeys(_STATS, 0)},
        "calculated_stats": None,
        "source_fields": {
            "iv_strength": iv_strength,
            **{
                field: member[field]
                for field in ("ability_slot", "forced_gender_flag")
                if field in member
            },
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
    if base_stats is not None:
        member["calculated_stats"] = _calculated_stat_ranges(
            species_id=member["species_id"],
            level=member["level"],
            base_stats=base_stats,
            ivs=member["ivs"]["values"],
            evs=member["evs"]["values"],
        )
    return member


def _calculated_stat_ranges(
    *,
    species_id: int,
    level: int,
    base_stats: Mapping[str, Any],
    ivs: Mapping[str, int],
    evs: Mapping[str, int],
) -> dict[str, Any]:
    if any(
        not isinstance(base_stats.get(stat), int) or base_stats[stat] <= 0
        for stat in _STATS
    ):
        raise DataSourceError("Gen V trainer Pokemon has invalid base stats")
    if not isinstance(level, int) or not 1 <= level <= 100:
        raise DataSourceError("Gen V trainer Pokemon level must be from 1 to 100")

    hp = (
        1
        if species_id == 292
        else ((2 * base_stats["hp"] + ivs["hp"] + evs["hp"] // 4) * level) // 100
        + level
        + 10
    )
    values: dict[str, Any] = {"hp": hp}
    for stat in _STATS[1:]:
        neutral = (
            (2 * base_stats[stat] + ivs[stat] + evs[stat] // 4) * level
        ) // 100 + 5
        values[stat] = {"minimum": neutral * 90 // 100, "maximum": neutral * 110 // 100}
    return {
        "source": "derived",
        "values": values,
        "limitation": "nature-runtime-random",
    }
