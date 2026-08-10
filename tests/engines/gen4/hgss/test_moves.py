from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss import parse_move_record
from romwiki.util.errors import InvalidRomError


class HgssMoveTests(unittest.TestCase):
    def test_decodes_a_real_retail_thunder_move_record(self) -> None:
        data = bytes.fromhex("0600015f0d640f0a0000001211000000")

        move = parse_move_record(data, move_id=85, archive_path="a/0/1/1")

        self.assertEqual(move.effect_id, 6)
        self.assertEqual(move.damage_class_id, 1)
        self.assertEqual(move.power, 95)
        self.assertEqual(move.type_id, 13)
        self.assertEqual(move.accuracy, 100)
        self.assertEqual(move.pp, 15)
        self.assertEqual(move.effect_chance, 10)
        self.assertEqual(move.flags, 0x12)
        self.assertEqual(move.provenance.member, 85)

    def test_rejects_nonzero_padding(self) -> None:
        data = bytearray(16)
        data[14] = 1

        with self.assertRaisesRegex(InvalidRomError, "nonzero padding"):
            parse_move_record(bytes(data), move_id=1, archive_path="a/0/1/1")


if __name__ == "__main__":
    unittest.main()
