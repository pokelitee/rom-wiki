from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.trainer_party import (
    derive_trainer_party_attributes,
    normalize_trainer_party_member,
)
from romwiki.util.errors import DataSourceError


def _member(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "iv_strength": 100,
        "ability_slot": 0,
        "forced_gender_flag": 0,
        "level": 37,
        "species_id": 106,
        "form_id": 0,
        "held_item_id": 207,
        "move_ids": (1, 2, 3, 4),
    }
    base.update(overrides)
    return base


class NormalizeTrainerPartyMemberTests(unittest.TestCase):
    def test_normalizes_a_custom_moves_member(self) -> None:
        normalized = normalize_trainer_party_member(_member(), has_custom_moves=True)

        self.assertEqual(normalized["species_id"], 106)
        self.assertEqual(normalized["level"], 37)
        self.assertEqual(normalized["held_item_id"], 207)
        self.assertEqual(normalized["move_ids"], [1, 2, 3, 4])
        self.assertEqual(normalized["moves_source"], "explicit")
        # Ability/gender/IVs/EVs aren't stored per party slot in Gen III.
        self.assertIsNone(normalized["ability"])
        self.assertIsNone(normalized["nature"])
        self.assertIsNone(normalized["gender"])
        self.assertIsNone(normalized["ivs"])
        self.assertIsNone(normalized["evs"])
        self.assertIsNone(normalized["calculated_stats"])
        self.assertEqual(normalized["source_fields"], {"iv_like_value": 100})

    def test_normalizes_a_level_up_member(self) -> None:
        normalized = normalize_trainer_party_member(_member(), has_custom_moves=False)

        self.assertEqual(normalized["move_ids"], [])
        self.assertEqual(normalized["moves_source"], "level-up")

    def test_rejects_a_missing_field(self) -> None:
        member = _member()
        del member["species_id"]
        with self.assertRaises(DataSourceError):
            normalize_trainer_party_member(member, has_custom_moves=True)

    def test_rejects_a_negative_iv_like_value(self) -> None:
        with self.assertRaises(DataSourceError):
            normalize_trainer_party_member(
                _member(iv_strength=-1), has_custom_moves=True
            )


class DeriveTrainerPartyAttributesTests(unittest.TestCase):
    def test_returns_the_member_unchanged(self) -> None:
        normalized = normalize_trainer_party_member(_member(), has_custom_moves=True)

        derived = derive_trainer_party_attributes(
            normalized,
            trainer_id=317,
            class_id=0x54,
            class_gender=None,
            gender_ratio=None,
            base_stats={"hp": 50, "attack": 120, "defense": 53},
        )

        self.assertIsNone(derived["calculated_stats"])
        self.assertEqual(derived, normalized)


if __name__ == "__main__":
    unittest.main()
