from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.b2w2.swarms import parse_swarm_table
from romwiki.util.errors import InvalidRomError


class SwarmTableTests(unittest.TestCase):
    def test_parses_header_species_and_level_range(self) -> None:
        data = b"".join(
            (
                struct.pack("<HHBBBB", 317, 83, 0, 40, 55, 0),
                struct.pack("<HHBBBB", 331, 311, 0, 40, 55, 0),
            )
        )

        records = parse_swarm_table(
            data,
            record_count=2,
            archive_path="overlay36",
            table_offset=0x50BFC,
            map_header_count=615,
            species_count=650,
        )

        self.assertEqual((records[0].header_id, records[0].species_id), (317, 83))
        self.assertEqual((records[0].minimum_level, records[0].maximum_level), (40, 55))
        self.assertEqual(records[1].table_offset, 0x50C04)

    def test_rejects_duplicate_headers_and_nonzero_padding(self) -> None:
        duplicate = struct.pack("<HHBBBB", 1, 25, 0, 5, 10, 0) * 2
        with self.assertRaisesRegex(InvalidRomError, "more than once"):
            parse_swarm_table(
                duplicate,
                record_count=2,
                archive_path="overlay36",
                table_offset=0,
                map_header_count=10,
                species_count=100,
            )

        malformed = struct.pack("<HHBBBB", 1, 25, 1, 5, 10, 0)
        with self.assertRaisesRegex(InvalidRomError, "nonzero padding"):
            parse_swarm_table(
                malformed,
                record_count=1,
                archive_path="overlay36",
                table_offset=0,
                map_header_count=10,
                species_count=100,
            )
