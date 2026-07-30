from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.locations import (
    parse_map_header_table,
    parse_wild_map_names,
)
from romwiki.engines.registry import get_engine

_MAP_NAMES = ("Route 1", "Route 2")


def _map_header(*, name_index: int, wild_set: int) -> bytes:
    record = bytearray(48)
    record[26] = name_index
    struct.pack_into("<H", record, 20, wild_set)
    return bytes(record)


class Gen5B2W2LocationsTests(unittest.TestCase):
    def test_engine_uses_the_b2w2_location_decoder(self) -> None:
        self.assertIs(
            get_engine("gen5_b2w2").locations.parse_map_header_table,
            parse_map_header_table,
        )

    def test_extracts_the_encounter_index_from_the_low_twelve_bits(self) -> None:
        data = _map_header(name_index=0, wild_set=0x4052) + _map_header(
            name_index=1, wild_set=0xC029
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertEqual(
            [header.encounter_map_index for header in headers],
            [82, 41],
        )

    def test_treats_flagged_null_encounter_indexes_as_absent(self) -> None:
        data = b"".join(
            _map_header(name_index=0, wild_set=value)
            for value in (0x0FFF, 0x1FFF, 0x5FFF, 0xBFFF, 0xDFFF, 0xFFFF)
        )

        headers = parse_map_header_table(
            data, map_names=_MAP_NAMES, archive_path="maps.narc"
        )

        self.assertTrue(all(header.encounter_map_index is None for header in headers))
        self.assertEqual(parse_wild_map_names(data, map_names=_MAP_NAMES), {})


if __name__ == "__main__":
    unittest.main()
