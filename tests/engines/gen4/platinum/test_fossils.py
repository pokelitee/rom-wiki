from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.platinum import Gen4FossilRevival, parse_fossil_revival_table
from romwiki.util.errors import InvalidRomError


class Gen4FossilTests(unittest.TestCase):
    def test_parses_fixed_item_to_species_table(self) -> None:
        data = struct.pack("<HHHH", 103, 142, 101, 138)

        revivals = parse_fossil_revival_table(
            data, offset=0, count=2, item_count=468, species_count=496
        )

        self.assertEqual(
            revivals,
            (
                Gen4FossilRevival(item_id=103, species_id=142),
                Gen4FossilRevival(item_id=101, species_id=138),
            ),
        )

    def test_rejects_invalid_species(self) -> None:
        data = struct.pack("<HH", 103, 999)

        with self.assertRaises(InvalidRomError):
            parse_fossil_revival_table(
                data, offset=0, count=1, item_count=468, species_count=496
            )

    def test_rejects_truncated_table(self) -> None:
        data = struct.pack("<H", 103)

        with self.assertRaises(InvalidRomError):
            parse_fossil_revival_table(
                data, offset=0, count=1, item_count=468, species_count=496
            )

    def test_reads_entries_from_a_nonzero_offset(self) -> None:
        data = bytes(6) + struct.pack("<HH", 104, 345)

        revivals = parse_fossil_revival_table(
            data, offset=6, count=1, item_count=468, species_count=496
        )

        self.assertEqual(revivals, (Gen4FossilRevival(item_id=104, species_id=345),))

    def test_rejects_the_empty_item_sentinel(self) -> None:
        data = struct.pack("<HH", 0, 142)

        with self.assertRaisesRegex(InvalidRomError, "invalid item 0"):
            parse_fossil_revival_table(
                data, offset=0, count=1, item_count=468, species_count=496
            )

    def test_rejects_a_negative_offset(self) -> None:
        data = struct.pack("<HH", 103, 142)

        with self.assertRaisesRegex(InvalidRomError, "outside the ROM image"):
            parse_fossil_revival_table(
                data, offset=-4, count=1, item_count=468, species_count=496
            )


if __name__ == "__main__":
    unittest.main()
