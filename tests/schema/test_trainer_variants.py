from __future__ import annotations

import unittest

from romwiki.schema.trainers import (
    unresolved_trainer_variant_support,
    validate_trainer_battle_families,
)
from romwiki.util.errors import DataSourceError


def _family() -> dict[str, object]:
    return {
        "id": "rival-opening",
        "label": "Opening rival battle",
        "order": 0,
        "provenance": {
            "source": "ROM script",
            "reference": "script:1@0x20",
            "verification": "Both dispatch targets were decoded.",
        },
        "variants": [
            {
                "trainer_id": 10,
                "order": 0,
                "conditions": [
                    {
                        "kind": "starter-choice",
                        "value": "snivy",
                        "label": "Player chose Snivy",
                    },
                    {
                        "kind": "sibling-version",
                        "value": "black-2",
                        "label": "Black 2",
                    },
                ],
            },
            {
                "trainer_id": 11,
                "order": 1,
                "conditions": [
                    {
                        "kind": "difficulty-mode",
                        "value": "challenge",
                        "label": "Challenge Mode",
                    }
                ],
            },
        ],
    }


class TrainerBattleFamilyContractTests(unittest.TestCase):
    def test_accepts_independent_version_and_battle_conditions(self) -> None:
        validate_trainer_battle_families(
            [_family()], unresolved_trainer_variant_support(), [10, 11]
        )

    def test_rejects_a_dangling_trainer_reference(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "missing trainer 11"):
            validate_trainer_battle_families(
                [_family()], unresolved_trainer_variant_support(), [10]
            )

    def test_rejects_contradictory_conditions(self) -> None:
        family = _family()
        family["variants"][0]["conditions"].append(
            {
                "kind": "starter-choice",
                "value": "tepig",
                "label": "Player chose Tepig",
            }
        )
        with self.assertRaisesRegex(DataSourceError, "contradictory condition"):
            validate_trainer_battle_families(
                [family], unresolved_trainer_variant_support(), [10, 11]
            )

    def test_rejects_duplicate_variants(self) -> None:
        family = _family()
        duplicate = dict(family["variants"][0])
        duplicate["order"] = 2
        family["variants"].append(duplicate)
        with self.assertRaisesRegex(DataSourceError, "duplicate variant"):
            validate_trainer_battle_families(
                [family], unresolved_trainer_variant_support(), [10, 11]
            )


if __name__ == "__main__":
    unittest.main()
