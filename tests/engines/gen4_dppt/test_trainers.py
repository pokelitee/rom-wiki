from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import (
    parse_trainer_class_genders,
    parse_trainer_record,
)
from romwiki.util.errors import InvalidRomError


class Gen4TrainerTests(unittest.TestCase):
    def test_decodes_flags_party_forms_and_trailing_data(self) -> None:
        trainer = bytearray(20)
        struct.pack_into("<BBBB4HII", trainer, 0, 3, 2, 7, 1, 5, 0, 0, 0, 9, 2)
        party = struct.pack(
            "<BBHHH4HH", 100, 1, 42, 479 | (2 << 10), 6, 85, 86, 87, 88, 3
        ) + b"\xff\xff"

        result = parse_trainer_record(
            bytes(trainer),
            party,
            trainer_id=12,
            name="Tristan",
            class_names=("Pokémon Trainer", "Youngster", "Ace Trainer"),
            class_genders=("female", "male", "male"),
            trainer_archive="trdata.narc",
            party_archive="trpoke.narc",
        )

        self.assertTrue(result.has_custom_moves)
        self.assertTrue(result.has_held_items)
        self.assertTrue(result.double_battle)
        self.assertEqual(result.class_gender, "male")
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
                trainer_archive="trdata.narc",
                party_archive="trpoke.narc",
            )

    def test_decodes_trainer_class_gender_table(self) -> None:
        self.assertEqual(
            parse_trainer_class_genders(b"\x00\x01\x02", count=3),
            ("male", "female", "male"),
        )
        with self.assertRaisesRegex(InvalidRomError, "unknown values"):
            parse_trainer_class_genders(b"\x03", count=1)


if __name__ == "__main__":
    unittest.main()
