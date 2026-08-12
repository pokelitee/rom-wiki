from __future__ import annotations

import unittest

from romwiki.engines.gen5.b2w2.battle_variants import (
    extract_trainer_battle_families,
)
from romwiki.engines.gen5.b2w2.trainers import (
    resolve_common_script_trainer_id,
    trainer_name_index,
)


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

    def test_retains_the_zero_entry_in_the_trainer_name_table(self) -> None:
        self.assertEqual(trainer_name_index(155), 155)

    def test_relates_elite_four_and_champion_difficulty_records(self) -> None:
        trainer_ids = {
            38,
            39,
            40,
            41,
            143,
            144,
            145,
            146,
            341,
            536,
            *range(772, 782),
        }
        contract = extract_trainer_battle_families(
            "black-2-us",
            {"trainer_variant_contract": "b2w2-retail-v1"},
            [{"trainer_id": trainer_id} for trainer_id in trainer_ids],
        )

        families = {family["id"]: family for family in contract["battle_families"]}
        shauntal = families["pokemon-league-shauntal"]
        self.assertEqual(
            [variant["trainer_id"] for variant in shauntal["variants"]],
            [38, 38, 772, 143, 143, 777],
        )
        self.assertEqual(
            shauntal["variants"][-1]["conditions"][1]["value"], "rematch"
        )
        iris = families["pokemon-league-iris"]
        self.assertEqual(
            [variant["trainer_id"] for variant in iris["variants"]],
            [341, 341, 776, 536, 536, 781],
        )

    def test_redux_relates_biancas_documented_difficulty_teams(self) -> None:
        contract = extract_trainer_battle_families(
            "blaze-black-2-redux",
            {
                "trainer_variant_contract": (
                    "blaze-black-2-redux-volt-white-2-redux-v1.4.1"
                )
            },
            [{"trainer_id": 4}, {"trainer_id": 852}],
        )

        family = contract["battle_families"][0]
        self.assertEqual(family["id"], "bianca-reversal-mountain")
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]], [4, 4, 852]
        )


if __name__ == "__main__":
    unittest.main()
