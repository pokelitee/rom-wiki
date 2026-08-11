from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import (
    parse_trainer_class_genders,
    parse_trainer_record,
)
from romwiki.engines.gen4.dppt.battle_variants import (
    extract_trainer_battle_families,
)
from romwiki.engines.gen4.dppt.trainers import (
    parse_trainer_class_prize_multipliers,
)
from romwiki.util.errors import InvalidRomError


class Gen4TrainerTests(unittest.TestCase):
    def test_decodes_flags_party_forms_and_trailing_data(self) -> None:
        trainer = bytearray(20)
        struct.pack_into("<BBBB4HII", trainer, 0, 3, 2, 7, 1, 5, 0, 0, 0, 9, 2)
        party = (
            struct.pack("<BBHHH4HH", 100, 1, 42, 479 | (2 << 10), 6, 85, 86, 87, 88, 3)
            + b"\xff\xff"
        )

        result = parse_trainer_record(
            bytes(trainer),
            party,
            trainer_id=12,
            name="Tristan",
            class_names=("Pokémon Trainer", "Youngster", "Ace Trainer"),
            class_genders=("female", "male", "male"),
            class_prize_multipliers=(0, 4, 12),
            trainer_archive="trdata.narc",
            party_archive="trpoke.narc",
        )

        self.assertTrue(result.has_custom_moves)
        self.assertTrue(result.has_held_items)
        self.assertTrue(result.double_battle)
        self.assertEqual(result.class_gender, "male")
        self.assertEqual(result.victory_money_multiplier, 12)
        self.assertEqual(result.party[0].species_id, 479)
        self.assertEqual(result.party[0].form_id, 2)
        self.assertEqual(result.party[0].move_ids, (85, 86, 87, 88))
        self.assertEqual(result.trailing_party_data, b"\xff\xff")

    def test_rejects_truncated_party(self) -> None:
        trainer = bytearray(20)
        trainer[3] = 1
        with self.assertRaises(InvalidRomError):
            parse_trainer_record(
                bytes(trainer),
                b"",
                trainer_id=1,
                name="",
                class_names=("Pokémon Trainer",),
                class_genders=("male",),
                class_prize_multipliers=(0,),
                trainer_archive="trdata.narc",
                party_archive="trpoke.narc",
            )

    def test_omits_unavailable_prize_multiplier(self) -> None:
        trainer = bytearray(20)

        result = parse_trainer_record(
            bytes(trainer),
            b"",
            trainer_id=1,
            name="Silver",
            class_names=("Rival",),
            class_genders=("male",),
            class_prize_multipliers=None,
            trainer_archive="trdata.narc",
            party_archive="trpoke.narc",
        )

        self.assertIsNone(result.victory_money_multiplier)
        self.assertNotIn("victory_money_multiplier", result.to_dict())

    def test_decodes_trainer_class_gender_table(self) -> None:
        self.assertEqual(
            parse_trainer_class_genders(b"\x00\x01\x02", count=3),
            ("male", "female", "male"),
        )
        with self.assertRaisesRegex(InvalidRomError, "unknown values"):
            parse_trainer_class_genders(b"\x03", count=1)

    def test_decodes_trainer_class_prize_multiplier_table(self) -> None:
        self.assertEqual(
            parse_trainer_class_prize_multipliers(b"\x00\x04\x28", count=3),
            (0, 4, 40),
        )
        with self.assertRaisesRegex(InvalidRomError, "has size 2; expected 3"):
            parse_trainer_class_prize_multipliers(b"\x00\x04", count=3)

    def test_does_not_relate_profile_records_without_parties(self) -> None:
        records = [
            *(
                {"trainer_id": trainer_id, "party": []}
                for trainer_id in range(837, 843)
            ),
            *(
                {"trainer_id": trainer_id, "party": [{"species_id": 1}]}
                for trainer_id in range(850, 853)
            ),
        ]

        result = extract_trainer_battle_families(
            "renegade-platinum",
            {"trainer_variant_contract": "renegade-platinum-v1.3.0"},
            records,
        )

        family_ids = {family["id"] for family in result["battle_families"]}
        self.assertNotIn("barry-fight-area", family_ids)
        self.assertNotIn("barry-weekend-rematch-1", family_ids)
        self.assertIn("barry-starter-demo", family_ids)


if __name__ == "__main__":
    unittest.main()
