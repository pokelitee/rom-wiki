from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.schema.trainers import NormalizedTrainerPokemon
from romwiki.util.errors import DataSourceError


def normalize_trainer_party_member(
    member: Mapping[str, Any], has_custom_moves: bool
) -> NormalizedTrainerPokemon:
    required = ("species_id", "form_id", "level", "held_item_id", "move_ids")
    missing = [field for field in required if field not in member]
    if missing:
        raise DataSourceError(
            "Gen IV trainer party member is missing fields: " + ", ".join(missing)
        )
    move_ids = list(member["move_ids"]) if has_custom_moves else []
    return {
        "species_id": member["species_id"],
        "form_id": member["form_id"],
        "level": member["level"],
        "held_item_id": member["held_item_id"],
        "move_ids": move_ids,
        "moves_source": "explicit" if has_custom_moves else "level-up",
        "ability": None,
        "nature": None,
        "gender": None,
        "ivs": None,
        "evs": None,
        "source_fields": {
            field: member[field]
            for field in ("difficulty", "gender_ability", "ball_seal")
            if field in member
        },
    }
