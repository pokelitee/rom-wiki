from __future__ import annotations

import unittest

from romwiki.engines.gen5.b2w2.battle_variants import (
    extract_trainer_battle_families,
)
from romwiki.engines.gen5.b2w2.trainers import resolve_common_script_trainer_id


class B2W2TrainerVariantTests(unittest.TestCase):
    def test_preserves_the_fire_branch_despite_its_static_name(self) -> None:
        records = [
            {"trainer_id": trainer_id, "name": name}
            for trainer_id, name in (
                (161, "Marlon"),
                (162, "Rival"),
                (163, "Rival"),
            )
        ]
        contract = extract_trainer_battle_families(
            "black-2-us",
            {"trainer_variant_contract": "b2w2-retail-v1"},
            records,
        )

        family = contract["battle_families"][0]
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]],
            [161, 162, 163],
        )
        self.assertEqual(family["variants"][0]["conditions"][0]["value"], "snivy")

    def test_does_not_inherit_the_bw_common_script_band_rule(self) -> None:
        self.assertIsNone(resolve_common_script_trainer_id(2161, trainer_count=814))


if __name__ == "__main__":
    unittest.main()
