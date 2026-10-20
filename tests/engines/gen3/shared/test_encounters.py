from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen3.shared.encounters import (
    count_encounter_headers,
    parse_encounter_record,
    parse_header,
    parse_method_info,
    parse_method_slots,
)
from romwiki.schema import EncounterMethod
from romwiki.util.errors import InvalidRomError


def _header(
    *,
    map_group: int = 3,
    map_num: int = 22,
    land_pointer: int = 0x0823C610,
    water_pointer: int = 0,
    rock_smash_pointer: int = 0,
    fishing_pointer: int = 0,
) -> bytes:
    data = bytearray(20)
    data[0] = map_group
    data[1] = map_num
    struct.pack_into("<I", data, 0x04, land_pointer)
    struct.pack_into("<I", data, 0x08, water_pointer)
    struct.pack_into("<I", data, 0x0C, rock_smash_pointer)
    struct.pack_into("<I", data, 0x10, fishing_pointer)
    return bytes(data)


def _info(*, rate: int, slots_pointer: int) -> bytes:
    data = bytearray(8)
    data[0] = rate
    struct.pack_into("<I", data, 4, slots_pointer)
    return bytes(data)


def _slots(*entries: tuple[int, int, int]) -> bytes:
    data = bytearray(4 * len(entries))
    for index, (min_level, max_level, species) in enumerate(entries):
        struct.pack_into("<BBH", data, index * 4, min_level, max_level, species)
    return bytes(data)


class ParseHeaderTests(unittest.TestCase):
    def test_decodes_map_group_num_and_pointers(self) -> None:
        header = _header(map_group=3, map_num=22, land_pointer=0x0823C610)

        map_group, map_num, pointers = parse_header(header, map_index=90)

        self.assertEqual(map_group, 3)
        self.assertEqual(map_num, 22)
        self.assertEqual(pointers["land"], 0x0823C610)
        self.assertEqual(pointers["water"], 0)
        self.assertEqual(pointers["rock_smash"], 0)
        self.assertEqual(pointers["fishing"], 0)

    def test_rejects_an_unexpected_header_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_header(b"short", map_index=0)


class ParseMethodInfoTests(unittest.TestCase):
    def test_decodes_rate_and_slots_pointer(self) -> None:
        info = _info(rate=21, slots_pointer=0x0823C608)

        rate, slots_pointer = parse_method_info(info, map_index=90, name="land")

        self.assertEqual(rate, 21)
        self.assertEqual(slots_pointer, 0x0823C608)

    def test_rejects_an_unexpected_info_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_method_info(b"short", map_index=0, name="land")


class ParseMethodSlotsTests(unittest.TestCase):
    def test_decodes_twelve_land_slots(self) -> None:
        entries = tuple((6 + i, 6 + i, 21) for i in range(12))
        data = _slots(*entries)

        slots = parse_method_slots(data, map_index=90, name="land", count=12)

        self.assertEqual(len(slots), 12)
        self.assertEqual(slots[0].minimum_level, 6)
        self.assertEqual(slots[0].maximum_level, 6)
        self.assertEqual(slots[0].species_id, 21)

    def test_rejects_an_unexpected_slot_array_size(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_method_slots(b"\x00" * 3, map_index=0, name="land", count=12)


class ParseEncounterRecordTests(unittest.TestCase):
    def test_builds_an_area_with_only_land_present(self) -> None:
        land = EncounterMethod(rate=21, slots=())

        record = parse_encounter_record(
            3, 22, {"land": land}, map_index=90, archive_path="offset:0x0"
        )

        self.assertEqual(record.area_id, 90)
        self.assertEqual(record.map_group, 3)
        self.assertEqual(record.map_num, 22)
        self.assertIs(record.land, land)
        self.assertIsNone(record.water)
        self.assertIsNone(record.rock_smash)
        self.assertIsNone(record.fishing)
        self.assertEqual(record.provenance.member, 90)
        self.assertEqual(record.provenance.source, "rom")
        self.assertEqual(record.locations, ())

    def test_builds_an_area_with_all_four_methods_present(self) -> None:
        methods = {
            "land": EncounterMethod(rate=21, slots=()),
            "water": EncounterMethod(rate=2, slots=()),
            "rock_smash": EncounterMethod(rate=25, slots=()),
            "fishing": EncounterMethod(rate=20, slots=()),
        }

        record = parse_encounter_record(
            3, 22, methods, map_index=90, archive_path="offset:0x0"
        )

        self.assertEqual(record.land.rate, 21)
        self.assertEqual(record.water.rate, 2)
        self.assertEqual(record.rock_smash.rate, 25)
        self.assertEqual(record.fishing.rate, 20)

    def test_rejects_an_unknown_method_name(self) -> None:
        with self.assertRaises(InvalidRomError):
            parse_encounter_record(
                3,
                22,
                {"grass_cave": EncounterMethod(rate=1, slots=())},
                map_index=0,
                archive_path="offset:0x0",
            )


class CountEncounterHeadersTests(unittest.TestCase):
    def test_counts_headers_before_the_terminator(self) -> None:
        data = bytearray(20 * 4)
        data[20 * 3] = 0xFF
        data[20 * 3 + 1] = 0xFF

        count = count_encounter_headers(
            lambda offset, size: bytes(data[offset : offset + size]), 0
        )

        self.assertEqual(count, 3)

    def test_rejects_a_table_without_a_terminator(self) -> None:
        with self.assertRaises(InvalidRomError):
            count_encounter_headers(lambda offset, size: bytes(size), 0)


if __name__ == "__main__":
    unittest.main()
