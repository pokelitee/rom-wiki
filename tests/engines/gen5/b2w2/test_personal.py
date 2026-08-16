from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2 import (
    ITEM_FIELD_USE_NAMES,
    ITEM_NAME_COUNT,
    PERSONAL_FORM_MEMBERS,
    PERSONAL_INTERNAL_MEMBERS,
    PERSONAL_RECORD_COUNT,
    POKEMON_NAME_COUNT,
    parse_personal_record,
)
from romwiki.util.errors import InvalidRomError


class Gen5B2W2PersonalDataTests(unittest.TestCase):
    def test_declares_the_sequel_archive_member_layout(self) -> None:
        self.assertEqual(PERSONAL_RECORD_COUNT, 709)
        self.assertEqual(PERSONAL_INTERNAL_MEMBERS[650], "pokestar-studios-1")
        self.assertEqual(PERSONAL_INTERNAL_MEMBERS[684], "pokestar-studios-35")
        self.assertEqual(PERSONAL_FORM_MEMBERS[685], "deoxys-attack")
        self.assertEqual(PERSONAL_FORM_MEMBERS[703], "kyurem-white")
        self.assertEqual(PERSONAL_FORM_MEMBERS[708], "landorus-therian")
        self.assertEqual(POKEMON_NAME_COUNT, 687)
        self.assertEqual(ITEM_NAME_COUNT, 639)
        self.assertEqual(ITEM_FIELD_USE_NAMES[26], "xtransceiver")
        self.assertEqual(ITEM_FIELD_USE_NAMES[30], "reveal-glass")

    def test_decodes_the_bw_compatible_fields_from_a_76_byte_record(self) -> None:
        data = bytearray(76)
        data[0:9] = bytes((79, 83, 100, 78, 85, 105, 16, 2, 3))
        struct.pack_into("<H", data, 0x0A, 3 << 10)
        struct.pack_into("<HHH", data, 0x0C, 1, 2, 3)
        data[0x12:0x1B] = bytes((0, 120, 90, 5, 15, 15, 22, 0, 128))
        data[0x21] = 4
        struct.pack_into("<H", data, 0x22, 270)
        data[0x28] = 1  # table position 0: TM01 -> machine_id 1
        data[0x33] = 1 << 4  # table position 92: HM01 -> machine_id 96
        data[0x34] = 1 << 4  # table position 100: TM95 -> machine_id 95
        data[0x3C:0x4C] = b"\xff" * 16

        record = parse_personal_record(
            bytes(data), species_id=708, archive_path="a/0/1/6"
        )

        self.assertEqual(record.base_stats.hp, 79)
        self.assertEqual(record.type_ids, (16, 2))
        self.assertEqual(record.base_experience, 270)
        self.assertEqual(record.ev_yields.special_defense, 3)
        self.assertEqual(record.wild_held_items.dark_grass, 3)
        self.assertEqual(record.ability_ids, (22, 0, 128))
        # Bits are indexed by physical ARM9 table position, which interleaves
        # TM01-92, HM01-06, then TM93-95 -- distinct from the contiguous
        # published machine_id (TM01-95 = 1-95, HM01-06 = 96-101).
        self.assertEqual(record.machine_ids, (1, 95, 96))
        self.assertEqual(record.provenance.member, 708)

    def test_rejects_a_bw_sized_record(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "expected 76"):
            parse_personal_record(bytes(60), species_id=1, archive_path="a/0/1/6")

    def test_can_repair_a_profile_declared_secondary_egg_group_editor_bug(
        self,
    ) -> None:
        data = bytearray(76)
        data[0x16] = 5
        data[0x17] = 91

        record = parse_personal_record(
            bytes(data),
            species_id=133,
            archive_path="a/0/1/6",
            repair_invalid_secondary_egg_group=True,
        )

        self.assertEqual(record.egg_group_ids, (5, 5))


if __name__ == "__main__":
    unittest.main()
