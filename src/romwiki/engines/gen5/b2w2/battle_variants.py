from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from romwiki.util.errors import ProfileError

_CONTRACTS = {
    "b2w2-retail-v1",
    "blaze-black-2-volt-white-2-v1.1",
    "blaze-black-2-redux-volt-white-2-redux-v1.4.1",
}
_RIVAL_GROUPS = (
    ("aspertia", "Aspertia City rival battle", (161, 162, 163)),
    ("floccesy-ranch", "Floccesy Ranch rival battle", (166, 167, 168)),
    ("castelia-sewers", "Castelia Sewers rival battle", (588, 589, 590)),
    ("pwt", "Pokémon World Tournament rival battle", (368, 369, 370)),
    ("undella", "Undella Town rival battle", (378, 379, 380)),
    ("route-13", "Route 13 rival battle", (701, 702, 703)),
    ("victory-road", "Victory Road rival battle", (684, 685, 686)),
    ("undella-rematch", "Undella Town rival rematch", (693, 694, 695)),
    ("driftveil-rematch", "Driftveil City rival rematch", (696, 697, 698)),
    ("seasonal-rematch", "Seasonal rival rematch", (794, 795, 796)),
)
_STARTERS = (
    ("snivy", "Player chose Snivy"),
    ("tepig", "Player chose Tepig"),
    ("oshawott", "Player chose Oshawott"),
)
_GYMS = (
    ("cheren", "Cheren Gym battle", 156, 764),
    ("roxie", "Roxie Gym battle", 157, 765),
    ("burgh", "Burgh Gym battle", 154, 766),
    ("elesa", "Elesa Gym battle", 153, 767),
    ("clay", "Clay Gym battle", 158, 768),
    ("skyla", "Skyla Gym battle", 155, 769),
    ("drayden", "Drayden Gym battle", 159, 770),
    ("marlon", "Marlon Gym battle", 160, 771),
)
_POKEMON_LEAGUE = (
    ("shauntal", "Shauntal Pokémon League battle", 38, 772, 143, 777),
    ("grimsley", "Grimsley Pokémon League battle", 40, 773, 145, 778),
    ("marshal", "Marshal Pokémon League battle", 39, 774, 144, 779),
    ("caitlin", "Caitlin Pokémon League battle", 41, 775, 146, 780),
    ("iris", "Iris Pokémon League battle", 341, 776, 536, 781),
)


def _rival_families(profile_id: str, available: set[object]) -> list[dict[str, Any]]:
    families = []
    for order, (stage, label, trainer_ids) in enumerate(_RIVAL_GROUPS):
        if not all(value in available for value in trainer_ids):
            continue
        families.append(
            {
                "id": f"hugh-{stage}",
                "label": label,
                "order": order,
                "provenance": {
                    "source": "B2W2 ROM field-script selection",
                    "reference": f"{profile_id}:hugh:{stage}",
                    "verification": (
                        "Starter-variable branches were traced to the complete Tepig, "
                        "Oshawott, and Snivy trainer-record run. The first record's "
                        "static message-table name was intentionally ignored."
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
    return families


def _difficulty_families(
    profile_id: str, available: set[object]
) -> list[dict[str, Any]]:
    families = []
    for order, (stage, label, normal_id, challenge_id) in enumerate(_GYMS, start=100):
        if normal_id not in available or challenge_id not in available:
            continue
        families.append(
            {
                "id": f"gym-{stage}",
                "label": label,
                "order": order,
                "provenance": {
                    "source": "B2W2 difficulty-mode trainer dispatch",
                    "reference": f"{profile_id}:difficulty:{stage}",
                    "verification": (
                        "Normal/Easy and Challenge dispatch targets were checked against "
                        "the exact trainer archives for this profile contract."
                    ),
                },
                "variants": [
                    {
                        "trainer_id": normal_id,
                        "order": 0,
                        "conditions": [
                            {
                                "kind": "difficulty-mode",
                                "value": "easy",
                                "label": "Easy Mode",
                            },
                            {
                                "kind": "story-stage",
                                "value": stage,
                                "label": label,
                            },
                        ],
                    },
                    {
                        "trainer_id": normal_id,
                        "order": 1,
                        "conditions": [
                            {
                                "kind": "difficulty-mode",
                                "value": "normal",
                                "label": "Normal Mode",
                            },
                            {
                                "kind": "story-stage",
                                "value": stage,
                                "label": label,
                            },
                        ],
                    },
                    {
                        "trainer_id": challenge_id,
                        "order": 2,
                        "conditions": [
                            {
                                "kind": "difficulty-mode",
                                "value": "challenge",
                                "label": "Challenge Mode",
                            },
                            {
                                "kind": "story-stage",
                                "value": stage,
                                "label": label,
                            },
                        ],
                    },
                ],
            }
        )
    return families


def _pokemon_league_difficulty_families(
    profile_id: str, available: set[object]
) -> list[dict[str, Any]]:
    families = []
    stages = (
        ("first-clear", "First Pokémon League clear", 0, 1),
        ("rematch", "Pokémon League rematch", 2, 3),
    )
    for order, (member, label, *trainer_ids) in enumerate(
        _POKEMON_LEAGUE, start=200
    ):
        if not all(trainer_id in available for trainer_id in trainer_ids):
            continue
        variants = []
        variant_order = 0
        for stage, stage_label, normal_offset, challenge_offset in stages:
            normal_id = trainer_ids[normal_offset]
            challenge_id = trainer_ids[challenge_offset]
            for mode, trainer_id in (
                ("easy", normal_id),
                ("normal", normal_id),
                ("challenge", challenge_id),
            ):
                variants.append(
                    {
                        "trainer_id": trainer_id,
                        "order": variant_order,
                        "conditions": [
                            {
                                "kind": "difficulty-mode",
                                "value": mode,
                                "label": f"{mode.title()} Mode",
                            },
                            {
                                "kind": "rematch-stage",
                                "value": stage,
                                "label": stage_label,
                            },
                        ],
                    }
                )
                variant_order += 1
        families.append(
            {
                "id": f"pokemon-league-{member}",
                "label": label,
                "order": order,
                "provenance": {
                    "source": "B2W2 difficulty-mode Pokémon League dispatch",
                    "reference": f"{profile_id}:difficulty:pokemon-league:{member}",
                    "verification": (
                        "Easy/Normal and Challenge first-clear and rematch rosters "
                        "were matched to the exact trainer archive records for this "
                        "profile contract."
                    ),
                },
                "variants": variants,
            }
        )
    return families


def _profile_difficulty_families(
    profile_id: str, contract: object, available: set[object]
) -> list[dict[str, Any]]:
    if (
        contract != "blaze-black-2-redux-volt-white-2-redux-v1.4.1"
        or not {4, 852}.issubset(available)
    ):
        return []
    return [
        {
            "id": "bianca-reversal-mountain",
            "label": "Bianca Reversal Mountain battle",
            "order": 300,
            "provenance": {
                "source": "Redux creator trainer documentation and ROM records",
                "reference": f"{profile_id}:difficulty:bianca:reversal-mountain",
                "verification": (
                    "The documented Easy/Normal and Challenge teams were matched "
                    "to exact Redux trainer records 4 and 852."
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
                        },
                        {
                            "kind": "story-stage",
                            "value": "reversal-mountain",
                            "label": "Reversal Mountain",
                        },
                    ],
                }
                for order, (mode, trainer_id) in enumerate(
                    (("easy", 4), ("normal", 4), ("challenge", 852))
                )
            ],
        }
    ]


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


def extract_trainer_battle_families(
    profile_id: str,
    parameters: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = parameters.get("trainer_variant_contract")
    if contract not in _CONTRACTS:
        raise ProfileError(
            f"Profile {profile_id!r} must select a verified B2W2 trainer variant contract"
        )
    available = {record.get("trainer_id") for record in records}
    families = _rival_families(profile_id, available)
    families.extend(_difficulty_families(profile_id, available))
    families.extend(_pokemon_league_difficulty_families(profile_id, available))
    families.extend(_profile_difficulty_families(profile_id, contract, available))
    families.extend(_n_families(profile_id, available))
    return {
        "trainer_variant_support": {
            "starter_choice": {"status": "verified"},
            "difficulty_mode": {
                "status": "partial",
                "note": (
                    "Gym party dispatch and the stored-level/stat bug are verified. "
                    "The engine's complete level-offset band table remains unresolved."
                ),
                "runtime": {
                    "easy_party": "normal-record",
                    "normal_party": "normal-record",
                    "challenge_party": "challenge-record-where-dispatched",
                    "displayed_level": "difficulty-adjusted-after-party-load",
                    "stat_level": "stored-record-level",
                    "iv_strength_field": "independent-party-byte",
                    "level_adjustment_scope": "all-trainer-battles",
                    "party_variant_scope": "verified-dispatch-only",
                },
            },
            "rematch_stage": {"status": "partial"},
            "story_stage": {"status": "partial"},
            "sibling_version": {"status": "verified"},
            "season": {"status": "verified"},
        },
        "battle_families": families,
    }
