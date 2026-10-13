from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import SplitPickupTable, parse_pickup_tables
from romwiki.util.errors import InvalidRomError


class Gen4PickupTests(unittest.TestCase):
    def test_parses_all_four_tables_at_their_own_offsets(self) -> None:
        data = bytearray(64)
        data[0:4] = struct.pack("<HH", 17, 18)
        data[8:12] = struct.pack("<HH", 25, 92)
        data[16:18] = bytes((30, 40))
        data[20:23] = bytes((5, 10, 15))

        tables = parse_pickup_tables(
            bytes(data),
            common_offset=0,
            rare_offset=8,
            common_rate_offset=16,
            honey_rate_offset=20,
            common_count=2,
            rare_count=2,
            rate_count=2,
            honey_rate_count=3,
            item_count=468,
        )

        self.assertEqual(
            tables,
            SplitPickupTable(
                common_item_ids=(17, 18),
                rare_item_ids=(25, 92),
                common_rate=(30, 40),
                honey_gather_rate=(5, 10, 15),
            ),
        )

    def test_rejects_item_id_out_of_range(self) -> None:
        data = struct.pack("<H", 999)

        with self.assertRaises(InvalidRomError):
            parse_pickup_tables(
                data,
                common_offset=0,
                rare_offset=0,
                common_rate_offset=0,
                honey_rate_offset=0,
                common_count=1,
                rare_count=0,
                rate_count=0,
                honey_rate_count=0,
                item_count=468,
            )


if __name__ == "__main__":
    unittest.main()
