from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {"bw-retail-v1", "blaze-black-volt-white-v3.1"}
_CHEREN_GROUPS = (
    ("bedroom", "Nuvema Town opening battle", (53, 54, 55)),
    ("route-3", "Route 3 rival battle", (56, 57, 58)),
    ("striaton", "Striaton City rival battle", (287, 288, 289)),
    ("route-4", "Route 4 rival battle", (403, 404, 405)),
    ("route-5", "Route 5 rival battle", (90, 91, 92)),
    ("twist-mountain", "Twist Mountain rival battle", (539, 540, 541)),
    ("route-10", "Route 10 rival battle", (588, 589, 590)),
    ("victory-road", "Victory Road rival battle", (591, 592, 593)),
)
_BIANCA_GROUPS = (
    ("bedroom", "Nuvema Town opening battle", (59, 60, 61)),
    ("route-2", "Route 2 rival battle", (498, 499, 500)),
    ("castelia-gate", "Castelia Gate rival battle", (507, 508, 509)),
    ("driftveil", "Driftveil City rival battle", (491, 492, 493)),
    ("route-8", "Route 8 rival battle", (494, 495, 496)),
    ("nuvema-rematch", "Nuvema Town rival rematch", (594, 595, 596)),
)
_CHEREN_STARTERS = (
    ("snivy", "Player chose Snivy"),
    ("tepig", "Player chose Tepig"),
    ("oshawott", "Player chose Oshawott"),
)
_BIANCA_STARTERS = (
    ("snivy", "Player chose Snivy"),
    ("tepig", "Player chose Tepig"),
    ("oshawott", "Player chose Oshawott"),
)


def _families(
    character: str,
    groups: tuple[tuple[str, str, tuple[int, int, int]], ...],
    starters: tuple[tuple[str, str], ...],
    available: set[object],
    profile_id: str,
    order_base: int,
) -> list[dict[str, Any]]:
    result = []
    for group_order, (stage, label, trainer_ids) in enumerate(groups):
        if not all(value in available for value in trainer_ids):
            continue
        result.append(
            {
                "id": f"{character}-{stage}",
                "label": f"{character.title()} — {label}",
                "order": order_base + group_order,
                "provenance": {
                    "source": "ROM field-script selection",
                    "reference": f"{profile_id}:{character}:{stage}",
                    "verification": (
                        "Starter-variable control flow was traced to all three exact "
                        "trainer IDs; static message-table names were not used."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": trainer_id,
                        "order": variant_order,
                        "conditions": [
                            {
                                "kind": "starter-choice",
                                "value": starter,
                                "label": starter_label,
                            },
                            {
                                "kind": "story-stage",
                                "value": stage,
                                "label": label,
                            },
                        ],
                    }
                    for variant_order, (
                        trainer_id,
                        (starter, starter_label),
                    ) in enumerate(zip(trainer_ids, starters, strict=True))
                ],
            }
        )
    return result


def extract_trainer_battle_families(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified BW trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records}
    families = _families(
        "cheren", _CHEREN_GROUPS, _CHEREN_STARTERS, available, profile_id, 0
    )
    families.extend(
        _families(
            "bianca", _BIANCA_GROUPS, _BIANCA_STARTERS, available, profile_id, 100
        )
    )
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {"status": "partial"},
            "story_stage": {"status": "partial"},
            "sibling_version": {"status": "verified"},
        },
        "battle_families": families,
    }
