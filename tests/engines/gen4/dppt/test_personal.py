from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt.personal import parse_personal_record
from romwiki.util.errors import InvalidRomError


class Gen4PersonalDataTests(unittest.TestCase):
    def test_decodes_stats_flags_and_provenance(self) -> None:
        data = bytearray(44)
        data[0:10] = bytes((45, 49, 49, 45, 65, 65, 12, 3, 45, 64))
        struct.pack_into("<H", data, 10, (2 << 2) | (1 << 8))
        struct.pack_into("<HH", data, 12, 10, 20)
        data[16:26] = bytes((31, 20, 70, 3, 1, 7, 65, 34, 0, 0x85))
        struct.pack_into("<IIII", data, 28, 1, 0, 0, 1 << 3)

        record = parse_personal_record(
            bytes(data), species_id=1, archive_path="personal.narc"
        )

        self.assertEqual(record.base_stats.hp, 45)
        self.assertEqual(record.base_stats.special_attack, 65)
        self.assertEqual(record.type_ids, (12, 3))
        self.assertEqual(record.ev_yields.attack, 2)
        self.assertEqual(record.ev_yields.special_attack, 1)
        self.assertEqual(record.wild_held_items.rare, 20)
        self.assertEqual(record.ability_ids, (65, 34))
        self.assertTrue(record.flip_sprite)
        self.assertEqual(record.body_color_id, 5)
        self.assertEqual(record.machine_ids, (1, 100))
        self.assertEqual(record.provenance.member, 1)

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_personal_record(b"short", species_id=1, archive_path="personal.narc")


if __name__ == "__main__":
    unittest.main()
