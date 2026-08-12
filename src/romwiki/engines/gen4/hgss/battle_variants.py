from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {
    "hgss-retail-v1",
    "sacred-gold-storm-silver-v1.05",
}
_RIVAL_GROUPS = (
    ("cherrygrove", "Cherrygrove City rival battle", (265, 2, 3)),
    ("azalea", "Azalea Town rival battle", (1, 266, 269)),
    ("burned-tower", "Burned Tower rival battle", (263, 267, 270)),
    ("goldenrod", "Goldenrod Tunnel rival battle", (288, 289, 271)),
    ("victory-road", "Victory Road rival battle", (264, 268, 272)),
    ("indigo-plateau", "Indigo Plateau rival battle", (285, 286, 287)),
    ("mt-moon", "Mt. Moon rival battle", (489, 490, 491)),
    ("double-battle", "Dragon's Den rival battle", (735, 736, 737)),
)
_STARTERS = (
    ("totodile", "Player chose Totodile"),
    ("chikorita", "Player chose Chikorita"),
    ("cyndaquil", "Player chose Cyndaquil"),
)


def extract_trainer_battle_families(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified HGSS trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records}
    families = []
    for order, (stage, label, trainer_ids) in enumerate(_RIVAL_GROUPS):
        if not all(value in available for value in trainer_ids):
            continue
        families.append(
            {
                "id": f"silver-{stage}",
                "label": label,
                "order": order,
                "provenance": {
                    "source": "ROM field-script selection",
                    "reference": f"{profile_id}:{stage}",
                    "verification": (
                        "Starter variable branches were traced to exact Silver trainer "
                        "records in the retail-compatible script layout."
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
                    ) in enumerate(zip(trainer_ids, _STARTERS, strict=True))
                ],
            }
        )
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {"status": "unsupported"},
            "rematch_stage": {
                "status": "partial",
                "note": "Silver stages are verified; phone-rematch state machines are unresolved.",
            },
            "story_stage": {"status": "partial"},
            "sibling_version": {"status": "verified"},
            "season": {"status": "unsupported"},
        },
        "battle_families": families,
    }
