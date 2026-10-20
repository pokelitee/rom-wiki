from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.shared.moves import parse_move_record
from romwiki.util.errors import InvalidRomError


class Gen5MoveTests(unittest.TestCase):
    def test_decodes_move_mechanics_and_provenance(self) -> None:
        # Real Thunderbolt record from a Black/White ROM: electric/special,
        # 95 power, 100 accuracy, 15 PP, 10% paralysis chance, single target.
        data = bytearray(36)
        data[0] = 12  # electric
        data[2] = 2  # category: special
        data[3] = 95  # power
        data[4] = 100  # accuracy
        data[5] = 15  # pp
        struct.pack_into("<b", data, 6, 0)  # priority
        data[10] = 10  # effect chance
        struct.pack_into("<H", data, 16, 6)  # effect id
        data[20] = 0  # target
        struct.pack_into("<I", data, 32, 0x48)  # flags

        move = parse_move_record(bytes(data), move_id=85, archive_path="movedata.narc")

        self.assertEqual(move.type_id, 12)
        self.assertEqual(move.damage_class_id, 2)
        self.assertEqual(move.power, 95)
        self.assertEqual(move.accuracy, 100)
        self.assertEqual(move.pp, 15)
        self.assertEqual(move.priority, 0)
        self.assertEqual(move.effect_chance, 10)
        self.assertEqual(move.effect_id, 6)
        self.assertEqual(move.target_id, 0)
        self.assertEqual(move.flags, 0x48)
        self.assertEqual(move.provenance.member, 85)
        self.assertEqual(move.provenance.archive, "movedata.narc")

    def test_decodes_signed_priority(self) -> None:
        data = bytearray(36)
        struct.pack_into("<b", data, 6, 1)

        move = parse_move_record(bytes(data), move_id=98, archive_path="movedata.narc")

        self.assertEqual(move.priority, 1)

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_move_record(b"short", move_id=1, archive_path="movedata.narc")


if __name__ == "__main__":
    unittest.main()
