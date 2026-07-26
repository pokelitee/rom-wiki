from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5_bw.pickup import (
    PICKUP_SLOT_CHANCES,
    parse_pickup_table,
    pickup_level_range_item_ids,
)
from romwiki.util.errors import InvalidRomError


def _overlay_with_table(offset: int, item_ids: tuple[int, ...]) -> bytes:
    data = bytearray(offset + len(item_ids) * 2)
    struct.pack_into(f"<{len(item_ids)}H", data, offset, *item_ids)
    return bytes(data)


class Gen5PickupTableTests(unittest.TestCase):
    def test_decodes_the_real_black_rom_table(self) -> None:
        # Real Black ROM pickup table (overlay 92, offset 1976): resolves to
        # the well-known real Gen5 Pickup item list.
        item_ids = (
            25,
            92,
            221,
            23,
            38,
            278,
            537,
            40,
            537,
            234,
            537,
            17,
            18,
            26,
            3,
            79,
            78,
            27,
            25,
            2,
            28,
            50,
            80,
            81,
            93,
            23,
            29,
            51,
            41,
        )
        overlay_data = _overlay_with_table(0x10, item_ids)

        table = parse_pickup_table(
            overlay_data, table_offset=0x10, archive_path="overlay92"
        )

        self.assertEqual(table.item_ids, item_ids)
        self.assertEqual(table.provenance.archive, "overlay92")
        self.assertEqual(table.provenance.member, 0x10)

    def test_rejects_a_table_that_does_not_fit_the_overlay(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_pickup_table(bytes(10), table_offset=0, archive_path="overlay92")


class Gen5PickupLevelRangeTests(unittest.TestCase):
    def test_level_range_zero_uses_the_first_sliding_window(self) -> None:
        item_ids = tuple(range(29))

        slots = pickup_level_range_item_ids(item_ids, 0)

        self.assertEqual(slots, (11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 1))
        self.assertEqual(len(slots), len(PICKUP_SLOT_CHANCES))

    def test_level_range_slides_by_one_entry_per_range(self) -> None:
        item_ids = tuple(range(29))

        slots = pickup_level_range_item_ids(item_ids, 9)

        self.assertEqual(slots, (20, 21, 22, 23, 24, 25, 26, 27, 28, 9, 10))

    def test_slot_chances_sum_to_one_hundred_percent(self) -> None:
        self.assertEqual(sum(PICKUP_SLOT_CHANCES), 100)


if __name__ == "__main__":
    unittest.main()
