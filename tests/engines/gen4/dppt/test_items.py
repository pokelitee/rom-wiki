from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.dppt import find_item_archive_members, parse_item_record
from romwiki.util.errors import InvalidRomError


class Gen4ItemTests(unittest.TestCase):
    def test_parses_item_record(self) -> None:
        data = bytearray(34)
        struct.pack_into("<H", data, 0, 1200)
        data[2:8] = bytes((17, 10, 3, 26, 60, 70))
        flags = 12 | (1 << 5) | (1 << 6) | (4 << 7) | (5 << 11)
        struct.pack_into("<H", data, 8, flags)
        data[10:14] = bytes((8, 2, 1, 0))
        party_flags = (1 << 0) | (1 << 8) | (2 << 12) | (1 << 42)
        data[14:21] = party_flags.to_bytes(7, "little")
        struct.pack_into("<6b", data, 21, 1, 2, 3, 4, 5, 6)
        data[27:29] = bytes((20, 10))
        struct.pack_into("<3b", data, 29, 5, 3, 2)

        item = parse_item_record(
            bytes(data),
            item_id=162,
            data_archive_member=139,
            archive_path="items.narc",
        )

        self.assertEqual(item.price, 1200)
        self.assertEqual(item.hold_effect_id, 17)
        self.assertEqual(item.fling_power, 60)
        self.assertEqual(item.natural_gift_power, 70)
        self.assertEqual(item.natural_gift_type_id, 12)
        self.assertTrue(item.prevent_toss)
        self.assertTrue(item.selectable)
        self.assertEqual(item.field_pocket_id, 4)
        self.assertEqual(item.battle_pocket_mask, 5)
        self.assertEqual(item.field_use_function_id, 8)
        self.assertTrue(item.party_effects.heal_sleep)
        self.assertTrue(item.party_effects.revive)
        self.assertEqual(item.party_effects.attack_stages, 2)
        self.assertTrue(item.party_effects.hp_restore)
        self.assertEqual(item.party_effects.special_defense_ev_amount, 6)
        self.assertEqual(item.party_effects.hp_restored, 20)
        self.assertEqual(item.party_effects.friendship_medium_amount, 3)
        self.assertEqual(item.item_id, 162)
        self.assertEqual(item.data_archive_member, 139)
        self.assertEqual(item.provenance.member, 139)

    def test_rejects_wrong_record_size(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "must be 34 bytes"):
            parse_item_record(
                b"\0" * 33,
                item_id=1,
                data_archive_member=1,
                archive_path="items.narc",
            )

    def test_finds_item_to_archive_member_map(self) -> None:
        prefix = b"\xaa" * 10
        table = bytearray()
        expected = (*range(65), 0, 65)
        for member_id in expected:
            table.extend(struct.pack("<4H", member_id, 10, 20, 30))
        offset, members = find_item_archive_members(
            prefix + table + b"\xbb" * 10,
            item_count=len(expected),
            data_member_count=66,
        )
        self.assertEqual(offset, len(prefix))
        self.assertEqual(members, expected)


if __name__ == "__main__":
    unittest.main()
