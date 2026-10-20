from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.engines.gen5.shared.starter_families import starter_branch_families
from romwiki.schema.trainers import unverified_trainer_variants
from romwiki.util.errors import ProfileError

_CONTRACTS = {"bw-retail-v1", "blaze-black-volt-white-v3.1"}


def resolve_trainer_variants(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    selector_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract is None:
        return unverified_trainer_variants()
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified BW trainer variant contract"
        )
    records_by_id: dict[int, Mapping[str, Any]] = {
        trainer_id: record
        for record in records
        if record.get("party") and (trainer_id := record.get("trainer_id")) is not None
    }
    families = starter_branch_families(profile_id, records_by_id, selector_data)
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {
                "status": "partial",
                "note": (
                    "The Nuvema Town rival rematch is verified. Other runtime-selected "
                    "rematches stay unrelated until their selector is decoded."
                ),
            },
            "story_stage": {
                "status": "partial",
                "note": (
                    "Starter-selected rival branches are decoded across the field "
                    "scripts. Other runtime-selected story stages stay unrelated "
                    "until their selector is decoded."
                ),
            },
            "sibling_version": {"status": "verified"},
            "season": {"status": "unsupported"},
        },
        "battle_families": families,
    }
