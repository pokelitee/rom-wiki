from __future__ import annotations

import unittest

from romwiki.pipeline.enrichment.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.util.errors import DataSourceError


class TrainerPartyNormalizationTests(unittest.TestCase):
    def test_normalizes_gen4_source_fields_and_explicit_moves(self) -> None:
        member = {
            "difficulty": 100,
            "gender_ability": 0,
            "level": 50,
            "species_id": 1,
            "form_id": 0,
            "held_item_id": 17,
            "move_ids": [33, 45, 0, 0],
            "ball_seal": 2,
        }

        normalized = normalize_trainer_party_member(
            "gen4_dppt", member, has_custom_moves=True
        )

        self.assertEqual(normalized["moves_source"], "explicit")
        self.assertEqual(normalized["move_ids"], [33, 45, 0, 0])
        self.assertEqual(
            normalized["source_fields"],
            {"difficulty": 100, "gender_ability": 0, "ball_seal": 2},
        )
        self.assertNotIn("difficulty", normalized)
        self.assertEqual(normalized["ability"], {"source": "derived", "slot": 1})
        self.assertEqual(normalized["ivs"]["values"]["hp"], 12)
        self.assertEqual(set(normalized["ivs"]["values"].values()), {12})
        self.assertEqual(set(normalized["evs"]["values"].values()), {0})
        self.assertEqual(normalized["evs"]["source"], "engine-default")

    def test_marks_gen4_default_moves_explicitly(self) -> None:
        normalized = normalize_trainer_party_member(
            "gen4_dppt",
            {
                "difficulty": 0,
                "gender_ability": 0,
                "level": 5,
                "species_id": 1,
                "form_id": 0,
                "held_item_id": None,
                "move_ids": [],
                "ball_seal": 0,
            },
            has_custom_moves=False,
        )

        self.assertEqual(normalized["moves_source"], "level-up")
        self.assertEqual(normalized["move_ids"], [])

    def test_derives_gen4_nature_and_gender_from_personality(self) -> None:
        normalized = normalize_trainer_party_member(
            "gen4_dppt",
            {
                "difficulty": 0,
                "gender_ability": 0,
                "level": 5,
                "species_id": 1,
                "form_id": 0,
                "held_item_id": None,
                "move_ids": [],
                "ball_seal": 0,
            },
            has_custom_moves=False,
        )

        derived = derive_trainer_party_attributes(
            "gen4_dppt",
            normalized,
            trainer_id=0,
            class_id=2,
            class_gender="female",
            gender_ratio=127,
            base_stats=None,
        )

        self.assertEqual(derived["nature"], {"source": "derived", "name": "Rash"})
        self.assertEqual(derived["gender"], {"source": "derived", "name": "Female"})

    def test_reproduces_gen4_invalid_iv_fallback(self) -> None:
        normalized = normalize_trainer_party_member(
            "gen4_dppt",
            {
                "difficulty": 196,
                "gender_ability": 9,
                "level": 50,
                "species_id": 466,
                "form_id": 0,
                "held_item_id": None,
                "move_ids": [],
                "ball_seal": 0,
            },
            has_custom_moves=False,
        )
        derived = derive_trainer_party_attributes(
            "gen4_dppt",
            normalized,
            trainer_id=320,
            class_id=79,
            class_gender="male",
            gender_ratio=63,
            base_stats=None,
        )

        self.assertEqual(derived["nature"]["name"], "Impish")
        self.assertEqual(
            derived["ivs"]["values"],
            {
                "hp": 4,
                "attack": 3,
                "defense": 29,
                "special_attack": 18,
                "special_defense": 15,
                "speed": 19,
            },
        )

    def test_derives_gen5_exact_hp_and_nature_dependent_ranges(self) -> None:
        normalized = normalize_trainer_party_member(
            "gen5_b2w2",
            {
                "iv_strength": 255,
                "ability_slot": 0,
                "forced_gender_flag": 0,
                "level": 50,
                "species_id": 1,
                "form_id": 0,
                "held_item_id": None,
                "move_ids": [],
            },
            has_custom_moves=False,
        )

        derived = derive_trainer_party_attributes(
            "gen5_b2w2",
            normalized,
            trainer_id=1,
            class_id=1,
            class_gender=None,
            gender_ratio=127,
            base_stats={
                "hp": 100,
                "attack": 100,
                "defense": 100,
                "special_attack": 100,
                "special_defense": 100,
                "speed": 100,
            },
        )

        stats = derived["calculated_stats"]
        self.assertEqual(derived["source_fields"]["iv_strength"], 255)
        self.assertEqual(derived["ability"], {"source": "engine-default", "slot": 0})
        self.assertNotIn("difficulty", derived["source_fields"])
        self.assertEqual(stats["values"]["hp"], 175)
        self.assertEqual(stats["values"]["attack"], {"minimum": 108, "maximum": 132})
        self.assertEqual(stats["limitation"], "nature-runtime-random")

    def test_rejects_unknown_engines(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "unknown_engine"):
            normalize_trainer_party_member("unknown_engine", {}, has_custom_moves=False)

    def test_rejects_invalid_gen4_difficulty(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "difficulty"):
            normalize_trainer_party_member(
                "gen4_dppt",
                {
                    "difficulty": 256,
                    "level": 5,
                    "species_id": 1,
                    "form_id": 0,
                    "held_item_id": None,
                    "move_ids": [],
                },
                has_custom_moves=False,
            )


if __name__ == "__main__":
    unittest.main()
