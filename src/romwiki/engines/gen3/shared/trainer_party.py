"""Gen III party-byte normalization for `pipeline/enrichment/trainer_party.py`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.schema.trainers import NormalizedTrainerPokemon
from romwiki.util.errors import DataSourceError

_STATS = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")


def normalize_trainer_party_member(
    member: Mapping[str, Any], has_custom_moves: bool
) -> NormalizedTrainerPokemon:
    required = ("species_id", "form_id", "level", "held_item_id", "move_ids")
    missing = [field for field in required if field not in member]
    if missing:
        raise DataSourceError(
            "Gen III trainer party member is missing fields: " + ", ".join(missing)
        )
    # The stored IV-like value's exact scale isn't confirmed against real
    # ROM data (values 0, 100, and 250 were seen this session -- none of
    # which confirms a 0-31 or 0-255 IV convention either way), so it's
    # carried through as a raw, undivided value rather than guessing a
    # conversion formula, and reported under `source_fields` for
    # transparency rather than `ivs` (which would claim a real IV).
    iv_strength = member.get("iv_strength")
    if not isinstance(iv_strength, int) or iv_strength < 0:
        raise DataSourceError(
            "Gen III trainer IV-like value must be a non-negative int"
        )
    move_ids = list(member["move_ids"]) if has_custom_moves else []
    return {
        "species_id": member["species_id"],
        "form_id": member["form_id"],
        "level": member["level"],
        "held_item_id": member["held_item_id"],
        "move_ids": move_ids,
        "moves_source": "explicit" if has_custom_moves else "level-up",
        # Ability/gender aren't stored per party slot in Generation III --
        # both are derived from the Pokemon's personality value at battle
        # time, which this table doesn't decode.
        "ability": None,
        "nature": None,
        "gender": None,
        "ivs": None,
        "evs": None,
        "calculated_stats": None,
        "source_fields": {"iv_like_value": iv_strength},
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
    # Without a verified IV, calculated stat ranges would misreport a
    # confidence this data doesn't have -- left undecoded until the
    # iv-like value's real scale is confirmed, matching how `ivs`/`evs`
    # above stay `None` instead of a guessed value.
    return member
