from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt.moves import parse_move_record
from romwiki.util.errors import InvalidRomError


class Gen4MoveTests(unittest.TestCase):
    def test_decodes_move_mechanics_and_provenance(self) -> None:
        data = bytearray(16)
        struct.pack_into("<H", data, 0, 6)
        data[2:8] = bytes((1, 90, 13, 100, 15, 10))
        struct.pack_into("<H", data, 8, 4)
        struct.pack_into("<b", data, 10, -1)
        data[11:14] = bytes((0x12, 17, 3))

        move = parse_move_record(bytes(data), move_id=85, archive_path="moves.narc")

        self.assertEqual(move.effect_id, 6)
        self.assertEqual(move.damage_class_id, 1)
        self.assertEqual(move.power, 90)
        self.assertEqual(move.type_id, 13)
        self.assertEqual(move.accuracy, 100)
        self.assertEqual(move.pp, 15)
        self.assertEqual(move.effect_chance, 10)
        self.assertEqual(move.target_id, 4)
        self.assertEqual(move.priority, -1)
        self.assertEqual(move.flags, 0x12)
        self.assertEqual(move.provenance.member, 85)

    def test_rejects_an_unexpected_record_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_move_record(b"short", move_id=1, archive_path="moves.narc")

    def test_rejects_nonzero_padding(self) -> None:
        data = bytearray(16)
        data[14] = 1
        with self.assertRaises(InvalidRomError):
            parse_move_record(bytes(data), move_id=1, archive_path="moves.narc")


if __name__ == "__main__":
    unittest.main()
