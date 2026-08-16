from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.safari import parse_safari_encounter_record
from romwiki.util.errors import InvalidRomError


def _record() -> bytes:
    data = bytearray((2, 1, 0, 0, 0, 0, 0, 0))
    species_id = 1
    for block_count in (2, 1, 0, 0, 0):
        for _ in range(3 * 10):
            data.extend(struct.pack("<HBB", species_id, 10, 0))
            species_id += 1
        for _ in range(3 * block_count):
            data.extend(struct.pack("<HBB", species_id, 20, 0))
            species_id += 1
        if block_count == 2:
            data.extend(bytes((1, 3, 0, 0, 3, 5, 4, 7)))
        elif block_count == 1:
            data.extend(bytes((4, 2, 0, 0)))
    return bytes(data)


class SafariEncounterTests(unittest.TestCase):
    def test_parses_methods_times_and_two_block_requirements(self) -> None:
        record = parse_safari_encounter_record(
            _record(),
            safari_area_id=0,
            archive_path="a/2/3/0",
            species_count=500,
        )

        self.assertEqual(record.area_name, "Plains")
        self.assertEqual(len(record.methods["grass"].base_pools["morning"]), 10)
        block = record.methods["grass"].block_encounters[1]
        self.assertEqual(
            [(value.block_type, value.count) for value in block.requirements],
            [("peak", 5), ("waterside", 7)],
        )
        self.assertEqual(block.times["night"].level, 20)
        self.assertEqual(len(record.methods["surf"].block_encounters), 1)
        self.assertEqual(record.provenance.member, 0)

    def test_validates_exact_size_and_padding(self) -> None:
        with self.assertRaisesRegex(InvalidRomError, "expected"):
            parse_safari_encounter_record(
                _record()[:-1],
                safari_area_id=0,
                archive_path="a/2/3/0",
                species_count=500,
            )
        data = bytearray(_record())
        data[7] = 1
        with self.assertRaisesRegex(InvalidRomError, "header padding"):
            parse_safari_encounter_record(
                bytes(data),
                safari_area_id=0,
                archive_path="a/2/3/0",
                species_count=500,
            )

    def test_validates_species_levels_and_requirements(self) -> None:
        data = bytearray(_record())
        struct.pack_into("<H", data, 8, 0)
        with self.assertRaisesRegex(InvalidRomError, "invalid species"):
            parse_safari_encounter_record(
                bytes(data),
                safari_area_id=0,
                archive_path="a/2/3/0",
                species_count=500,
            )
        data = bytearray(_record())
        data[10] = 0
        with self.assertRaisesRegex(InvalidRomError, "invalid level"):
            parse_safari_encounter_record(
                bytes(data),
                safari_area_id=0,
                archive_path="a/2/3/0",
                species_count=500,
            )
        data = bytearray(_record())
        requirement_offset = 8 + 30 * 4 + 6 * 4
        data[requirement_offset] = 5
        with self.assertRaisesRegex(InvalidRomError, "invalid block type"):
            parse_safari_encounter_record(
                bytes(data),
                safari_area_id=0,
                archive_path="a/2/3/0",
                species_count=500,
            )
