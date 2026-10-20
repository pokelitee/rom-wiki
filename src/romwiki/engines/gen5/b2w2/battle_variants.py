from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.engines.gen5.shared.starter_families import starter_branch_families
from romwiki.schema.trainers import unverified_trainer_variants
from romwiki.util.errors import ProfileError

_CONTRACTS = {
    "b2w2-retail-v1",
    "blaze-black-2-volt-white-2-v1.1",
    "blaze-black-2-redux-volt-white-2-redux-v1.4.1",
}


def _decoded_difficulty_families(
    profile_id: str,
    records: Sequence[Mapping[str, Any]],
    selector_data: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    decoded = (selector_data or {}).get("difficulty_branch_families") or ()
    records_by_id = {record.get("trainer_id"): record for record in records}
    families: list[dict[str, Any]] = []
    seen_dispatches: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for branch in decoded:
        normal_ids = tuple(branch.normal_trainer_ids)
        challenge_ids = tuple(branch.challenge_trainer_ids)
        dispatch = (normal_ids, challenge_ids)
        if dispatch in seen_dispatches:
            continue
        seen_dispatches.add(dispatch)
        for slot, (normal_id, challenge_id) in enumerate(
            zip(normal_ids, challenge_ids, strict=True), start=1
        ):
            normal = records_by_id.get(normal_id)
            challenge = records_by_id.get(challenge_id)
            if normal is None or challenge is None or normal_id == challenge_id:
                continue
            label = _difficulty_family_label(normal, challenge)
            suffix = f"-slot-{slot}" if len(normal_ids) > 1 else ""
            family_id = (
                f"difficulty-script-{branch.script_file_id:04d}-"
                f"{branch.position:04x}{suffix}"
            )
            families.append(
                {
                    "id": family_id,
                    "label": label,
                    "order": 100 + len(families),
                    "provenance": {
                        "source": "B2W2 ROM field-script difficulty branch",
                        "reference": (
                            f"{profile_id}:script:{branch.script_file_id}:"
                            f"0x{branch.position:X}{suffix}"
                        ),
                        "verification": (
                            "The script reads the current difficulty mode, compares "
                            "it with Challenge Mode, and branches to these exact "
                            "trainer records."
                        ),
                    },
                    "variants": [
                        {
                            "trainer_id": trainer_id,
                            "order": order,
                            "conditions": [
                                {
                                    "kind": "difficulty-mode",
                                    "value": mode,
                                    "label": f"{mode.title()} Mode",
                                }
                            ],
                        }
                        for order, (mode, trainer_id) in enumerate(
                            (
                                ("easy", normal_id),
                                ("normal", normal_id),
                                ("challenge", challenge_id),
                            )
                        )
                    ],
                }
            )
    return families


def _difficulty_family_label(
    normal: Mapping[str, Any], challenge: Mapping[str, Any]
) -> str:
    normal_label = _trainer_label(normal)
    challenge_label = _trainer_label(challenge)
    if normal_label == challenge_label:
        return f"{normal_label} difficulty battle"
    return f"{normal_label} / {challenge_label} difficulty battle"


def _trainer_label(record: Mapping[str, Any]) -> str:
    label = " ".join(
        str(value) for value in (record.get("class_name"), record.get("name")) if value
    )
    return label or f"Trainer {record['trainer_id']}"


def _n_families(profile_id: str, available: set[object]) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    if {5, 6}.issubset(available):
        families.append(
            {
                "id": "n-castle-first-battle",
                "label": "N's Castle first battle",
                "order": 400,
                "provenance": {
                    "source": "B2W2 version dispatch and exact trainer records",
                    "reference": f"{profile_id}:n-castle:first-battle",
                    "verification": (
                        "The Black 2-based Zekrom and White 2-based Reshiram "
                        "targets were matched to exact trainer records 5 and 6."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": trainer_id,
                        "order": order,
                        "conditions": [
                            {
                                "kind": "sibling-version",
                                "value": version,
                                "label": version_label,
                            },
                            {
                                "kind": "story-stage",
                                "value": "n-castle-first-battle",
                                "label": "First battle",
                            },
                        ],
                    }
                    for order, (trainer_id, version, version_label) in enumerate(
                        (
                            (5, "black-2-based", "Black 2-based version"),
                            (6, "white-2-based", "White 2-based version"),
                        )
                    )
                ],
            }
        )
    seasonal_records = (
        (782, "spring", "Spring"),
        (783, "summer", "Summer"),
        (784, "autumn", "Autumn"),
        (785, "winter", "Winter"),
    )
    if all(trainer_id in available for trainer_id, _, _ in seasonal_records):
        families.append(
            {
                "id": "n-castle-seasonal-rematch",
                "label": "N's Castle seasonal rematch",
                "order": 401,
                "provenance": {
                    "source": "B2W2 seasonal dispatch and exact trainer records",
                    "reference": f"{profile_id}:n-castle:seasonal-rematch",
                    "verification": (
                        "Spring, summer, autumn, and winter selection was matched "
                        "to exact trainer records 782 through 785."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": trainer_id,
                        "order": order,
                        "conditions": [
                            {
                                "kind": "season",
                                "value": season,
                                "label": season_label,
                            },
                            {
                                "kind": "rematch-stage",
                                "value": "seasonal-rematch",
                                "label": "Seasonal rematch",
                            },
                        ],
                    }
                    for order, (trainer_id, season, season_label) in enumerate(
                        seasonal_records
                    )
                ],
            }
        )
    return families


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
            f"Profile {profile_id!r} must select a verified B2W2 trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records}
    records_by_id: dict[int, Mapping[str, Any]] = {
        trainer_id: record
        for record in records
        if record.get("party") and (trainer_id := record.get("trainer_id")) is not None
    }
    families = starter_branch_families(profile_id, records_by_id, selector_data)
    families.extend(_decoded_difficulty_families(profile_id, records, selector_data))
    families.extend(_n_families(profile_id, available))
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {
                "status": "partial",
                "note": (
                    "Literal field-script difficulty dispatch is decoded from the ROM. "
                    "Indirect selectors and the complete runtime level-offset table "
                    "remain unresolved."
                ),
                "runtime": {
                    "easy_party": "normal-record",
                    "normal_party": "normal-record",
                    "challenge_party": "challenge-record-where-dispatched",
                    "displayed_level": "difficulty-adjusted-after-party-load",
                    "stat_level": "stored-record-level",
                    "iv_strength_field": "independent-party-byte",
                    "level_adjustment_scope": "all-trainer-battles",
                    "party_variant_scope": "decoded-field-script-dispatch",
                },
            },
            "rematch_stage": {
                "status": "partial",
                "note": (
                    "Difficulty-selected Pokémon League records are decoded. Other "
                    "runtime-selected rematches stay unrelated until their selector "
                    "is decoded."
                ),
            },
            "story_stage": {
                "status": "partial",
                "note": (
                    "Literal field-script selectors are decoded without inferring "
                    "relationships from trainer names or record adjacency."
                ),
            },
            "sibling_version": {"status": "verified"},
            "season": {"status": "verified"},
        },
        "battle_families": families,
    }
