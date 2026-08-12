from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {"platinum-retail-v1", "renegade-platinum-v1.3.0"}
_RIVAL_GROUPS = (
    ("route-201", "Route 201 rival battle", (247, 248, 249)),
    ("hearthome", "Hearthome City rival battle", (470, 471, 472)),
    ("pastoria", "Pastoria City rival battle", (473, 474, 475)),
    ("canalave", "Canalave City rival battle", (476, 477, 478)),
    ("pokemon-league", "Pokémon League rival battle", (479, 480, 481)),
    ("tag-battle", "Spear Pillar partner battle", (607, 619, 620)),
    ("fight-area", "Fight Area rival battle", (837, 838, 839)),
    ("weekend-rematch-1", "Rival rematch stage 1", (840, 841, 842)),
    ("starter-demo", "Starter demonstration battle", (850, 851, 852)),
    ("weekend-rematch-2", "Rival rematch stage 2", (871, 872, 873)),
    ("pokemon-league-rematch", "Pokémon League rival rematch", (923, 924, 925)),
)
_STARTERS = (
    ("piplup", "Player chose Piplup"),
    ("turtwig", "Player chose Turtwig"),
    ("chimchar", "Player chose Chimchar"),
)
_REMATCH_STAGES = {
    "weekend-rematch-1",
    "weekend-rematch-2",
    "pokemon-league-rematch",
}


def resolve_trainer_variants(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified DPPT trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records if record.get("party")}
    groups = [
        group
        for group in _RIVAL_GROUPS
        if all(value in available for value in group[2])
    ]
    families = []
    for order, (stage, label, trainer_ids) in enumerate(groups):
        families.append(
            {
                "id": f"barry-{stage}",
                "label": label,
                "order": order,
                "provenance": {
                    "source": "ROM field-script selection",
                    "reference": f"{profile_id}:{stage}",
                    "verification": (
                        "Starter variable branches were traced to the three literal "
                        "trainer records and checked against each exact party."
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
                            *(
                                [
                                    {
                                        "kind": "rematch-stage",
                                        "value": "rematch",
                                        "label": "Rematch",
                                    }
                                ]
                                if stage in _REMATCH_STAGES
                                else []
                            ),
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
                "note": "Verified Barry stages only; Vs. Seeker NPC chains remain unresolved.",
            },
            "story_stage": {"status": "partial"},
            "sibling_version": {"status": "unsupported"},
            "season": {"status": "unsupported"},
        },
        "battle_families": families,
    }
