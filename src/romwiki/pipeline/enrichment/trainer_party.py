from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.schema.trainers import NormalizedTrainerPokemon


def normalize_trainer_party_member(
    engine: str,
    member: Mapping[str, Any],
    *,
    has_custom_moves: bool,
) -> NormalizedTrainerPokemon:
    """Translate an engine party record into the shared trainer-party schema."""
    adapter = get_engine(engine)
    return adapter.trainer_party.normalize_trainer_party_member(
        member, has_custom_moves
    )


def derive_trainer_party_attributes(
    engine: str,
    member: NormalizedTrainerPokemon,
    *,
    trainer_id: int,
    class_id: int,
    class_gender: str | None,
    gender_ratio: int | None,
    base_stats: Mapping[str, Any] | None,
) -> NormalizedTrainerPokemon:
    adapter = get_engine(engine)
    return adapter.trainer_party.derive_trainer_party_attributes(
        member,
        trainer_id=trainer_id,
        class_id=class_id,
        class_gender=class_gender,
        gender_ratio=gender_ratio,
        base_stats=base_stats,
    )
