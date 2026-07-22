from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from romwiki.engines.gen4_dppt.trainer_party import (
    derive_trainer_party_attributes as derive_gen4_dppt_party_attributes,
    normalize_trainer_party_member as normalize_gen4_dppt_party_member,
)
from romwiki.schema.trainers import NormalizedTrainerPokemon
from romwiki.util.errors import DataSourceError


TrainerPartyNormalizer = Callable[
    [Mapping[str, Any], bool], NormalizedTrainerPokemon
]


def normalize_trainer_party_member(
    engine: str,
    member: Mapping[str, Any],
    *,
    has_custom_moves: bool,
) -> NormalizedTrainerPokemon:
    """Translate an engine party record into the shared trainer-party schema."""
    try:
        normalizer = _NORMALIZERS[engine]
    except KeyError as error:
        raise DataSourceError(
            f"Trainer party normalization is not implemented for engine {engine!r}"
        ) from error
    return normalizer(member, has_custom_moves)


_NORMALIZERS: dict[str, TrainerPartyNormalizer] = {
    "gen4_dppt": normalize_gen4_dppt_party_member,
}


def derive_trainer_party_attributes(
    engine: str,
    member: NormalizedTrainerPokemon,
    *,
    trainer_id: int,
    class_id: int,
    class_gender: str,
    gender_ratio: int | None,
    base_stats: Mapping[str, Any] | None,
) -> NormalizedTrainerPokemon:
    try:
        derive = _ATTRIBUTE_DERIVERS[engine]
    except KeyError as error:
        raise DataSourceError(
            f"Trainer party attribute derivation is not implemented for engine {engine!r}"
        ) from error
    return derive(
        member,
        trainer_id=trainer_id,
        class_id=class_id,
        class_gender=class_gender,
        gender_ratio=gender_ratio,
        base_stats=base_stats,
    )


_ATTRIBUTE_DERIVERS = {
    "gen4_dppt": derive_gen4_dppt_party_attributes,
}
