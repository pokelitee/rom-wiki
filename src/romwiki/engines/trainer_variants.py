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
        *,
        selector_data: Mapping[str, Any] | None = ...,
    ) -> dict[str, Any]: ...


def resolve_trainer_variants(
    resolver: TrainerVariantResolver,
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    selector_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and validate one engine/profile's exact trainer relationships.

    `selector_data` carries selector tables the pipeline decoded from the ROM,
    because resolvers only see normalized records and cannot open the image
    themselves.
    """
    result = resolver.resolve_trainer_variants(
        profile_id, parameters, records, selector_data=selector_data
    )
    validate_trainer_battle_families(
        result["battle_families"],
        result["trainer_variant_support"],
        (
            trainer_id
            for record in records
            if (trainer_id := record.get("trainer_id")) is not None
        ),
    )
    return result
