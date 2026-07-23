from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import Gen4GameCornerPrize, parse_game_corner_prizes
from romwiki.util.errors import InvalidRomError


class Gen4GameCornerTests(unittest.TestCase):
    def test_parses_fixed_offset_prize_table(self) -> None:
        data = bytearray(64)
        data[8:16] = struct.pack("<HHHH", 251, 1000, 265, 2000)

        prizes = parse_game_corner_prizes(
            bytes(data), offset=8, count=2, item_count=468
        )

        self.assertEqual(
            prizes,
            (
                Gen4GameCornerPrize(item_id=251, price=1000),
                Gen4GameCornerPrize(item_id=265, price=2000),
            ),
        )

    def test_rejects_item_id_out_of_range(self) -> None:
        data = struct.pack("<HH", 999, 1000)

        with self.assertRaises(InvalidRomError):
            parse_game_corner_prizes(data, offset=0, count=1, item_count=468)

    def test_rejects_truncated_table(self) -> None:
        data = struct.pack("<H", 251)

        with self.assertRaises(InvalidRomError):
            parse_game_corner_prizes(data, offset=0, count=1, item_count=468)


if __name__ == "__main__":
    unittest.main()
