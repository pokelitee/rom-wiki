from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from romwiki.schema.trainers import validate_trainer_battle_families


class TrainerVariantResolver(Protocol):
    def resolve_trainer_variants(
        self,
        profile_id: str,
        parameters: Mapping[str, Any],
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]: ...


def resolve_trainer_variants(
    resolver: TrainerVariantResolver,
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve and validate one engine/profile's exact trainer relationships."""
    result = resolver.resolve_trainer_variants(profile_id, parameters, records)
    validate_trainer_battle_families(
        result["battle_families"],
        result["trainer_variant_support"],
        (record.get("trainer_id") for record in records),
    )
    return result
