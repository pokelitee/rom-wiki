from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from romwiki.engines.gen4_dppt.trainer_party import (
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
