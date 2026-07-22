from __future__ import annotations

import unittest

from romwiki.pipeline.trainer_party import normalize_trainer_party_member
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
        self.assertIsNone(normalized["ivs"])

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

    def test_rejects_unknown_engines(self) -> None:
        with self.assertRaisesRegex(DataSourceError, "unknown_engine"):
            normalize_trainer_party_member(
                "unknown_engine", {}, has_custom_moves=False
            )


if __name__ == "__main__":
    unittest.main()
