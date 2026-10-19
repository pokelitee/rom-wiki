from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.personal import parse_personal_record
from romwiki.util.errors import InvalidRomError


class Gen3PersonalDataTests(unittest.TestCase):
    def test_decodes_stats_flags_and_provenance(self) -> None:
        data = bytearray(28)
        data[0:9] = bytes((45, 49, 49, 45, 65, 65, 12, 3, 45))
        data[9] = 64
        struct.pack_into("<H", data, 0x0A, (2 << 2) | (1 << 8))
        struct.pack_into("<HH", data, 0x0C, 10, 20)
        data[0x10:0x19] = bytes((31, 20, 70, 3, 1, 7, 65, 0, 34))
        data[0x19] = 5 | (1 << 6)

        record = parse_personal_record(
            bytes(data), species_id=1, archive_path="offset:0x0"
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
        self.assertIsNone(record.wild_held_items.dark_grass)
        self.assertEqual(record.gender_ratio, 31)
        self.assertEqual(record.hatch_cycles, 20)
        self.assertEqual(record.base_friendship, 70)
        self.assertEqual(record.growth_rate_id, 3)
        self.assertEqual(record.egg_group_ids, (1, 7))
        self.assertEqual(record.ability_ids, (65, 0))
        self.assertTrue(record.flip_sprite)
        self.assertEqual(record.body_color_id, 5)
        self.assertEqual(record.machine_ids, ())
        self.assertEqual(record.machine_masks, (0, 0, 0, 0))
        self.assertEqual(record.provenance.member, 1)
        self.assertEqual(record.provenance.archive, "offset:0x0")
        self.assertEqual(record.provenance.source, "rom")

    def test_decodes_machine_compatibility_when_a_learnset_is_given(self) -> None:
        # Real Bulbasaur/Ivysaur mask (see machines.py's test coverage):
        # TM06/09/10/11/17/19/21/22/27/32/36/42/43/44/45, HM01/04/05/06.
        learnset = struct.pack("<II", 0x84350720, 0x00E41E08)

        record = parse_personal_record(
            bytes(28),
            species_id=1,
            archive_path="offset:0x0",
            tmhm_learnset=learnset,
        )

        self.assertEqual(
            record.machine_ids,
            (6, 9, 10, 11, 17, 19, 21, 22, 27, 32, 36, 42, 43, 44, 45, 51, 54, 55, 56),
        )
        self.assertEqual(record.machine_masks, (0x84350720, 0x00E41E08, 0, 0))

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_personal_record(b"short", species_id=1, archive_path="offset:0x0")


if __name__ == "__main__":
    unittest.main()
