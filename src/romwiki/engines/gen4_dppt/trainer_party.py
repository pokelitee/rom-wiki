from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.gen4_dppt.constants import NATURE_NAMES
from romwiki.schema.trainers import NormalizedTrainerPokemon
from romwiki.util.errors import DataSourceError

_STATS = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")
_LCRNG_MULTIPLIER = 0x41C64E6D
_LCRNG_INCREMENT = 0x6073


def normalize_trainer_party_member(
    member: Mapping[str, Any], has_custom_moves: bool
) -> NormalizedTrainerPokemon:
    required = ("species_id", "form_id", "level", "held_item_id", "move_ids")
    missing = [field for field in required if field not in member]
    if missing:
        raise DataSourceError(
            "Gen IV trainer party member is missing fields: " + ", ".join(missing)
        )
    difficulty = member.get("difficulty")
    difficulty_high = member.get("gender_ability", 0)
    if not isinstance(difficulty, int) or not 0 <= difficulty <= 255:
        raise DataSourceError("Gen IV trainer difficulty must be a byte")
    if not isinstance(difficulty_high, int) or not 0 <= difficulty_high <= 255:
        raise DataSourceError("Gen IV trainer difficulty high byte must be a byte")
    difficulty_value = difficulty | (difficulty_high << 8)
    iv = difficulty_value * 31 // 255
    move_ids = list(member["move_ids"]) if has_custom_moves else []
    return {
        "species_id": member["species_id"],
        "form_id": member["form_id"],
        "level": member["level"],
        "held_item_id": member["held_item_id"],
        "move_ids": move_ids,
        "moves_source": "explicit" if has_custom_moves else "level-up",
        "ability": {"source": "derived", "slot": 1},
        "nature": None,
        "gender": None,
        "ivs": (
            {"source": "derived", "values": dict.fromkeys(_STATS, iv)}
            if iv <= 31
            else None
        ),
        "evs": {
            "source": "engine-default",
            "values": dict.fromkeys(_STATS, 0),
        },
        "calculated_stats": None,
        "source_fields": {
            field: member[field]
            for field in ("difficulty", "gender_ability", "ball_seal")
            if field in member
        },
    }


def derive_trainer_party_attributes(
    member: NormalizedTrainerPokemon,
    *,
    trainer_id: int,
    class_id: int,
    class_gender: str,
    gender_ratio: int | None,
    base_stats: Mapping[str, Any] | None,
) -> NormalizedTrainerPokemon:
    if class_gender not in {"male", "female"}:
        raise DataSourceError(f"Unknown Gen IV trainer class gender: {class_gender!r}")
    if gender_ratio is not None and not 0 <= gender_ratio <= 255:
        raise DataSourceError("Gen IV Pokémon gender ratio must be a byte")
    source_fields = member["source_fields"]
    difficulty_value = source_fields["difficulty"] | (
        source_fields.get("gender_ability", 0) << 8
    )
    personality, rng_seed = _trainer_personality(
        trainer_id=trainer_id,
        class_id=class_id,
        species_id=member["species_id"],
        level=member["level"],
        difficulty=difficulty_value,
        class_gender=class_gender,
    )
    ivs = _trainer_ivs(difficulty_value, rng_seed)
    nature_index = personality % len(NATURE_NAMES)
    return {
        **member,
        "ivs": ivs,
        "nature": {
            "source": "derived",
            "name": NATURE_NAMES[nature_index],
        },
        "gender": (
            {"source": "derived", "name": _pokemon_gender(personality, gender_ratio)}
            if gender_ratio is not None
            else None
        ),
        "calculated_stats": _calculated_stats(
            species_id=member["species_id"],
            level=member["level"],
            base_stats=base_stats,
            ivs=ivs["values"],
            evs=member["evs"]["values"],
            nature_index=nature_index,
        ),
    }


def _trainer_personality(
    *,
    trainer_id: int,
    class_id: int,
    species_id: int,
    level: int,
    difficulty: int,
    class_gender: str,
) -> tuple[int, int]:
    seed = (trainer_id + species_id + level + difficulty) & 0xFFFFFFFF
    for _ in range(class_id):
        seed = (seed * _LCRNG_MULTIPLIER + _LCRNG_INCREMENT) & 0xFFFFFFFF
    random_value = seed >> 16
    gender_modifier = 0x78 if class_gender == "female" else 0x88
    return (random_value << 8) | gender_modifier, seed


def _trainer_ivs(difficulty: int, rng_seed: int) -> dict[str, Any]:
    iv = difficulty * 31 // 255
    if iv <= 31:
        return {"source": "derived", "values": dict.fromkeys(_STATS, iv)}
    # Pokémon creation consumes two RNG calls before regenerating an invalid
    # fixed IV value, then packs three five-bit IVs into each of two calls.
    seed = rng_seed
    for _ in range(2):
        seed = (seed * _LCRNG_MULTIPLIER + _LCRNG_INCREMENT) & 0xFFFFFFFF
    first, seed = _next_iv_triplet(seed)
    second, _ = _next_iv_triplet(seed)
    hp, attack, defense = first
    speed, special_attack, special_defense = second
    return {
        "source": "derived",
        "values": {
            "hp": hp,
            "attack": attack,
            "defense": defense,
            "special_attack": special_attack,
            "special_defense": special_defense,
            "speed": speed,
        },
    }


def _next_iv_triplet(seed: int) -> tuple[tuple[int, int, int], int]:
    seed = (seed * _LCRNG_MULTIPLIER + _LCRNG_INCREMENT) & 0xFFFFFFFF
    value = seed >> 16
    return ((value & 31, (value >> 5) & 31, (value >> 10) & 31), seed)


def _pokemon_gender(personality: int, gender_ratio: int) -> str:
    if gender_ratio == 255:
        return "Genderless"
    if gender_ratio == 254:
        return "Female"
    if gender_ratio == 0:
        return "Male"
    return "Female" if (personality & 0xFF) < gender_ratio else "Male"


def _calculated_stats(
    *,
    species_id: int,
    level: int,
    base_stats: Mapping[str, Any] | None,
    ivs: Mapping[str, int],
    evs: Mapping[str, int],
    nature_index: int,
) -> dict[str, Any] | None:
    if base_stats is None:
        return None
    if any(
        not isinstance(base_stats.get(stat), int) or base_stats[stat] <= 0
        for stat in _STATS
    ):
        raise DataSourceError("Gen IV trainer Pokémon has invalid base stats")
    if not isinstance(level, int) or not 1 <= level <= 100:
        raise DataSourceError("Gen IV trainer Pokémon level must be from 1 to 100")

    values = {
        "hp": (
            1
            if species_id == 292
            else ((2 * base_stats["hp"] + ivs["hp"] + evs["hp"] // 4) * level) // 100
            + level
            + 10
        )
    }
    nature_stats = ("attack", "defense", "speed", "special_attack", "special_defense")
    increased = nature_stats[nature_index // 5]
    decreased = nature_stats[nature_index % 5]
    for stat in nature_stats:
        value = ((2 * base_stats[stat] + ivs[stat] + evs[stat] // 4) * level) // 100 + 5
        if increased != decreased:
            if stat == increased:
                value = value * 110 // 100
            elif stat == decreased:
                value = value * 90 // 100
        values[stat] = value
    return {"source": "derived", "values": values}
