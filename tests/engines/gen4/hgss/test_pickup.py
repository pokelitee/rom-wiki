from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.pickup import (
    parse_pickup_item_table,
    pickup_level_range_item_ids,
)
from romwiki.util.errors import InvalidRomError


class HgssPickupTests(unittest.TestCase):
    def test_decodes_sliding_level_ranges(self) -> None:
        common = tuple(range(1, 19))
        rare = tuple(range(101, 112))

        self.assertEqual(
            pickup_level_range_item_ids(common, rare, 0),
            (*range(1, 10), 101, 102),
        )
        self.assertEqual(
            pickup_level_range_item_ids(common, rare, 9),
            (*range(10, 19), 110, 111),
        )

    def test_validates_table_bounds_and_item_ids(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_pickup_item_table(b"\0\0", offset=2, count=1, item_count=537)
        with self.assertRaises(InvalidRomError):
            parse_pickup_item_table(
                struct.pack("<H", 537), offset=0, count=1, item_count=537
            )
