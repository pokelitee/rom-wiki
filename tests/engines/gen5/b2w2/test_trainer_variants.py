from __future__ import annotations

import unittest

from romwiki.engines.gen5.b2w2.battle_variants import (
    resolve_trainer_variants,
)
from romwiki.engines.gen5.b2w2.difficulty_branches import DifficultyBranchFamily
from romwiki.engines.gen5.b2w2.trainers import (
    resolve_common_script_trainer_id,
    trainer_name_index,
)
from romwiki.engines.gen5.shared.starter_branches import Gen5StarterBranchFamily


class B2W2TrainerVariantTests(unittest.TestCase):
    def test_relates_decoded_starter_branches_despite_a_static_name(self) -> None:
        # The first record's message-table name is stale ("Marlon"); the family
        # comes from the decoded branch and is still the rival's.
        records = [
            {
                "trainer_id": trainer_id,
                "class_name": "PKMN Trainer",
                "name": name,
                "party": [{"species_id": 1}],
                "script_references": [{"name": "Aspertia City"}],
            }
            for trainer_id, name in ((161, "Marlon"), (162, "Rival"), (163, "Rival"))
        ]
        family = Gen5StarterBranchFamily(
            script_file_id=854,
            position=0,
            selected=((0, 161), (1, 162)),
            fallthrough_trainer_id=163,
        )
        contract = resolve_trainer_variants(
            "black-2-us",
            {"trainer_variant_contract": "b2w2-retail-v1"},
            records,
            selector_data={
                "starter_branch_families": (family,),
                "starter_species": (495, 498, 501),
                "species_names": {495: "snivy", 498: "tepig", 501: "oshawott"},
            },
        )

        [decoded] = contract["battle_families"]
        self.assertEqual(decoded["label"], "Aspertia City rival battle")
        self.assertEqual(
            [variant["trainer_id"] for variant in decoded["variants"]],
            [161, 162, 163],
        )
        self.assertEqual(
            [variant["conditions"][0]["value"] for variant in decoded["variants"]],
            ["snivy", "tepig", "oshawott"],
        )

    def test_inherits_the_bw_common_script_band_rule(self) -> None:
        # Verified against real Black 2 ROM data: B2W2 reuses BW's band
        # arithmetic unchanged.
        self.assertEqual(resolve_common_script_trainer_id(2161, trainer_count=814), 161)

    def test_retains_the_zero_entry_in_the_trainer_name_table(self) -> None:
        self.assertEqual(trainer_name_index(155), 155)

    def test_relates_decoded_difficulty_records_without_known_ids(self) -> None:
        contract = resolve_trainer_variants(
            "black-2-us",
            {"trainer_variant_contract": "b2w2-retail-v1"},
            [
                {"trainer_id": 38, "class_name": "Elite Four", "name": "Shauntal"},
                {"trainer_id": 772, "class_name": "Elite Four", "name": "Shauntal"},
            ],
            selector_data={
                "difficulty_branch_families": (
                    DifficultyBranchFamily(280, 269, (38,), (772,)),
                )
            },
        )

        family = contract["battle_families"][0]
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]],
            [38, 38, 772],
        )
        self.assertIn("script-0280", family["id"])

    def test_redux_relates_biancas_decoded_difficulty_teams(self) -> None:
        contract = resolve_trainer_variants(
            "blaze-black-2-redux",
            {
                "trainer_variant_contract": (
                    "blaze-black-2-redux-volt-white-2-redux-v1.4.1"
                )
            },
            [
                {"trainer_id": 4, "class_name": "Trainer", "name": "Bianca"},
                {"trainer_id": 852, "class_name": "Trainer", "name": "Bianca"},
            ],
            selector_data={
                "difficulty_branch_families": (
                    DifficultyBranchFamily(1062, 239, (4,), (852,)),
                )
            },
        )

        family = contract["battle_families"][0]
        self.assertEqual(family["id"], "difficulty-script-1062-00ef")
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]], [4, 4, 852]
        )

    def test_relates_ns_version_selected_first_battle(self) -> None:
        contract = resolve_trainer_variants(
            "black-2-us",
            {"trainer_variant_contract": "b2w2-retail-v1"},
            [{"trainer_id": trainer_id} for trainer_id in (5, 6)],
        )

        family = contract["battle_families"][0]
        self.assertEqual(family["id"], "n-castle-first-battle")
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]], [5, 6]
        )
        self.assertEqual(
            [variant["conditions"][0]["value"] for variant in family["variants"]],
            ["black-2-based", "white-2-based"],
        )

    def test_relates_ns_four_seasonal_rematches(self) -> None:
        contract = resolve_trainer_variants(
            "blaze-black-2-redux",
            {
                "trainer_variant_contract": (
                    "blaze-black-2-redux-volt-white-2-redux-v1.4.1"
                )
            },
            [{"trainer_id": trainer_id} for trainer_id in range(782, 786)],
        )

        family = contract["battle_families"][0]
        self.assertEqual(family["id"], "n-castle-seasonal-rematch")
        self.assertEqual(
            [variant["trainer_id"] for variant in family["variants"]],
            [782, 783, 784, 785],
        )
        self.assertEqual(
            [variant["conditions"][0]["value"] for variant in family["variants"]],
            ["spring", "summer", "autumn", "winter"],
        )


if __name__ == "__main__":
    unittest.main()
