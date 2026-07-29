from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.bw.personal import parse_personal_record
from romwiki.util.errors import InvalidRomError


class Gen5PersonalDataTests(unittest.TestCase):
    def test_decodes_stats_flags_and_provenance(self) -> None:
        data = bytearray(60)
        data[0:9] = bytes((45, 49, 49, 45, 65, 65, 12, 3, 45))
        struct.pack_into("<H", data, 0x0A, (2 << 2) | (1 << 8))
        struct.pack_into("<HH", data, 0x0C, 10, 20)
        struct.pack_into("<H", data, 0x10, 30)
        data[0x12:0x1B] = bytes((31, 20, 70, 3, 1, 7, 65, 0, 34))
        data[0x21] = 5 | (1 << 6)
        struct.pack_into("<H", data, 0x22, 64)
        data[0x28] |= 1 << 0  # machine 1 (TM01)
        data[0x28 + 12] |= 1 << 4  # machine 101 (HM06)

        record = parse_personal_record(
            bytes(data), species_id=1, archive_path="a/0/1/6"
        )

        self.assertEqual(record.base_stats.hp, 45)
        self.assertEqual(record.base_stats.special_attack, 65)
        self.assertEqual(record.type_ids, (12, 3))
        self.assertEqual(record.catch_rate, 45)
        self.assertEqual(record.base_experience, 64)
        self.assertEqual(record.ev_yields.attack, 2)
        self.assertEqual(record.ev_yields.special_attack, 1)
        self.assertEqual(record.wild_held_items.common, 10)
        self.assertEqual(record.wild_held_items.rare, 20)
        self.assertEqual(record.wild_held_items.dark_grass, 30)
        self.assertEqual(record.gender_ratio, 31)
        self.assertEqual(record.hatch_cycles, 20)
        self.assertEqual(record.base_friendship, 70)
        self.assertEqual(record.growth_rate_id, 3)
        self.assertEqual(record.egg_group_ids, (1, 7))
        self.assertEqual(record.ability_ids, (65, 0, 34))
        self.assertTrue(record.flip_sprite)
        self.assertEqual(record.body_color_id, 5)
        self.assertEqual(record.machine_ids, (1, 101))
        self.assertEqual(record.provenance.member, 1)
        self.assertEqual(record.provenance.archive, "a/0/1/6")

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_personal_record(b"short", species_id=1, archive_path="a/0/1/6")

    def test_zero_pads_the_undersized_member_zero_placeholder(self) -> None:
        record = parse_personal_record(bytes(56), species_id=0, archive_path="a/0/1/6")

        self.assertEqual(record.species_id, 0)
        self.assertEqual(record.base_stats.hp, 0)
        self.assertEqual(record.ability_ids, (0, 0, 0))

    def test_rejects_a_placeholder_sized_record_for_a_real_species(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_personal_record(bytes(56), species_id=1, archive_path="a/0/1/6")


if __name__ == "__main__":
    unittest.main()
